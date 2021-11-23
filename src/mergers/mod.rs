use pyo3::prelude::*;
pub mod texts;

pub fn mergers_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let mergers_module = PyModule::new(py, "mergers")?;
    texts::texts_mod(py, mergers_module)?;
    parent.add_submodule(mergers_module)?;
    Ok(())
}
