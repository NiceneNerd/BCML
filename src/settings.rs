use crate::Result;
use cow_utils::CowUtils;
use fs_err as fs;
use once_cell::sync::Lazy;
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::{
    path::{Path, PathBuf},
    sync::Arc,
};

#[derive(Debug, Default, PartialEq, Eq, Clone, Copy, Hash, Serialize, Deserialize)]
pub enum Language {
    #[default]
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
    #[serde(default = "default_store_dir")]
    pub store_dir: PathBuf,
    #[serde(default)]
    pub lang: Language,
    #[serde(default = "last_version")]
    pub last_version: String,
    #[serde(default = "fn_true")]
    pub changelog: bool,
    #[serde(default = "fn_true")]
    pub wiiu: bool,
    #[serde(default = "fn_true")]
    pub auto_gb: bool,
    #[serde(default)]
    pub cemu_dir: PathBuf,
    #[serde(default)]
    pub game_dir: PathBuf,
    #[serde(default)]
    pub game_dir_nx: PathBuf,
    #[serde(default)]
    pub update_dir: PathBuf,
    #[serde(default)]
    pub dlc_dir: PathBuf,
    #[serde(default)]
    pub dlc_dir_nx: PathBuf,
    #[serde(default)]
    pub export_dir: PathBuf,
    #[serde(default)]
    pub export_dir_nx: PathBuf,
    #[serde(default)]
    pub load_reverse: bool,
    #[serde(default)]
    pub site_meta: PathBuf,
    #[serde(default)]
    pub dark_theme: bool,
    #[serde(default)]
    pub no_guess: bool,
    #[serde(default)]
    pub no_cemu: bool,
    #[serde(default)]
    pub no_hardlinks: bool,
    #[serde(default)]
    pub force_7z: bool,
    #[serde(default)]
    pub suppress_update: bool,
    #[serde(default)]
    pub nsfw: bool,
    #[serde(default)]
    pub strip_gfx: bool,
    #[serde(default)]
    pub show_gb: bool,
}

#[inline]
fn default_store_dir() -> PathBuf {
    DATA_DIR.clone()
}

#[inline]
fn last_version() -> String {
    env!("CARGO_PKG_VERSION").to_owned()
}

#[inline(always)]
fn fn_true() -> bool {
    true
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            store_dir: default_store_dir(),
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

    pub fn export_dir(&self) -> Option<PathBuf> {
        if self.wiiu {
            if self.no_cemu {
                Some(self.export_dir.clone())
            } else {
                #[cfg(target_os = "windows")]
                return Some(self.cemu_dir.join("graphicPacks/BreathOfTheWild_BCML"));
                #[cfg(target_os = "linux")]
                return Some("~/.local/share/cemu/graphicPacks/BreathOfTheWild_BCML");
            }
        } else {
            Some(self.export_dir_nx.clone())
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

    pub fn reload(&mut self) -> Result<()> {
        *self = if Self::path().exists() {
            let text = fs::read_to_string(&Self::path()).unwrap();
            serde_json::from_str(&text.cow_replace(": null", ": \"\""))
                .expect("Failed to read settings file")
        } else {
            println!("WARNING: Settings file does not exist, loading default settings...");
            Settings::default()
        };
        Ok(())
    }

    pub fn save(&self) -> Result<()> {
        serde_json::to_writer_pretty(fs::File::create(&Self::path())?, &self)?;
        Ok(())
    }
}

pub static SETTINGS: Lazy<Arc<RwLock<Settings>>> = Lazy::new(|| {
    let settings_path = Settings::path();
    Arc::new(RwLock::new(if settings_path.exists() {
        let text = fs::read_to_string(&settings_path).expect("Couldn't read settings, that's bad");
        serde_json::from_str(&text.cow_replace(": null", ": \"\""))
            .expect("Failed to read settings file")
    } else {
        println!("WARNING: Settings file does not exist, loading default settings...");
        Settings::default()
    }))
});

pub static TMP_SETTINGS: Lazy<Arc<RwLock<Settings>>> = Lazy::new(|| {
    let settings_path = Settings::tmp_path();
    Arc::new(RwLock::new(if settings_path.exists() {
        let text = fs::read_to_string(&settings_path).expect("Chouldn't read settings, that's bad");
        serde_json::from_str(&text.cow_replace(": null", ": \"\""))
            .expect("Failed to read temp settings file")
    } else {
        println!("WARNING: Temp settings file does not exist, loading default settings...");
        Settings::default()
    }))
});

pub static DATA_DIR: Lazy<PathBuf> = Lazy::new(|| {
    if std::env::args().any(|f| &f == "--portable") {
        std::env::current_dir()
            .expect("Big problems if no cwd")
            .join("bcml-data")
    } else if cfg!(windows) {
        dirs2::data_local_dir().expect("Big problems if no local data dir")
    } else {
        dirs2::config_dir().expect("Big problems if no config dir")
    }
    .join("bcml")
});
