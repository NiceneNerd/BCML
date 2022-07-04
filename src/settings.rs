use crate::Result;
use cow_utils::CowUtils;
use fs_err as fs;
use once_cell::sync::Lazy;
use serde::{Deserialize, Serialize};
use std::{
    path::{Path, PathBuf},
    sync::{Arc, RwLock},
};

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

#[derive(Debug, PartialEq, Eq, Clone, Hash, Serialize, Deserialize)]
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
            store_dir: DATA_DIR.clone(),
            lang: Language::USen,
            last_version: env!("CARGO_PKG_VERSION").to_owned(),
            changelog: true,
            wiiu: true,
            auto_gb: true,
            cemu_dir: Default::default(),
            dark_theme: Default::default(),
            dlc_dir: Default::default(),
            dlc_dir_nx: Default::default(),
            export_dir: Default::default(),
            export_dir_nx: Default::default(),
            force_7z: Default::default(),
            game_dir: Default::default(),
            game_dir_nx: Default::default(),
            load_reverse: Default::default(),
            no_cemu: Default::default(),
            no_guess: Default::default(),
            no_hardlinks: Default::default(),
            nsfw: Default::default(),
            show_gb: Default::default(),
            site_meta: Default::default(),
            strip_gfx: Default::default(),
            suppress_update: Default::default(),
            update_dir: Default::default(),
        }
    }
}

impl Settings {
    pub fn path() -> PathBuf {
        DATA_DIR.join("settings.json")
    }

    pub fn tmp_path() -> PathBuf {
        DATA_DIR.join("tmp_settings.json")
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

    pub fn master_content_dir(&self) -> PathBuf {
        self.master_mod_dir().join(if self.wiiu {
            "content"
        } else {
            "01007EF00011E000/romfs"
        })
    }

    pub fn master_dlc_dir(&self) -> PathBuf {
        self.master_mod_dir().join(if self.wiiu {
            "aoc/0010"
        } else {
            "01007EF00011F001/romfs"
        })
    }

    pub fn merged_modpack_dir(&self) -> PathBuf {
        self.store_dir
            .join(if self.wiiu { "merged" } else { "merged_nx" })
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
        serde_json::to_writer_pretty(fs::File::create(&Self::path())?, &self)?;
        Ok(())
    }
}

pub static SETTINGS: Lazy<Arc<RwLock<Settings>>> = Lazy::new(|| {
    let settings_path = Settings::path();
    Arc::new(RwLock::new(if settings_path.exists() {
        let text = fs::read_to_string(&settings_path).unwrap();
        serde_json::from_str(&text.cow_replace(": null", ": \"\"")).unwrap_or_default()
    } else {
        Settings::default()
    }))
});

pub static TMP_SETTINGS: Lazy<Arc<RwLock<Settings>>> = Lazy::new(|| {
    let settings_path = Settings::tmp_path();
    Arc::new(RwLock::new(if settings_path.exists() {
        let text = fs::read_to_string(&settings_path).unwrap();
        serde_json::from_str(&text.cow_replace(": null", ": \"\"")).unwrap_or_default()
    } else {
        Settings::default()
    }))
});

pub static DATA_DIR: Lazy<PathBuf> = Lazy::new(|| {
    if std::env::args().any(|f| &f == "--portable") {
        std::env::current_dir().unwrap().join("bcml-data")
    } else if cfg!(windows) {
        dirs2::data_local_dir().unwrap()
    } else {
        dirs2::config_dir().unwrap()
    }
    .join("bcml")
});
