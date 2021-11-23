use crate::{Result, RustError};
use pyo3::prelude::*;
use rayon::prelude::*;
use roead::{
    byml::Byml,
    sarc::{Sarc, SarcWriter},
    yaz0::{compress, decompress},
};
use std::path::Path;

pub fn maps_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let maps_module = PyModule::new(py, "maps")?;
    parent.add_submodule(maps_module)?;
    Ok(())
}

// #[pyfunction]
// pub fn diff_maps(py: Python, mod_root: String, stock_map_root)
