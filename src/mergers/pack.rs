use crate::util::{self, settings};
use anyhow::{Context, Result};
use cow_utils::CowUtils;
use pyo3::prelude::*;
use rayon::prelude::*;
use roead::{
    sarc::{Sarc, SarcWriter},
    yaz0::compress,
    Bytes, Endian,
};
use std::{
    collections::{HashMap, HashSet},
    path::{Path, PathBuf},
};

static SPECIAL: &[&str] = &[
    "gamedata",
    "savedataformat",
    // "Layout/Common.sblarc", We'll try doing this
    "tera_resource.Nin_NX_NVN",
    "Dungeon",
    "Bootup_",
    "AocMainField",
];

static EXCLUDE_EXTS: &[&str] = &["sbeventpack"];

pub fn packs_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let packs_module = PyModule::new(py, "packs")?;
    packs_module.add_wrapped(wrap_pyfunction!(merge_sarcs))?;
    parent.add_submodule(packs_module)?;
    Ok(())
}

fn merge_sarc(sarcs: Vec<Sarc>, endian: Endian) -> Result<Bytes> {
    let all_files: HashSet<String> = sarcs
        .iter()
        .flat_map(|s| {
            s.files()
                .map(|f| f.name_unchecked().to_owned())
                .collect::<Vec<String>>()
        })
        .collect();
    let files = all_files
        .into_iter()
        .map(|file| {
            let mut modded = true;
            let data = sarcs
                .iter()
                .rev()
                .filter_map(|s| {
                    let data = s.files().find_map(|f| {
                        if f.name_unchecked() == file {
                            Some(f.data().to_vec())
                        } else {
                            None
                        }
                    });
                    data
                })
                .find(|d| util::is_file_modded(&file.cow_replace(".s", "."), d))
                .or_else(|| {
                    modded = false;
                    sarcs.iter().find_map(|s| {
                        s.files().find_map(|f| {
                            if f.name_unchecked() == file {
                                Some(f.data().to_vec())
                            } else {
                                None
                            }
                        })
                    })
                })
                .context("Can't find any SARCs versions for file")?;

            let file_path = Path::new(&file);

            if modded
                && data.len() > 0x40
                && (&data[..4] == b"SARC" || &data[0x11..0x15] == b"SARC")
                && !file_path
                    .extension()
                    .and_then(|e| e.to_str())
                    .map(|e| EXCLUDE_EXTS.contains(&e))
                    .unwrap_or_default()
                && !SPECIAL.iter().any(|s| file.as_str().contains(s))
            {
                let nest_sarcs: Vec<Sarc> = sarcs
                    .iter()
                    .filter_map(|s| {
                        s.files()
                            .find(|f| f.name() == Some(&file))
                            .and_then(|d| Sarc::read(d.data().to_vec()).ok())
                    })
                    .collect();
                let mut merged = merge_sarc(nest_sarcs, endian)?;
                if file_path
                    .extension()
                    .map(|e| e.to_str().unwrap().starts_with('s'))
                    .unwrap_or_default()
                {
                    merged = compress(&merged);
                }

                Ok((file, merged.as_slice().into()))
            } else {
                Ok((file, data.to_vec()))
            }
        })
        .collect::<Result<Vec<(String, Vec<u8>)>>>()?;
    Ok(SarcWriter::from_files(endian, files).to_binary())
}

#[pyfunction]
pub fn merge_sarcs(py: Python, diffs: HashMap<PathBuf, Vec<PathBuf>>) -> PyResult<()> {
    let settings = settings().clone();
    py.allow_threads(|| -> Result<()> {
        diffs
            .par_iter()
            .filter(|f| f.0.file_name() != Some(std::ffi::OsStr::new("AocMainField.pack")))
            .try_for_each(|(path, sarc_paths)| -> Result<()> {
                let out = settings.master_mod_dir().join(&path);
                if out.exists() {
                    std::fs::remove_file(&out)?;
                }
                let sarcs = sarc_paths
                    .iter()
                    .filter_map(|file| -> Option<Result<Sarc>> {
                        std::fs::read(&file)
                            .map(|data| Sarc::read(data).ok())
                            .map_err(anyhow::Error::from)
                            .transpose()
                    })
                    .collect::<Result<Vec<Sarc>>>()?;
                let mut merged = merge_sarc(sarcs, settings.endian())?;
                if out.extension().unwrap().to_str().unwrap().starts_with('s') {
                    merged = compress(merged);
                }
                std::fs::create_dir_all(&out.parent().unwrap())?;
                std::fs::write(out, merged)?;
                Ok(())
            })?;
        Ok(())
    })?;
    Ok(())
}
