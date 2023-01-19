use anyhow::{Context, Result};
use fs_err as fs;
use indexmap::IndexMap;
use join_str::jstr;
use msyt::{model::Entry, Msyt};
use pyo3::prelude::*;
use rayon::prelude::*;
use roead::{
    sarc::{Sarc, SarcWriter},
    yaz0::{compress, decompress},
};
use std::path::Path;

type Diff = IndexMap<String, Entry>;

pub fn texts_mod(py: Python, parent: &PyModule) -> PyResult<()> {
    let texts_module = PyModule::new(py, "texts")?;
    texts_module.add_wrapped(wrap_pyfunction!(diff_language))?;
    texts_module.add_wrapped(wrap_pyfunction!(merge_language))?;
    parent.add_submodule(texts_module)?;
    Ok(())
}

#[pyfunction]
pub fn diff_language(
    py: Python,
    mod_bootup_path: String,
    stock_bootup_path: String,
    only_new_keys: bool,
) -> PyResult<PyObject> {
    let diff = py.allow_threads(|| -> Result<IndexMap<String, Diff>> {
        let language = &Path::new(&mod_bootup_path)
            .file_stem()
            .expect("Okay, how does this path have no name?")
            .to_str()
            .expect("And this should definitely work, too")[7..];
        let mod_bootup = Sarc::new(fs::read(&mod_bootup_path)?)?;
        let stock_bootup = Sarc::new(fs::read(&stock_bootup_path)?)?;
        let message_path = jstr!("Message/Msg_{&language}.product.ssarc");
        let mod_message = Sarc::new(decompress(
            mod_bootup
                .get_data(&message_path)
                .with_context(|| {
                    jstr!("Failed to read {&message_path} from Bootup_{language}.pack")
                })?,
        )?)?;
        let stock_message = Sarc::new(decompress(
            stock_bootup
                .get_data(&message_path)
                .with_context(|| {
                    jstr!("Failed to read {&message_path} from Bootup_{language}.pack")
                })?,
        )?)?;
        let diffs = mod_message
            .files()
            .filter(|file| {
                file.name()
                    .map(|name| name.ends_with("msbt"))
                    .unwrap_or(false)
            })
            .par_bridge()
            .map(|file| -> Result<Option<(String, Diff)>> {
                if let Some(path) = file.name().map(std::borrow::ToOwned::to_owned) {
                    let mod_text = Msyt::from_msbt_bytes(file.data())
                        .with_context(|| jstr!("Invalid MSBT file: {&path}"))?;
                    if let Some(stock_text) = stock_message
                        .get_data(&path)
                        .and_then(|data| Msyt::from_msbt_bytes(data).ok())
                    {
                        if mod_text == stock_text {
                            Ok(None)
                        } else {
                            let diffs: Diff = mod_text
                                .entries
                                .iter()
                                .filter(|(e, t)| {
                                    if only_new_keys {
                                        !stock_text.entries.contains_key(*e)
                                    } else {
                                        stock_text.entries.get(*e) != Some(t)
                                    }
                                })
                                .map(|(e, t)| (e.to_owned(), t.clone()))
                                .collect();
                            if diffs.is_empty() {
                                Ok(None)
                            } else {
                                Ok(Some((path.replace("msbt", "msyt"), diffs)))
                            }
                        }
                    } else {
                        Ok(Some((path.replace("msbt", "msyt"), mod_text.entries)))
                    }
                } else {
                    Ok(None)
                }
            })
            .collect::<Result<Vec<Option<(String, Diff)>>>>()?
            .into_iter()
            .flatten()
            .collect();
        Ok(diffs)
    })?;
    let diff_text =
        serde_json::to_string(&diff).expect("It's whack if this diff doesn't serialize");
    let json = PyModule::import(py, "json")?;
    #[allow(deprecated)]
    let dict = json.call_method1("loads", (&diff_text,))?;
    Ok(Py::from(dict))
}

#[pyfunction]
pub fn merge_language(
    py: Python,
    diffs: String,
    stock_bootup_path: String,
    dest_bootup_path: String,
    be: bool,
) -> PyResult<()> {
    let diffs: IndexMap<String, Diff> =
        serde_json::from_str(&diffs).map_err(anyhow::Error::from)?;
    let endian = if be {
        msyt::Endianness::Big
    } else {
        msyt::Endianness::Little
    };
    py.allow_threads(|| -> Result<()> {
        let language = &Path::new(&stock_bootup_path)
            .file_stem()
            .expect("Okay, how does this path have no name?")
            .to_str()
            .expect("And this should definitely work, too")[7..];
        let stock_bootup = Sarc::new(fs::read(&stock_bootup_path)?)?;
        let message_path = format!("Message/Msg_{}.product.ssarc", &language);
        let stock_message = Sarc::new(decompress(
            stock_bootup
                .get_data(&message_path)
                .with_context(|| {
                    jstr!("Failed to read {&message_path} from Bootup_{language}.pack")
                })?,
        )?)?;
        let mut new_message = SarcWriter::from(&stock_message);
        let merged_files = diffs
            .into_par_iter()
            .map(|(file, diff)| -> Result<(String, Vec<u8>)> {
                let file = file.replace("msyt", "msbt");
                if let Some(stock_file) = stock_message.get_data(&file) {
                    let mut stock_text = Msyt::from_msbt_bytes(stock_file)?;
                    stock_text.entries.extend(diff.into_iter());
                    Ok((file, stock_text.into_msbt_bytes(endian)?))
                } else {
                    let text = Msyt {
                        msbt: msyt::model::MsbtInfo {
                            group_count: diff.len() as u32,
                            atr1_unknown: Some(if file.contains("EventFlowMsg") { 0 } else { 4 }),
                            ato1: None,
                            tsy1: None,
                            nli1: None,
                        },
                        entries: diff,
                    };
                    Ok((file, text.into_msbt_bytes(endian)?))
                }
            })
            .collect::<Result<Vec<(String, Vec<u8>)>>>()?;
        new_message.add_files(merged_files.into_iter());
        let mut new_bootup = SarcWriter::new(if be {
            roead::Endian::Big
        } else {
            roead::Endian::Little
        });
        new_bootup.add_file(&message_path, compress(new_message.to_binary()).as_slice());
        fs::create_dir_all(&dest_bootup_path[..dest_bootup_path.len() - 17])?;
        fs::write(&dest_bootup_path, new_bootup.to_binary())?;
        Ok(())
    })?;
    Ok(())
}
