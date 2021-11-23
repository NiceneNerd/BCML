pub use botw_utils::*;

lazy_static::lazy_static! {
    pub static ref HASH_TABLE_WIIU: hashes::StockHashTable = hashes::StockHashTable::new(&hashes::Platform::WiiU);
    pub static ref HASH_TABLE_SWITCH: hashes::StockHashTable = hashes::StockHashTable::new(&hashes::Platform::Switch);
}

#[inline]
pub fn is_file_modded(canon: &str, data: &[u8], be: bool) -> bool {
    if be {
        HASH_TABLE_WIIU.is_file_modded(canon, data, true)
    } else {
        HASH_TABLE_SWITCH.is_file_modded(canon, data, true)
    }
}

#[inline]
pub fn content(be: bool) -> &'static str {
    if be {
        "content"
    } else {
        "01007EF00011E000/romfs"
    }
}

#[inline]
pub fn dlc(be: bool) -> &'static str {
    if be {
        "aoc/0010"
    } else {
        "01007EF00011F001/romfs"
    }
}
