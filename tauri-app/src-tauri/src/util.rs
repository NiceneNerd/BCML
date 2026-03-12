use anyhow::Result;
use join_str::jstr;
use once_cell::sync::Lazy;
use parking_lot::{Mutex, RwLockReadGuard};
use roead::sarc::Sarc;
pub use rustc_hash::{FxHashMap as HashMap, FxHashSet as HashSet};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};

pub use botw_utils::*;

pub static HASH_TABLE_WIIU: Lazy<hashes::StockHashTable> =
    Lazy::new(|| hashes::StockHashTable::new(&hashes::Platform::WiiU));
pub static HASH_TABLE_SWITCH: Lazy<hashes::StockHashTable> =
    Lazy::new(|| hashes::StockHashTable::new(&hashes::Platform::Switch));
static STOCK_PACKS: Lazy<Mutex<HashMap<PathBuf, Arc<Sarc<'static>>>>> =
    Lazy::new(|| Mutex::new(HashMap::default()));

#[inline(always)]
pub fn settings() -> RwLockReadGuard<'static, crate::settings::Settings> {
    if crate::settings::Settings::tmp_path().exists() {
        crate::settings::TMP_SETTINGS.read()
    } else {
        crate::settings::SETTINGS.read()
    }
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
        let mut result = settings().main_game_dir().join(file);
        if result.exists() {
            Ok(result)
        } else {
            result = settings().base_game_dir().join(file);
            if result.exists() {
                Ok(result)
            } else {
                anyhow::bail!("Stock game file does not exist at {}", result.display())
            }
        }
    }
}

pub fn get_aoc_game_file<P: AsRef<Path>>(file: P) -> Result<PathBuf> {
    let result = settings().dlc_dir().map(|d| d.join(file.as_ref()));
    if result.as_ref().map(|d| d.exists()).unwrap_or_default() {
        Ok(unsafe { result.unwrap_unchecked() })
    } else {
        anyhow::bail!("Stock DLC game file does not exist at {:?}", result)
    }
}

pub fn get_stock_pack(pack: &str) -> Result<Arc<Sarc<'static>>> {
    let pack_path = get_aoc_game_file(&jstr!("Pack/{pack}.pack"))
        .or_else(|_| get_game_file(&jstr!("Pack/{pack}.pack")))?;
    let mut stock_packs = STOCK_PACKS.lock();
    if let Some(pack) = stock_packs.get(&pack_path) {
        Ok(pack.clone())
    } else {
        let data = fs_err::read(&pack_path)?;
        stock_packs.insert(pack_path, Arc::new(Sarc::new(data)?));
        drop(stock_packs);
        get_stock_pack(pack)
    }
}

pub fn merge_map(base: &mut roead::byml::Hash, other: &roead::byml::Hash, extend: bool) {
    other.iter().for_each(|(k, v)| {
        if let Some(bv) = base.get_mut(k) {
            match (bv, v) {
                (roead::byml::Byml::Hash(bh), roead::byml::Byml::Hash(oh)) => {
                    merge_map(bh, oh, extend);
                }
                (roead::byml::Byml::Array(ba), roead::byml::Byml::Array(oa)) => {
                    if extend {
                        ba.extend(oa.iter().cloned());
                    } else {
                        base.insert(k.clone(), v.clone());
                    }
                }
                _ => {
                    base.insert(k.clone(), v.clone());
                }
            }
        } else {
            base.insert(k.clone(), v.clone());
        }
    })
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
