use crate::{util, Result};
use anyhow::Context;
use fs_err as fs;
use once_cell::sync::Lazy;
use pyo3::{prelude::*, types::PyBytes};
use rayon::prelude::*;
use roead::{
    byml::{Byml, Hash},
    yaz0::{compress, decompress},
};
use std::{collections::BTreeMap, sync::Arc};

type ActorMap = BTreeMap<u32, Byml>;

static STOCK_ACTORINFO: Lazy<Result<Arc<ActorMap>>> = Lazy::new(|| {
    let load = || -> Result<ActorMap> {
        if let Byml::Hash(hash) = Byml::from_binary(&decompress(fs::read(util::get_game_file(
            "Actor/ActorInfo.product.sbyml",
        )?)?)?)? {
            hash.get("Actors")
                .ok_or_else(|| anyhow::anyhow!("Stock actor info missing Actors list."))?
                .as_array()?
                .iter()
                .map(|actor| -> Result<(u32, Byml)> {
                    Ok((
                        roead::aamp::hash_name(actor.as_hash()?["name"].as_string()?),
                        actor.clone(),
                    ))
                })
                .collect::<Result<ActorMap>>()
        } else {
            anyhow::bail!("Stock actor info is not a hash???")
        }
    };
    load().map(Arc::new)
});

pub fn actorinfo_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let actorinfo_module = PyModule::new(py, "actorinfo")?;
    actorinfo_module.add_wrapped(wrap_pyfunction!(diff_actorinfo))?;
    actorinfo_module.add_wrapped(wrap_pyfunction!(merge_actorinfo))?;
    parent.add_submodule(actorinfo_module)?;
    Ok(())
}

fn stock_actorinfo() -> Result<Arc<ActorMap>> {
    Ok(STOCK_ACTORINFO
        .as_ref()
        .map_err(|e| anyhow::format_err!("{:?}", e))
        .context("Failed to parse stock actor info.")?
        .clone())
}

pub fn merge_actormap(base: &mut ActorMap, other: &ActorMap) {
    other.iter().for_each(|(k, v)| {
        if let Some(bv) = base.get_mut(k) {
            match (bv, v) {
                (roead::byml::Byml::Hash(bh), roead::byml::Byml::Hash(oh)) => {
                    util::merge_map(bh, oh, false);
                }
                _ => {
                    base.insert(*k, v.clone());
                }
            }
        } else {
            base.insert(*k, v.clone());
        }
    })
}

#[pyfunction]
fn diff_actorinfo(py: Python, actorinfo_path: String) -> PyResult<PyObject> {
    let diff = py.allow_threads(|| -> Result<Vec<u8>> {
        if let Byml::Hash(mod_actorinfo) =
            Byml::from_binary(&decompress(&fs::read(&actorinfo_path)?)?)?
        {
            let stock_actorinfo = stock_actorinfo()?;
            let diff: Hash = mod_actorinfo
                .get("Actors")
                .ok_or_else(|| anyhow::format_err!("Modded actor info missing Actors data"))?
                .as_array()?
                .par_iter()
                .filter_map(|actor| -> Option<(smartstring::alias::String, Byml)> {
                    actor.as_hash().ok().and_then(|actor_hash| {
                        let name = actor_hash.get("name")?.as_string().ok()?;
                        let hash = roead::aamp::hash_name(name);
                        if !stock_actorinfo.contains_key(&hash) {
                            Some((hash.to_string().into(), actor.clone()))
                        } else if let Some(Byml::Hash(stock_actor)) = stock_actorinfo.get(&hash)
                            && stock_actor != actor_hash
                        {
                            Some((
                                hash.to_string().into(),
                                Byml::Hash(
                                    actor_hash
                                        .iter()
                                        .filter_map(|(k, v)| {
                                            (stock_actor.get(k) != Some(v))
                                                .then(|| (k.clone(), v.clone()))
                                        })
                                        .collect(),
                                ),
                            ))
                        } else {
                            None
                        }
                    })
                })
                .collect();
            Ok(Byml::Hash(diff).to_text()?.as_bytes().to_vec())
        } else {
            anyhow::bail!("Modded actor info is not a hash???")
        }
    })?;
    Ok(PyBytes::new(py, &diff).into())
}

#[pyfunction]
fn merge_actorinfo(py: Python, modded_actors: Vec<u8>) -> PyResult<()> {
    let merge = || -> Result<()> {
        let modded_actor_root = Byml::from_binary(&modded_actors)?;
        let modded_actors: ActorMap = py.allow_threads(|| -> Result<ActorMap> {
            modded_actor_root
                .as_hash()?
                .into_par_iter()
                .map(|(h, a)| Ok((h.parse::<u32>()?, a.clone())))
                .collect()
        })?;
        let mut merged_actors = stock_actorinfo()?.as_ref().clone();
        merge_actormap(&mut merged_actors, &modded_actors);
        let (hashes, actors): (Vec<Byml>, Vec<Byml>) = merged_actors
            .into_iter()
            .map(|(hash, actor)| {
                (
                    if hash < 2147483648 {
                        Byml::I32(hash as i32)
                    } else {
                        Byml::U32(hash)
                    },
                    actor,
                )
            })
            .unzip();
        let merged_actorinfo = Byml::Hash(
            [
                ("Actors".into(), Byml::Array(actors)),
                ("Hashes".into(), Byml::Array(hashes)),
            ]
            .into_iter()
            .collect(),
        );
        let output = util::settings()
            .master_content_dir()
            .join("Actor/ActorInfo.product.sbyml");
        if !output.parent().expect("No parent folder?!?!?").exists() {
            fs::create_dir_all(output.parent().expect("No parent folder?!?!?"))?;
        }
        fs::write(
            output,
            compress(merged_actorinfo.to_binary(util::settings().endian())),
        )?;
        Ok(())
    };
    Ok(merge()?)
}
