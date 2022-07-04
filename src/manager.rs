use crate::{util, Result};
use anyhow::Context;
use fs_err as fs;
use join_str::jstr;
#[cfg(windows)]
use mslnk::ShellLink;
use pyo3::prelude::*;
use rayon::prelude::*;
#[cfg(windows)]
use remove_dir_all::remove_dir_all;
#[cfg(not(windows))]
use std::fs::remove_dir_all;
use std::path::PathBuf;

pub fn manager_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let manager_module = PyModule::new(py, "manager")?;
    #[cfg(windows)]
    manager_module.add_wrapped(wrap_pyfunction!(create_shortcut))?;
    manager_module.add_wrapped(wrap_pyfunction!(link_master_mod))?;
    parent.add_submodule(manager_module)?;
    Ok(())
}

#[cfg(windows)]
#[pyfunction]
fn create_shortcut(_py: Python, py_path: String, ico_path: String, dest: String) -> PyResult<()> {
    let make = || -> anyhow::Result<()> {
        let mut link = ShellLink::new(&py_path)?;
        link.set_arguments(Some("-m bcml".into()));
        link.set_name(Some("BCML".into()));
        link.set_icon_location(Some(ico_path));
        fs::create_dir_all(std::path::Path::new(&dest).parent().unwrap())?;
        link.create_lnk(&dest)?;
        Ok(())
    };
    Ok(make()?)
}

#[pyfunction]
fn link_master_mod(py: Python, output: Option<String>) -> PyResult<()> {
    if let Some(output) = output
        .map(PathBuf::from)
        .or_else(|| util::settings().export_dir().map(|o| o.to_path_buf()))
    {
        let merged = util::settings().merged_modpack_dir();
        if merged.exists() {
            remove_dir_all(&merged).context("Failed to clear internal merged folder")?;
        }
        fs::create_dir_all(&merged).context("Failed to create internal merged folder")?;
        let rules_path = merged.join("rules.txt");
        if !util::settings().no_cemu && !rules_path.exists() {
            fs::hard_link(
                util::settings().master_mod_dir().join("rules.txt"),
                rules_path,
            )
            .context("Failed to hard link rules.txt")?;
        }
        let mod_folders: Vec<PathBuf> =
            glob::glob(&util::settings().mods_dir().join("*").to_string_lossy())
                .unwrap()
                .filter_map(|p| p.ok())
                .filter(|p| p.is_dir() && !p.join(".disabled").exists())
                .collect::<std::collections::BTreeSet<PathBuf>>()
                .into_iter()
                .flat_map(|p| {
                    let glob_str = p.join("options/*").display().to_string();
                    [p].into_iter()
                        .chain(
                            glob::glob(&glob_str)
                                .unwrap()
                                .filter_map(|p| p.ok())
                                .filter(|p| p.is_dir()),
                        )
                        .collect::<Vec<PathBuf>>()
                })
                .collect();
        dbg!(&mod_folders);
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
                                    || item.extension().and_then(|e| e.to_str()) == Some("json")
                                    || rel.starts_with("logs")
                                    || rel.starts_with("options")
                                    || rel.starts_with("meta")
                                    || (rel.ancestors().count() == 1
                                        && rel.extension().and_then(|e| e.to_str())
                                            != Some("txt")
                                        && !item.is_dir()))
                            })
                            .collect();
                    mod_files
                        .into_par_iter()
                        .try_for_each(|(item, rel)| -> Result<()> {
                            let out = merged.join(&rel);
                            out.parent()
                                .map(fs::create_dir_all)
                                .transpose()
                                .with_context(|| jstr!("Failed to create parent folder for file {rel.to_str().unwrap()}"))?
                                .unwrap();
                            fs::hard_link(item, &out)
                                .with_context(|| jstr!("Failed to hard link {rel.to_str().unwrap()} to {out.to_str().unwrap()}"))?;
                            Ok(())
                        })?;
                    Ok(())
                })
        })?;
        if output.is_dir() {
            println!("Clearing output folder at {}", output.display());
            remove_dir_all(&output).context("Failed to clear out output folder")?;
        }
        if !output.exists() {
            fs::create_dir_all(output.parent().unwrap())
                .context("Failed to prepare parent of output directory")?;
            if util::settings().no_hardlinks {
                dircpy::copy_dir(merged, &output).context("Failed to copy output folder")?;
            } else {
                #[cfg(target_os = "linux")]
                std::os::unix::fs::symlink(merged, &output)
                    .context("Failed to symlink output folder")?;
                #[cfg(target_os = "windows")]
                junction::create(merged, &output)
                    .context("Failed to create output directory junction")?;
            }
        }
        if glob::glob(&output.join("*").to_string_lossy())
            .unwrap()
            .filter_map(|p| p.ok())
            .count()
            == 0
        {
            return Err(anyhow::anyhow!("Output folder is empty").into());
        }
    }
    Ok(())
}
