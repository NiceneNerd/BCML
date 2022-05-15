use crate::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, PartialEq, Eq, Clone, Copy, Hash, Serialize, Deserialize)]
pub enum Language {
    USen,
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

impl std::fmt::Display for Language {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        std::fmt::Debug::fmt(&self, f)
    }
}

#[derive(Debug, PartialEq, Clone, Hash, Serialize, Deserialize)]
pub struct Settings {
    pub cemu_dir: PathBuf,
    pub game_dir: PathBuf,
    pub game_dir_nx: PathBuf,
    pub update_dir: PathBuf,
    pub dlc_dir: PathBuf,
    pub dlc_dir_nx: PathBuf,
    pub store_dir: PathBuf,
    pub export_dir: PathBuf,
    pub export_dir_nx: PathBuf,
    pub load_reverse: bool,
    pub site_meta: PathBuf,
    pub dark_theme: bool,
    pub no_guess: bool,
    pub lang: Language,
    pub no_cemu: bool,
    pub wiiu: bool,
    pub no_hardlinks: bool,
    pub force_7z: bool,
    pub suppress_update: bool,
    pub nsfw: bool,
    pub last_version: String,
    pub changelog: bool,
    pub strip_gfx: bool,
    pub auto_gb: bool,
    pub show_gb: bool,
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
            last_version: env!("CARGO_PKG_VERSION").to_owned(),
            changelog: true,
            wiiu: true,
            auto_gb: true,
            ..Default::default()
        }
    }
}

impl Settings {
    pub fn path() -> PathBuf {
        if cfg!(windows) {
            dirs2::data_local_dir().unwrap()
        } else {
            dirs2::config_dir().unwrap()
        }
        .join("bcml")
        .join("settings.json")
    }

    pub fn base_game_dir(&self) -> &Path {
        if self.wiiu {
            &self.game_dir
        } else {
            &self.game_dir_nx
        }
    }

    pub fn main_game_dir(&self) -> &Path {
        if self.wiiu {
            &self.update_dir
        } else {
            &self.game_dir_nx
        }
    }

    pub fn dlc_dir(&self) -> Option<&Path> {
        let dir = if self.wiiu {
            &self.dlc_dir
        } else {
            &self.dlc_dir_nx
        };
        if dir.to_str().map(|d| d.is_empty()).unwrap_or_default() {
            None
        } else {
            Some(dir)
        }
    }

    pub fn mods_dir(&self) -> PathBuf {
        self.store_dir
            .join(if self.wiiu { "mods" } else { "mods_nx" })
    }

    pub fn export_dir(&self) -> Option<&Path> {
        let dir = if self.wiiu {
            self.export_dir.as_path()
        } else {
            self.export_dir_nx.as_path()
        };
        if dir.to_str().map(|d| d.is_empty()).unwrap_or_default() {
            None
        } else {
            Some(dir)
        }
    }

    pub fn master_mod_dir(&self) -> PathBuf {
        self.mods_dir().join("9999_BCML")
    }

    #[inline]
    pub fn endian(&self) -> roead::Endian {
        if self.wiiu {
            roead::Endian::Big
        } else {
            roead::Endian::Little
        }
    }

    pub fn save(&self) -> Result<()> {
        serde_json::to_writer_pretty(std::fs::File::create(&Self::path())?, &self)?;
        Ok(())
    }
}

lazy_static::lazy_static! {
    pub static ref SETTINGS: std::sync::Arc<std::sync::Mutex<Settings>> = {
        let settings_path = Settings::path();
        std::sync::Arc::new(std::sync::Mutex::new(if settings_path.exists() {
            serde_json::from_reader(std::fs::File::open(&settings_path).unwrap()).unwrap()
        } else {
            Settings::default()
        }))
    };
}
