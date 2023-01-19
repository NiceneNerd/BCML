#![feature(let_chains)]
#![deny(clippy::unwrap_used)]
pub mod manager;
pub mod mergers;
pub mod settings;
pub mod util;
pub use anyhow::Result;
use cow_utils::CowUtils;
use fs_err as fs;
use path_slash::{PathBufExt, PathExt};
use pyo3::prelude::*;
use rayon::prelude::*;
use roead::sarc::Sarc;
use std::{
    borrow::Cow,
    path::{Path, PathBuf},
};

#[pymodule]
fn bcml(py: Python, m: &PyModule) -> PyResult<()> {
    mergers::mergers_mod(py, m)?;
    manager::manager_mod(py, m)?;
    m.add_wrapped(wrap_pyfunction!(find_modified_files))?;
    m.add_wrapped(wrap_pyfunction!(reload_settings))?;
    Ok(())
}

#[pyfunction]
fn reload_settings() -> PyResult<()> {
    println!("Reloading settings");
    settings::SETTINGS.write().reload()?;
    Ok(())
}

#[pyfunction]
fn find_modified_files(py: Python, mod_dir: String) -> PyResult<Vec<String>> {
    println!("Finding modified files...");
    let mod_dir = Path::new(&mod_dir);
    let content = mod_dir.join(util::content());
    let dlc = mod_dir.join(util::dlc());
    let files: Vec<PathBuf> = py.allow_threads(|| {
        glob::glob(&mod_dir.join("**/*").to_string_lossy())
            .expect("Bad glob?!?!?!")
            .filter_map(std::result::Result::ok)
            .par_bridge()
            .filter(|f| {
                f.is_file()
                    && (f.starts_with(&content) || f.starts_with(&dlc))
                    && util::get_canon_name(unsafe { f.strip_prefix(mod_dir).unwrap_unchecked() })
                        .and_then(|canon| {
                            fs::read(f)
                                .ok()
                                .map(|data| util::is_file_modded(&canon, &data))
                        })
                        .unwrap_or(false)
            })
            .collect()
    });
    println!("Found {} modified files...", files.len());
    let sarc_files: Vec<String> = py.allow_threads(|| -> Result<Vec<String>> {
        Ok(files
            .par_iter()
            .filter(|f| {
                fs::metadata(f).expect("No file metadata!?!?!?!").len() > 4
                    && f.extension()
                        .and_then(|ext| ext.to_str())
                        .map(|ext| botw_utils::extensions::SARC_EXTS.contains(&ext))
                        .unwrap_or(false)
            })
            .map(|file| -> Result<Vec<String>> {
                let sarc = Sarc::new(fs::read(file)?)?;
                find_modded_sarc_files(
                    &sarc,
                    file.starts_with(&dlc),
                    &unsafe { file.strip_prefix(mod_dir).unwrap_unchecked() }.to_slash_lossy(),
                )
            })
            .collect::<Result<Vec<_>>>()?
            .into_par_iter()
            .flatten()
            .collect())
    })?;
    println!("Found {} modified files in SARCs...", sarc_files.len());
    Ok(files
        .into_par_iter()
        .map(|file| file.to_slash_lossy())
        .chain(sarc_files.into_par_iter())
        .collect())
}

fn find_modded_sarc_files(sarc: &Sarc, aoc: bool, path: &str) -> Result<Vec<String>> {
    Ok(sarc
        .files()
        .filter(|f| f.name().is_some())
        .filter(|file| {
            let (f, d) = (file.unwrap_name(), file.data());
            let mut canon = f.cow_replace(".s", ".");
            if aoc {
                canon = Cow::Owned(["Aoc/0010", &canon].join(""));
            }
            util::is_file_modded(&canon, d)
        })
        .map(|file| -> Result<Vec<String>> {
            let (f, d) = (file.unwrap_name(), file.data());
            let mut modded_files: Vec<String> = vec![[path, f].join("//")];
            if !f.ends_with("ssarc")
                && d.len() > 0x40
                && (&d[..4] == b"SARC" || &d[0x11..0x15] == b"SARC")
            {
                let sarc = Sarc::new(d)?;
                modded_files.extend(find_modded_sarc_files(
                    &sarc,
                    aoc,
                    modded_files
                        .first()
                        .as_ref()
                        .expect("What a strange filename"),
                )?);
            }
            Ok(modded_files)
        })
        .collect::<Result<Vec<Vec<String>>>>()?
        .into_iter()
        .flatten()
        .collect())
}
