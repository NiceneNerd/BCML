use crate::{Result, RustError};
use jstr::jstr;
use path_slash::PathExt;
use roead::sarc::Sarc;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::{Arc, Mutex, MutexGuard},
};

pub use botw_utils::*;

lazy_static::lazy_static! {
    pub static ref HASH_TABLE_WIIU: hashes::StockHashTable = hashes::StockHashTable::new(&hashes::Platform::WiiU);
    pub static ref HASH_TABLE_SWITCH: hashes::StockHashTable = hashes::StockHashTable::new(&hashes::Platform::Switch);
    static ref STOCK_PACKS: Mutex<HashMap<PathBuf, Arc<Sarc<'static>>>> = Mutex::new(HashMap::new());
}

pub fn settings() -> MutexGuard<'static, crate::settings::Settings> {
    crate::settings::SETTINGS.lock().unwrap()
}

#[inline]
pub fn is_file_modded(canon: &str, data: &[u8]) -> bool {
    if settings().wiiu {
        HASH_TABLE_WIIU.is_file_modded(canon, data, true)
    } else {
        HASH_TABLE_SWITCH.is_file_modded(canon, data, true)
    }
}

#[inline]
pub fn content() -> &'static str {
    if settings().wiiu {
        "content"
    } else {
        "01007EF00011E000/romfs"
    }
}

#[inline]
pub fn dlc() -> &'static str {
    if settings().wiiu {
        "aoc/0010"
    } else {
        "01007EF00011F001/romfs"
    }
}

pub fn get_game_file<P: AsRef<Path>>(file: P) -> Result<PathBuf> {
    let aoc = file
        .as_ref()
        .to_str()
        .map(|f| f.contains(dlc()) || f.contains("aoc"))
        .unwrap_or_default();
    let file = strip_rom_prefixes(&file);
    if aoc {
        get_aoc_game_file(file)
    } else {
        let mut result;
        if settings().wiiu {
            result = settings().update_dir.join(file);
            if result.exists() {
                return Ok(result);
            }
        }
        result = settings().base_game_dir().join(file);
        if result.exists() {
            Ok(result)
        } else {
            Err(RustError::FileNotFoundError(file.to_slash_lossy()))
        }
    }
}

pub fn get_aoc_game_file<P: AsRef<Path>>(file: P) -> Result<PathBuf> {
    let result = settings().dlc_dir().map(|d| d.join(file.as_ref()));
    if result.as_ref().map(|d| d.exists()).unwrap_or_default() {
        Ok(result.unwrap())
    } else {
        Err(RustError::FileNotFoundError(file.as_ref().to_slash_lossy()))
    }
}

pub fn get_stock_pack(pack: &str) -> Result<Arc<Sarc<'static>>> {
    let pack_path = get_aoc_game_file(&jstr!("Pack/{pack}.pack"))
        .or_else(|_| get_game_file(&jstr!("Pack/{pack}.pack")))?;
    let mut stock_packs = STOCK_PACKS.lock().unwrap();
    if let Some(pack) = stock_packs.get(&pack_path) {
        Ok(pack.clone())
    } else {
        let data = std::fs::read(&pack_path)?;
        stock_packs.insert(pack_path, Arc::new(Sarc::read(data)?));
        drop(stock_packs);
        get_stock_pack(pack)
    }
}

const ROM_PREFIXES: &[&str] = &[
    "content",
    "romfs",
    "aoc",
    "0010",
    "01007ef00011e000",
    "01007ef00011e001",
    "01007ef00011e002",
    "01007ef00011f001",
    "01007ef00011f002",
    "01007EF00011E000",
    "01007EF00011E001",
    "01007EF00011E002",
    "01007EF00011F001",
    "01007EF00011F002",
];

fn strip_rom_prefixes<P: AsRef<Path> + ?Sized>(file: &P) -> &Path {
    let mut file = file.as_ref();
    loop {
        let mut matched = false;
        for prefix in ROM_PREFIXES {
            match file.strip_prefix(prefix) {
                Ok(stripped) => {
                    file = stripped;
                    matched = true;
                }
                Err(_) => continue,
            }
        }
        if !matched {
            break;
        }
    }
    file
}
