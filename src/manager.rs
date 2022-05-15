use crate::{util, Result, RustError};
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
        if output.exists() {
            if !util::settings().no_cemu {
                std::fs::remove_dir_all(&output)?;
            } else {
                #[allow(unused_must_use)]
                {
                    std::fs::remove_dir_all(output.join(util::content()));
                    std::fs::remove_dir_all(output.join(util::dlc()));
                }
            }
        }
        std::fs::create_dir_all(&output)?;
        if !util::settings().no_cemu {
            std::fs::copy(
                util::settings().master_mod_dir().join("rules.txt"),
                output.join("rules.txt"),
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
                                !(output.join(&rel).exists()
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
                            let out = output.join(&rel);
                            out.parent().map(std::fs::create_dir_all).transpose()?;
                            // std::fs::hard_link(item, out)?;
                            #[cfg(target_family = "windows")]
                            std::os::windows::fs::symlink_file(item, out)?;
                            #[cfg(target_family = "unix")]
                            std::os::unix::fs::symlink(item, out)?;
                            Ok(())
                        })?;
                    Ok(())
                })
        })?;
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
