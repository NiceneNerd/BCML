use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, PartialEq, Eq, Clone, Copy, Hash, Serialize, Deserialize)]
pub enum Language {
    USen = "USen",
    EUen,
    USfr,
    USes,
    EUde,
    EUes,
    EUfr,
    EUit,
    EUnl,
    EUru,
    CNzh,
    JPja,
    KRko,
    TWzh,
}

#[derive(Debug, PartialEq, Clone, Hash, Serialize, Deserialize)]
pub struct Settings {
    cemu_dir: PathBuf,
    game_dir: PathBuf,
    game_dir_nx: PathBuf,
    update_dir: PathBuf,
    dlc_dir: PathBuf,
    dlc_dir_nx: PathBuf,
    store_dir: PathBuf,
    export_dir: PathBuf,
    export_dir_nx: PathBuf,
    load_reverse: bool,
    site_meta: PathBuf,
    dark_theme: bool,
    no_guess: bool,
    lang: Language,
    no_cemu: bool,
    wiiu: bool,
    no_hardlinks: bool,
    force_7z: bool,
    suppress_update: bool,
    nsfw: bool,
    last_version: String,
    changelog: bool,
    strip_gfx: bool,
    auto_gb: bool,
    show_gb: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            store_dir: if cfg!(windows) {
                dirs2::data_local_dir().unwrap()
            } else {
                dirs2::config_dir().unwrap()
            }
            .join("bcml"),
            lang: Language::USen,
            last_version: env!("CARGO_PKG_VERSION"),
            changelog: true,
            wiiu: true,
            auto_gb: true,
            ..Default::default()
        }
    }
}

impl std::fmt::Display for Language {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(&self, f)
    }
}
