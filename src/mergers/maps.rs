use crate::{settings::Settings, util, Result, RustError};
use anyhow::Context;
use jstr::jstr;
use pyo3::prelude::*;
use rayon::prelude::*;
use roead::{
    byml::{Byml, Hash},
    sarc::Sarc,
    yaz0::{compress, decompress},
};
use std::{
    collections::{BTreeSet, HashMap},
    fmt::Display,
    path::{Path, PathBuf},
};

pub fn maps_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let maps_module = PyModule::new(py, "maps")?;
    maps_module.add_wrapped(wrap_pyfunction!(merge_maps))?;
    parent.add_submodule(maps_module)?;
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
enum MapUnitType {
    Static,
    Dynamic,
}

impl Display for MapUnitType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(self, f)
    }
}

impl From<&str> for MapUnitType {
    fn from(mtype: &str) -> Self {
        match mtype {
            "Static" => Self::Static,
            "Dynamic" => Self::Dynamic,
            _ => panic!("Invalid map unit type: {}", mtype),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct MapUnit {
    unit: String,
    kind: MapUnitType,
    aocfield: bool,
}

impl Display for MapUnit {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}_{}", self.unit, self.kind)
    }
}

impl TryFrom<&Path> for MapUnit {
    type Error = RustError;
    fn try_from(value: &Path) -> Result<Self> {
        let mut split = value.file_stem().unwrap().to_str().unwrap().split('_');
        Ok(MapUnit {
            unit: split.next().context("Not a map unitt")?.into(),
            kind: split.next().context("Not a map unitt")?.into(),
            aocfield: value.to_str().unwrap().contains("AocField"),
        })
    }
}

impl MapUnit {
    fn from_unit_name(name: &str, aocfield: bool) -> Result<Self> {
        let mut split = name.split('_');
        Ok(Self {
            unit: split.next().context("Not a map unitt")?.into(),
            kind: split.next().context("Not a map unitt")?.into(),
            aocfield,
        })
    }

    #[inline]
    fn get_path(&self) -> String {
        let field = if self.aocfield {
            "AocField"
        } else {
            "MainField"
        };
        jstr!("Map/{field}/{&self.unit}/{&self.to_string()}.smubin")
    }

    fn get_base_path(&self) -> PathBuf {
        util::settings().main_game_dir().join(self.get_path())
    }

    fn get_aoc_path(&self) -> PathBuf {
        util::settings().dlc_dir().unwrap().join(self.get_path())
    }

    fn get_resource_path(&self) -> String {
        let field = if self.aocfield {
            "AocField"
        } else {
            "MainField"
        };
        jstr!("Map/{field}/{&self.unit}/{&self.to_string()}.mubin")
    }

    fn get_aoc_resource_path(&self) -> String {
        let field = if self.aocfield {
            "AocField"
        } else {
            "MainField"
        };
        jstr!("Aoc/0010/Map/{field}/{&self.unit}/{&self.to_string()}.mubin")
    }

    fn get_stock_base_map(&self) -> Result<Byml> {
        match self.kind {
            MapUnitType::Dynamic => {
                let path = self.get_base_path();
                Ok(Byml::from_binary(&decompress(&std::fs::read(&path)?)?)?)
            }
            MapUnitType::Static => {
                let pack = util::get_stock_pack("TitleBG")?;
                Ok(Byml::from_binary(&decompress(
                    &pack
                        .get_file_data(&self.get_path())
                        .ok_or_else(|| RustError::FileMissingFromSarc(self.get_path()))?,
                )?)?)
            }
        }
    }

    fn get_stock_dlc_map(&self) -> Result<Byml> {
        match self.kind {
            MapUnitType::Dynamic => {
                let path = self.get_aoc_path();
                Ok(Byml::from_binary(&decompress(&std::fs::read(&path)?)?)?)
            }
            MapUnitType::Static => {
                let pack = util::get_stock_pack("AocMainField")?;
                Ok(Byml::from_binary(&decompress(
                    &pack
                        .get_file_data(&self.get_path())
                        .ok_or_else(|| RustError::FileMissingFromSarc(self.get_path()))?,
                )?)?)
            }
        }
    }

    fn get_mod_base_map(&self, mod_dir: &Path) -> Result<Byml> {
        let path = mod_dir.join(util::content()).join(self.get_path());
        if path.exists() {
            Ok(Byml::from_binary(&decompress(&std::fs::read(&path)?)?)?)
        } else {
            let pack = Sarc::read(std::fs::read(
                mod_dir.join(util::content()).join("Pack/TitleBG.pack"),
            )?)?;
            Ok(Byml::from_binary(&decompress(
                &pack
                    .get_file_data(&self.get_path())
                    .ok_or_else(|| RustError::FileMissingFromSarc(self.get_path()))?,
            )?)?)
        }
    }

    fn get_mod_dlc_map(&self, mod_dir: &Path) -> Result<Byml> {
        let path = mod_dir.join(util::dlc()).join(self.get_path());
        Ok(Byml::from_binary(&decompress(&std::fs::read(&path)?)?)?)
    }
}

fn merge_entries(diff: &Hash, entries: &mut Vec<Byml>) -> Result<()> {
    let stock_hashes: Vec<u32> = entries
        .iter()
        .map(|e| e["HashId"].as_uint().unwrap())
        .collect();
    let mut orphans: Vec<Byml> = vec![];
    for (hash, entry) in diff["mod"].as_hash()? {
        let hash = hash.parse::<u32>().unwrap();
        if let Some(idx) = stock_hashes.iter().position(|h| *h == hash) {
            entries[idx] = entry.clone();
        } else {
            orphans.push(entry.clone());
        }
    }
    let to_del: BTreeSet<usize> = diff["del"]
        .as_array()?
        .iter()
        .filter_map(|b| b.as_uint().ok())
        .filter_map(|dh| stock_hashes.iter().position(|sh| *sh == dh))
        .collect();
    to_del.into_iter().rev().for_each(|i| {
        entries.remove(i);
    });
    entries.extend(
        diff["add"]
            .as_array()?
            .iter()
            .cloned()
            .chain(orphans.into_iter())
            .filter(|e| {
                !stock_hashes.contains(
                    &(e["HashId"]
                        .as_uint()
                        .or_else(|_| e["HashId"].as_int().map(|i| i as u32))
                        .unwrap()),
                )
            }),
    );
    entries.sort_by_cached_key(|e| {
        e["HashId"]
            .as_uint()
            .or_else(|_| e["HashId"].as_int().map(|i| i as u32))
            .unwrap()
    });
    Ok(())
}

fn merge_map(map_unit: MapUnit, diff: &Hash, settings: &Settings) -> Result<(String, u32)> {
    let mut new_map = if settings.dlc_dir().map(|d| d.exists()).unwrap_or_default() {
        map_unit.get_stock_dlc_map()
    } else {
        map_unit.get_stock_base_map()
    }?;
    if let Byml::Array(ref mut objs) = new_map["Objs"] {
        merge_entries(diff["Objs"].as_hash()?, objs)?;
    }
    if let Byml::Array(ref mut rails) = new_map["Rails"] {
        merge_entries(diff["Rails"].as_hash()?, rails)?;
    }
    let data = new_map.to_binary(settings.endian());
    let size = rstb::calc::calc_from_size_and_name(
        data.len(),
        "dummy.mubin",
        if settings.wiiu {
            rstb::Endian::Big
        } else {
            rstb::Endian::Little
        },
    )
    .unwrap();
    let out = settings
        .master_mod_dir()
        .join(if util::settings().dlc_dir().is_some() {
            util::dlc()
        } else {
            util::content()
        })
        .join(map_unit.get_path());
    if !out.parent().unwrap().exists() {
        std::fs::create_dir_all(out.parent().unwrap())?;
    }
    std::fs::write(out, compress(data))?;
    Ok((
        if settings.dlc_dir().is_some() {
            map_unit.get_aoc_resource_path()
        } else {
            map_unit.get_resource_path()
        },
        size,
    ))
}

#[pyfunction]
pub fn merge_maps(py: Python, diff_bytes: Vec<u8>) -> PyResult<PyObject> {
    let diffs = Byml::from_binary(&diff_bytes).unwrap();
    let rstb_values: HashMap<String, u32> = if let Byml::Hash(diffs) = diffs {
        py.allow_threads(|| -> Result<HashMap<String, u32>> {
            let settings = util::settings().clone();
            diffs
                .into_par_iter()
                .map(|(unit, diff)| {
                    let map_unit = MapUnit::from_unit_name(&unit, false)?;
                    merge_map(map_unit, diff.as_hash()?, &settings)
                })
                .collect::<Result<HashMap<String, u32>>>()
        })?
    } else {
        Default::default()
    };
    Ok(rstb_values.into_py(py))
}
