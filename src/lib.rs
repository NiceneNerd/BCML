#![feature(let_chains)]
pub mod manager;
pub mod mergers;
pub mod settings;
pub mod util;
use cow_utils::CowUtils;
use path_slash::{PathBufExt, PathExt};
use pyo3::{exceptions::PyException, prelude::*};
use rayon::prelude::*;
use roead::sarc::Sarc;
use std::{
    borrow::Cow,
    path::{Path, PathBuf},
};
use thiserror::Error;

pub type Result<T> = std::result::Result<T, RustError>;

#[derive(Debug, Error)]
pub enum RustError {
    #[error("File not found: {0}")]
    FileNotFoundError(String),
    #[error(transparent)]
    BymlError(#[from] roead::byml::BymlError),
    #[error(transparent)]
    AampError(#[from] roead::aamp::AampError),
    #[error(transparent)]
    SarcError(#[from] roead::sarc::SarcError),
    #[error(transparent)]
    Yaz0Error(#[from] roead::yaz0::Yaz0Error),
    #[error(transparent)]
    IoError(#[from] std::io::Error),
    #[error("SARC missing expected file: {0}")]
    FileMissingFromSarc(String),
    #[error("Error handling MSBT file: {0}")]
    MsbtError(String),
    #[error(transparent)]
    JsonError(#[from] serde_json::Error),
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl From<RustError> for PyErr {
    fn from(err: RustError) -> Self {
        PyException::new_err(err.to_string())
    }
}

#[pymodule]
fn bcml(py: Python, m: &PyModule) -> PyResult<()> {
    mergers::mergers_mod(py, m)?;
    manager::manager_mod(py, m)?;
    m.add_wrapped(wrap_pyfunction!(find_modified_files))?;
    Ok(())
}

#[pyfunction]
fn find_modified_files(py: Python, mod_dir: String, be: bool) -> PyResult<Vec<String>> {
    println!("Finding modified files...");
    let mod_dir = Path::new(&mod_dir);
    let content = mod_dir.join(util::content());
    let dlc = mod_dir.join(util::dlc());
    let files: Vec<PathBuf> = py.allow_threads(|| {
        glob::glob(mod_dir.join("**/*").to_str().unwrap())
            .unwrap()
            .filter_map(std::result::Result::ok)
            .collect::<Vec<_>>()
            .into_par_iter()
            .filter(|f| {
                f.is_file()
                    && (f.starts_with(&content) || f.starts_with(&dlc))
                    && util::get_canon_name(f.strip_prefix(&mod_dir).unwrap())
                        .and_then(|canon| {
                            std::fs::read(f)
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
                std::fs::metadata(f).unwrap().len() > 4
                    && f.extension()
                        .and_then(|ext| ext.to_str())
                        .map(|ext| botw_utils::extensions::SARC_EXTS.contains(&ext))
                        .unwrap_or(false)
            })
            .map(|file| -> Result<Vec<String>> {
                let sarc = Sarc::read(std::fs::read(file)?)?;
                find_modded_sarc_files(
                    &sarc,
                    file.starts_with(&dlc),
                    be,
                    &file.strip_prefix(&mod_dir).unwrap().to_slash_lossy(),
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

fn find_modded_sarc_files(sarc: &Sarc, aoc: bool, be: bool, path: &str) -> Result<Vec<String>> {
    Ok(sarc
        .files()
        .filter(|f| f.name().is_some())
        .filter(|file| {
            let (f, d) = (file.name_unchecked(), file.data());
            let mut canon = f.cow_replace(".s", ".");
            if aoc {
                canon = Cow::Owned(["Aoc/0010", &canon].join(""));
            }
            util::is_file_modded(&canon, d)
        })
        .map(|file| -> Result<Vec<String>> {
            let (f, d) = (file.name_unchecked(), file.data());
            let mut modded_files: Vec<String> = vec![[path, f].join("//")];
            if !f.ends_with("ssarc")
                && d.len() > 0x40
                && (&d[..4] == b"SARC" || &d[0x11..0x15] == b"SARC")
            {
                let sarc = Sarc::read(d)?;
                modded_files.extend(find_modded_sarc_files(
                    &sarc,
                    aoc,
                    be,
                    modded_files.first().as_ref().unwrap(),
                )?);
            }
            Ok(modded_files)
        })
        .collect::<Result<Vec<Vec<String>>>>()?
        .into_iter()
        .flatten()
        .collect())
}
