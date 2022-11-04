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

static RULES_TXT: &str = r#"[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = BCML
path = The Legend of Zelda: Breath of the Wild/Mods/BCML
description = Complete pack of mods merged using BCML
version = 7
default = true
fsPriority = 9999
"#;

#[cfg(windows)]
#[inline]
fn win_symlink(target: &std::path::Path, link: &std::path::Path) -> Result<()> {
    match junction::create(target, link) {
        Ok(()) => Ok(()),
        Err(_) => {
            let arg_list = format!(
                "Start-Process -FilePath cmd -ArgumentList '/c,mklink,/d,\"{}\",\"{}\"' -Verb RunAs",
                link.to_str().unwrap(),
                target.to_str().unwrap()
            );
            std::process::Command::new("powershell")
                .arg(arg_list)
                .status()
                .expect("Failed to spawn mklink process");
            Ok(())
        }
    }
}

#[pyfunction]
fn link_master_mod(py: Python, output: Option<String>) -> PyResult<()> {
    if let Some(output) = output
        .map(PathBuf::from)
        .or_else(|| util::settings().export_dir())
    {
        let settings = util::settings();
        let merged = settings.merged_modpack_dir();
        if merged.exists() {
            remove_dir_all(&merged).context("Failed to clear internal merged folder")?;
        }
        fs::create_dir_all(&merged).context("Failed to create internal merged folder")?;
        let needs_rules = !settings.no_cemu && settings.wiiu;
        let rules_path = merged.join("rules.txt");
        if needs_rules && !rules_path.exists() {
            // Since for some incomprehensible reason hard-linking this from
            // the master folder randomly doesn't work, we'll just write it
            // straight to the merged folder.
            fs::write(&rules_path, RULES_TXT).context("Failed to write rules.txt")?;
        }
        let mod_folders: Vec<PathBuf> =
            glob::glob(&settings.mods_dir().join("*").to_string_lossy())
                .unwrap()
                .filter_map(|p| p.ok())
                .filter(|p| p.is_dir() && !p.join(".disabled").exists())
                .collect::<std::collections::BTreeSet<PathBuf>>()
                .into_iter()
                .flat_map(|p| {
                    let glob_str = p.join("options/*").display().to_string();
                    std::iter::once(p)
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
                                !(merged.join(rel).exists()
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
                            fs::hard_link(&item, &out)
                                .with_context(|| jstr!("Failed to hard link {rel.to_str().unwrap()} to {out.to_str().unwrap()}"))
                                .or_else(|_| {
                                    eprintln!("Failed to hard link {} to {}", rel.display(), out.display());
                                    fs::copy(item, &out)
                                        .with_context(|| jstr!("Failed to copy {rel.to_str().unwrap()} to {out.to_str().unwrap()}"))
                                        .map(|_| ())
                                })?;
                            Ok(())
                        })?;
                    Ok(())
                })
        })?;
        let exists = output.exists();
        let is_link = {
            #[cfg(windows)]
            {
                junction::exists(&output).unwrap_or(false)
                    || output.is_symlink()
                    || !output.is_dir()
            }
            #[cfg(unix)]
            {
                output.is_symlink() || !output.is_dir()
            }
        };
        let should_be_link = !settings.no_hardlinks;
        // Only if the output folder exists and is a symlink and is supposed to
        // be a symlink, we're done. If it is a real folder, or it is a link
        // when it should be a real folder, or it doesn't exist, we must proceed
        // to set up the output folder.
        if !(exists && is_link && should_be_link) {
            println!("Preparing output folder at {}", output.display());
            if should_be_link {
                if !is_link && exists {
                    // If `no_hard_links` is not enabled, then this existing folder
                    // is probably leftover from someone upgrading or changing
                    // their hard link setting, in which case we should remove the
                    // output folder entirely to make way for the new link.
                    remove_dir_all(&output).context("Failed to clear output folder")?;
                }
                #[cfg(target_os = "linux")]
                std::os::unix::fs::symlink(merged, &output)
                    .context("Failed to symlink output folder")?;
                #[cfg(target_os = "windows")]
                win_symlink(&merged, &output).context("Failed to link output folder")?;
            } else {
                // If there is already a linked folder (e.g. after settings change),
                // then we should remove it.
                if exists && is_link {
                    #[cfg(windows)]
                    junction::delete(&output)
                        .or_else(|_| fs::remove_file(&output))
                        .or_else(|_| fs::remove_dir(&output))
                        .context("Failed to remove output folder link")?;
                    #[cfg(unix)]
                    fs::remove_file(&output)
                        .or_else(|_| fs::remove_dir(&output))
                        .context("Failed to remove output folder link")?;
                }
                if !exists {
                    fs::create_dir_all(&output).context("Failed to create output folder")?;
                }
                // If `no_hard_links` is enabled, then we can save some trouble by
                // only clearing actual mod content instead of the whole output
                // folder. Among other benefits, this lets us keep mods for other
                // games when the output folder is `/atmosphere/contents` and
                // reduces the risk of accidentally deleting whatever else when
                // people set their output folders badly.
                let (content, dlc) = (util::content(), util::dlc());
                let (merged_content, out_content) = (merged.join(content), output.join(content));
                let (merged_dlc, out_dlc) = (merged.join(dlc), output.join(dlc));
                if out_content.exists() {
                    remove_dir_all(&out_content)
                        .context("Failed to clear output content folder")?;
                }
                if merged_content.exists() {
                    dircpy::copy_dir(&merged_content, &out_content)
                        .context("Failed to copy output content folder")?;
                }
                if out_dlc.exists() {
                    remove_dir_all(&out_dlc).context("Failed to clear output DLC folder")?;
                }
                if merged_dlc.exists() {
                    dircpy::copy_dir(&merged_dlc, &out_dlc)
                        .context("Failed to copy output DLC folder")?;
                }
                if needs_rules {
                    fs::copy(&rules_path, output.join("rules.txt"))?;
                    // For Waikuteru's, and other mods that contain Cemu code patches
                    let (merged_patches, out_patches) =
                        (merged.join("patches"), output.join("patches"));
                    if out_patches.exists() {
                        remove_dir_all(&out_patches)
                            .context("Failed to clear output patches folder")?;
                    }
                    if merged_patches.exists() {
                        dircpy::copy_dir(&merged_patches, &out_patches)
                            .context("Failed to copy output patches folder")?;
                    }
                }
            }
        }
        if glob::glob(&output.join("*").to_string_lossy())
            .unwrap()
            .filter_map(|p| p.ok())
            .count()
            == 0
            && std::fs::read_dir(settings.mods_dir()).unwrap().count() > 1
        {
            return Err(anyhow::anyhow!("Output folder is empty").into());
        }
    }
    Ok(())
}
