use crate::{util, Result};
use pyo3::prelude::*;
use rayon::prelude::*;
use std::path::PathBuf;

pub fn manager_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let manager_module = PyModule::new(py, "manager")?;
    manager_module.add_wrapped(wrap_pyfunction!(link_master_mod))?;
    parent.add_submodule(manager_module)?;
    Ok(())
}

#[pyfunction]
fn link_master_mod(py: Python, output: Option<String>) -> PyResult<()> {
    if let Some(output) = output
        .map(PathBuf::from)
        .or_else(|| util::settings().export_dir().map(|o| o.to_path_buf()))
    {
        let merged = util::settings().merged_modpack_dir();
        #[allow(unused_must_use)]
        if merged.exists() {
            std::fs::remove_dir_all(merged.join(util::content()));
            std::fs::remove_dir_all(merged.join(util::dlc()));
        }
        std::fs::create_dir_all(&merged).unwrap_or(());
        let rules_path = merged.join("rules.txt");
        if !util::settings().no_cemu && !rules_path.exists() {
            std::fs::hard_link(
                util::settings().master_mod_dir().join("rules.txt"),
                rules_path,
            )?;
        }
        let mod_folders: std::collections::BTreeSet<PathBuf> =
            glob::glob(&util::settings().mods_dir().join("*").to_string_lossy())
                .unwrap()
                .filter_map(|p| p.ok())
                .filter(|p| p.is_dir() && !p.join(".disabled").exists())
                .collect();
        py.allow_threads(|| -> Result<()> {
            mod_folders
                .into_iter()
                .rev()
                .try_for_each(|folder| -> Result<()> {
                    let mod_files: Vec<(PathBuf, PathBuf)> =
                        glob::glob(&folder.join("**/*").to_string_lossy())
                            .unwrap()
                            .filter_map(|p| {
                                p.ok().map(|p| {
                                    (p.clone(), p.strip_prefix(&folder).unwrap().to_owned())
                                })
                            })
                            .filter(|(item, rel)| {
                                !(merged.join(&rel).exists()
                                    || item.is_dir()
                                    || rel.starts_with("logs")
                                    || rel.starts_with("options")
                                    || rel.starts_with("meta")
                                    || (rel.ancestors().count() == 1
                                        && rel.extension() != Some(std::ffi::OsStr::new("txt"))
                                        && !item.is_dir()))
                            })
                            .collect();
                    mod_files
                        .into_par_iter()
                        .try_for_each(|(item, rel)| -> Result<()> {
                            let out = merged.join(&rel);
                            out.parent().map(std::fs::create_dir_all);
                            std::fs::hard_link(item, out)?;
                            Ok(())
                        })?;
                    Ok(())
                })
        })?;
        if output.is_dir() {
            std::fs::remove_dir_all(&output)?;
        }
        if !output.exists() {
            #[cfg(target_os = "linux")]
            std::os::unix::fs::symlink(merged, &output)?;
            #[cfg(target_os = "windows")]
            junction::create(merged, &output)?;
        }
        assert!(
            glob::glob(&output.join("*").to_string_lossy())
                .unwrap()
                .filter_map(|p| p.ok())
                .count()
                > 0
        )
    }
    Ok(())
}
