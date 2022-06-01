pub mod pack;
use pyo3::prelude::*;
pub mod actorinfo;
pub mod maps;
pub mod texts;

pub fn mergers_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let mergers_module = PyModule::new(py, "mergers")?;
    actorinfo::actorinfo_mod(py, mergers_module)?;
    texts::texts_mod(py, mergers_module)?;
    maps::maps_mod(py, mergers_module)?;
    pack::packs_mod(py, mergers_module)?;
    parent.add_submodule(mergers_module)?;
    Ok(())
}
