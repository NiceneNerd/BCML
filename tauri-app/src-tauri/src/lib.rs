#![deny(clippy::unwrap_used)]

pub use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use fs_err as fs;

// Simplified settings management for the Tauri app
// This is a basic implementation that will be extended later
fn get_default_settings_dir() -> PathBuf {
    if cfg!(windows) {
        dirs::data_local_dir().unwrap_or_else(|| PathBuf::from(".")).join("bcml")
    } else {
        dirs::config_dir().unwrap_or_else(|| PathBuf::from(".")).join("bcml")
    }
}

fn get_settings_file() -> PathBuf {
    get_default_settings_dir().join("settings.json")
}

#[derive(Debug, Default, Serialize, Deserialize)]
struct SimpleSettings {
    pub game_dir: String,
    pub game_dir_nx: String,
    pub update_dir: String,
    pub dlc_dir: String,
    pub dlc_dir_nx: String,
    pub cemu_dir: String,
    pub store_dir: String,
    pub export_dir: String,
    pub export_dir_nx: String,
    pub wiiu: bool,
    pub lang: String,
    pub no_cemu: bool,
    pub no_hardlinks: bool,
    pub force_7z: bool,
    pub suppress_update: bool,
    pub load_reverse: bool,
    pub nsfw: bool,
    pub changelog: bool,
    pub strip_gfx: bool,
    pub auto_gb: bool,
    pub show_gb: bool,
    pub site_meta: String,
    pub no_guess: bool,
}

impl SimpleSettings {
    fn load() -> Result<Self, String> {
        let settings_file = get_settings_file();
        if settings_file.exists() {
            let content = fs::read_to_string(&settings_file).map_err(|e| e.to_string())?;
            serde_json::from_str(&content).map_err(|e| e.to_string())
        } else {
            Ok(Self {
                store_dir: get_default_settings_dir().to_string_lossy().to_string(),
                wiiu: true,
                lang: "USen".to_string(),
                changelog: true,
                auto_gb: true,
                show_gb: true,
                ..Default::default()
            })
        }
    }

    fn save(&self) -> Result<(), String> {
        let settings_file = get_settings_file();
        if let Some(parent) = settings_file.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let content = serde_json::to_string_pretty(self).map_err(|e| e.to_string())?;
        fs::write(&settings_file, content).map_err(|e| e.to_string())
    }

    fn mods_dir(&self) -> PathBuf {
        let base_dir = if self.store_dir.is_empty() {
            get_default_settings_dir()
        } else {
            PathBuf::from(&self.store_dir)
        };
        base_dir.join(if self.wiiu { "mods" } else { "mods_nx" })
    }
}

// Tauri command structures
#[derive(Debug, Deserialize)]
pub struct ModDirArgs {
    mod_dir: String,
}

#[derive(Debug, Serialize)]
pub struct ModFile {
    path: String,
    modified: bool,
}

#[derive(Debug, Serialize)]
pub struct ModInfo {
    name: String,
    path: String,
    enabled: bool,
    priority: i32,
    description: Option<String>,
    version: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SettingsData {
    game_dir: String,
    game_dir_nx: String,
    update_dir: String,
    dlc_dir: String,
    dlc_dir_nx: String,
    cemu_dir: String,
    store_dir: String,
    export_dir: String,
    export_dir_nx: String,
    wiiu: bool,
    lang: String,
    no_cemu: bool,
    no_hardlinks: bool,
    force_7z: bool,
    suppress_update: bool,
    load_reverse: bool,
    nsfw: bool,
    changelog: bool,
    strip_gfx: bool,
    auto_gb: bool,
    show_gb: bool,
    site_meta: String,
    no_guess: bool,
}

#[derive(Debug, Serialize)]
pub struct BackupInfo {
    name: String,
    path: String,
    num: i32,
}

#[derive(Debug, Serialize)]
pub struct ProfileInfo {
    name: String,
    path: String,
}

// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn get_version() -> Result<String, String> {
    Ok("3.10.8".to_string())
}

#[tauri::command]
async fn sanity_check() -> Result<bool, String> {
    // Check if BCML setup is valid
    let settings = SimpleSettings::load()?;
    
    // Check if game directory exists and contains valid game files
    if !settings.game_dir.is_empty() {
        let game_dir = Path::new(&settings.game_dir);
        if !game_dir.exists() {
            return Ok(false);
        }
    }
    
    // Check if store directory exists
    let store_dir = PathBuf::from(&settings.store_dir);
    if !store_dir.exists() {
        fs::create_dir_all(&store_dir).map_err(|e| e.to_string())?;
    }
    
    // Check if mods directory exists
    let mods_dir = settings.mods_dir();
    if !mods_dir.exists() {
        fs::create_dir_all(&mods_dir).map_err(|e| e.to_string())?;
    }
    
    Ok(true)
}

#[tauri::command]
async fn get_mods() -> Result<Vec<ModInfo>, String> {
    let settings = SimpleSettings::load()?;
    let mods_dir = settings.mods_dir();
    
    if !mods_dir.exists() {
        return Ok(vec![]);
    }
    
    let mut mods = Vec::new();
    
    // Scan for mod directories
    for entry in fs::read_dir(&mods_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        
        if path.is_dir() && !path.file_name().unwrap_or_default().to_string_lossy().starts_with('.') {
            let mod_name = path.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            
            // Skip special BCML directories
            if mod_name == "9999_BCML" {
                continue;
            }
            
            let enabled = !path.join(".disabled").exists();
            let mut description = None;
            let mut version = None;
            
            // Try to read mod metadata
            let info_file = path.join("info.json");
            if info_file.exists() {
                if let Ok(info_content) = fs::read_to_string(&info_file) {
                    if let Ok(info_json) = serde_json::from_str::<serde_json::Value>(&info_content) {
                        description = info_json.get("description")
                            .and_then(|v| v.as_str())
                            .map(|s| s.to_string());
                        version = info_json.get("version")
                            .and_then(|v| v.as_str())
                            .map(|s| s.to_string());
                    }
                }
            }
            
            // Extract priority from folder name (if numeric prefix exists)
            let priority = if let Some(first_part) = mod_name.split('_').next() {
                first_part.parse::<i32>().unwrap_or(0)
            } else {
                0
            };
            
            mods.push(ModInfo {
                name: mod_name,
                path: path.to_string_lossy().to_string(),
                enabled,
                priority,
                description,
                version,
            });
        }
    }
    
    // Sort by priority (higher priority first)
    mods.sort_by(|a, b| b.priority.cmp(&a.priority));
    
    Ok(mods)
}

#[tauri::command]
async fn get_settings() -> Result<SettingsData, String> {
    let settings = SimpleSettings::load()?;
    
    Ok(SettingsData {
        game_dir: settings.game_dir,
        game_dir_nx: settings.game_dir_nx,
        update_dir: settings.update_dir,
        dlc_dir: settings.dlc_dir,
        dlc_dir_nx: settings.dlc_dir_nx,
        cemu_dir: settings.cemu_dir,
        store_dir: settings.store_dir,
        export_dir: settings.export_dir,
        export_dir_nx: settings.export_dir_nx,
        wiiu: settings.wiiu,
        lang: settings.lang,
        no_cemu: settings.no_cemu,
        no_hardlinks: settings.no_hardlinks,
        force_7z: settings.force_7z,
        suppress_update: settings.suppress_update,
        load_reverse: settings.load_reverse,
        nsfw: settings.nsfw,
        changelog: settings.changelog,
        strip_gfx: settings.strip_gfx,
        auto_gb: settings.auto_gb,
        show_gb: settings.show_gb,
        site_meta: settings.site_meta,
        no_guess: settings.no_guess,
    })
}

#[tauri::command]
async fn save_settings(settings_data: SettingsData) -> Result<(), String> {
    let settings = SimpleSettings {
        game_dir: settings_data.game_dir,
        game_dir_nx: settings_data.game_dir_nx,
        update_dir: settings_data.update_dir,
        dlc_dir: settings_data.dlc_dir,
        dlc_dir_nx: settings_data.dlc_dir_nx,
        cemu_dir: settings_data.cemu_dir,
        store_dir: if settings_data.store_dir.is_empty() {
            get_default_settings_dir().to_string_lossy().to_string()
        } else {
            settings_data.store_dir
        },
        export_dir: settings_data.export_dir,
        export_dir_nx: settings_data.export_dir_nx,
        wiiu: settings_data.wiiu,
        lang: settings_data.lang,
        no_cemu: settings_data.no_cemu,
        no_hardlinks: settings_data.no_hardlinks,
        force_7z: settings_data.force_7z,
        suppress_update: settings_data.suppress_update,
        load_reverse: settings_data.load_reverse,
        nsfw: settings_data.nsfw,
        changelog: settings_data.changelog,
        strip_gfx: settings_data.strip_gfx,
        auto_gb: settings_data.auto_gb,
        show_gb: settings_data.show_gb,
        site_meta: settings_data.site_meta,
        no_guess: settings_data.no_guess,
    };
    
    settings.save()
}

#[tauri::command]
async fn toggle_mod(mod_path: String, enabled: bool) -> Result<(), String> {
    let mod_dir = Path::new(&mod_path);
    let disabled_file = mod_dir.join(".disabled");
    
    if enabled {
        // Enable mod by removing .disabled file
        if disabled_file.exists() {
            fs::remove_file(&disabled_file).map_err(|e| e.to_string())?;
        }
    } else {
        // Disable mod by creating .disabled file
        if !disabled_file.exists() {
            fs::write(&disabled_file, "").map_err(|e| e.to_string())?;
        }
    }
    
    Ok(())
}

#[tauri::command]
async fn uninstall_mod(mod_path: String) -> Result<(), String> {
    let mod_dir = Path::new(&mod_path);
    
    if !mod_dir.exists() {
        return Err("Mod directory does not exist".to_string());
    }
    
    // Safety check - ensure we're only deleting from the mods directory
    let settings = SimpleSettings::load()?;
    let mods_dir = settings.mods_dir();
    
    if !mod_dir.starts_with(&mods_dir) {
        return Err("Invalid mod path - not in mods directory".to_string());
    }
    
    // Remove the mod directory
    std::fs::remove_dir_all(mod_dir).map_err(|e| e.to_string())?;
    
    Ok(())
}

#[tauri::command]
async fn find_modified_files(args: ModDirArgs) -> Result<Vec<String>, String> {
    let mod_dir = Path::new(&args.mod_dir);
    
    if !mod_dir.exists() {
        return Err("Directory does not exist".to_string());
    }
    
    let mut modified_files = Vec::new();
    
    // Recursively scan directory for files
    fn scan_directory(dir: &Path, base_dir: &Path, files: &mut Vec<String>) -> Result<(), Box<dyn std::error::Error>> {
        for entry in fs::read_dir(dir)? {
            let entry = entry?;
            let path = entry.path();
            
            if path.is_file() {
                // Get relative path from base directory
                let relative_path = path.strip_prefix(base_dir)?;
                
                // For now, just check file extensions to identify potentially modified files
                // This is a simplified version - the full implementation would use hash checking
                if let Some(ext) = path.extension() {
                    let ext_str = ext.to_string_lossy().to_lowercase();
                    if matches!(ext_str.as_str(), "sbyml" | "byml" | "pack" | "sarc" | "smubin" | "sbfres") {
                        files.push(relative_path.to_string_lossy().to_string());
                    }
                }
            } else if path.is_dir() {
                // Skip hidden directories and special BCML directories
                if let Some(name) = path.file_name() {
                    let name_str = name.to_string_lossy();
                    if !name_str.starts_with('.') && name_str != "logs" && name_str != "options" {
                        scan_directory(&path, base_dir, files)?;
                    }
                }
            }
        }
        Ok(())
    }
    
    scan_directory(mod_dir, mod_dir, &mut modified_files).map_err(|e| e.to_string())?;
    
    Ok(modified_files)
}

// Additional commands for full functionality
#[tauri::command]
async fn save_mod_list() -> Result<(), String> {
    // TODO: Implement saving mod list to file
    // For now, just return success
    Ok(())
}

#[tauri::command]
async fn update_bcml() -> Result<(), String> {
    // TODO: Implement BCML update functionality
    // For now, just return success
    Err("Update functionality not yet implemented".to_string())
}

#[tauri::command]
async fn launch_game() -> Result<(), String> {
    let settings = SimpleSettings::load()?;
    
    if settings.wiiu && !settings.no_cemu && !settings.cemu_dir.is_empty() {
        // Try to launch Cemu if configured
        let cemu_exe = Path::new(&settings.cemu_dir).join("Cemu.exe");
        if cemu_exe.exists() {
            std::process::Command::new(&cemu_exe)
                .spawn()
                .map_err(|e| format!("Failed to launch Cemu: {}", e))?;
            Ok(())
        } else {
            Err("Cemu executable not found".to_string())
        }
    } else {
        Err("Game launch not configured".to_string())
    }
}

#[tauri::command]
async fn install_mod(mods: Vec<String>, options: serde_json::Value) -> Result<(), String> {
    // TODO: Implement mod installation
    // For now, just return success
    println!("Installing mods: {:?} with options: {:?}", mods, options);
    Ok(())
}

#[tauri::command]
async fn uninstall_all_mods() -> Result<(), String> {
    let settings = SimpleSettings::load()?;
    let mods_dir = settings.mods_dir();
    
    if !mods_dir.exists() {
        return Ok(());
    }
    
    // Remove all mod directories except BCML special directories
    for entry in fs::read_dir(&mods_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        
        if path.is_dir() {
            let name = path.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            
            // Skip special BCML directories
            if name == "9999_BCML" || name.starts_with('.') {
                continue;
            }
            
            std::fs::remove_dir_all(&path).map_err(|e| e.to_string())?;
        }
    }
    
    Ok(())
}

#[tauri::command]
async fn explore_mod(mod_path: String) -> Result<(), String> {
    let path = Path::new(&mod_path);
    
    if !path.exists() {
        return Err("Mod directory does not exist".to_string());
    }
    
    // Open the directory in the system file explorer
    #[cfg(windows)]
    {
        std::process::Command::new("explorer")
            .arg(&mod_path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&mod_path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&mod_path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    
    Ok(())
}

#[tauri::command]
async fn reprocess_mod(mod_path: String) -> Result<(), String> {
    // TODO: Implement mod reprocessing
    println!("Reprocessing mod: {}", mod_path);
    Ok(())
}

#[tauri::command]
async fn remerge_all() -> Result<(), String> {
    // TODO: Implement remerge functionality
    println!("Remerging all mods");
    Ok(())
}

#[tauri::command]
async fn export_mods() -> Result<(), String> {
    // TODO: Implement mod export functionality
    println!("Exporting mods");
    Ok(())
}

// Backup management commands
#[tauri::command]
async fn get_backups() -> Result<Vec<BackupInfo>, String> {
    let settings = SimpleSettings::load()?;
    let backups_dir = Path::new(&settings.store_dir).join("backups");
    
    if !backups_dir.exists() {
        return Ok(vec![]);
    }
    
    let mut backups = Vec::new();
    
    for entry in fs::read_dir(&backups_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        
        if path.is_dir() {
            let name = path.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            
            // Count mods in backup (rough estimate)
            let mods_count = if let Ok(entries) = fs::read_dir(&path) {
                entries.count() as i32
            } else {
                0
            };
            
            backups.push(BackupInfo {
                name,
                path: path.to_string_lossy().to_string(),
                num: mods_count,
            });
        }
    }
    
    Ok(backups)
}

#[tauri::command]
async fn create_backup(backup: String) -> Result<(), String> {
    // TODO: Implement backup creation
    println!("Creating backup: {}", backup);
    Ok(())
}

#[tauri::command]
async fn restore_backup(backup: String) -> Result<(), String> {
    // TODO: Implement backup restoration
    println!("Restoring backup: {}", backup);
    Ok(())
}

#[tauri::command]
async fn delete_backup(backup: String) -> Result<(), String> {
    let backup_path = Path::new(&backup);
    
    if backup_path.exists() && backup_path.is_dir() {
        std::fs::remove_dir_all(backup_path).map_err(|e| e.to_string())?;
    }
    
    Ok(())
}

#[tauri::command]
async fn restore_old_backup() -> Result<(), String> {
    // TODO: Implement BCML 2.8 backup restoration
    Err("Old backup restoration not yet implemented".to_string())
}

// Profile management commands
#[tauri::command]
async fn get_profiles() -> Result<Vec<ProfileInfo>, String> {
    let settings = SimpleSettings::load()?;
    let profiles_dir = Path::new(&settings.store_dir).join("profiles");
    
    if !profiles_dir.exists() {
        return Ok(vec![]);
    }
    
    let mut profiles = Vec::new();
    
    for entry in fs::read_dir(&profiles_dir).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let path = entry.path();
        
        if path.is_dir() {
            let name = path.file_name()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string();
            
            profiles.push(ProfileInfo {
                name,
                path: path.to_string_lossy().to_string(),
            });
        }
    }
    
    Ok(profiles)
}

#[tauri::command]
async fn get_current_profile() -> Result<Option<ProfileInfo>, String> {
    // TODO: Implement current profile detection
    Ok(None)
}

#[tauri::command]
async fn save_profile(profile: serde_json::Value) -> Result<(), String> {
    // TODO: Implement profile saving
    println!("Saving profile: {:?}", profile);
    Ok(())
}

#[tauri::command]
async fn set_profile(profile: serde_json::Value) -> Result<(), String> {
    // TODO: Implement profile loading
    println!("Loading profile: {:?}", profile);
    Ok(())
}

#[tauri::command]
async fn delete_profile(profile: serde_json::Value) -> Result<(), String> {
    // TODO: Implement profile deletion
    println!("Deleting profile: {:?}", profile);
    Ok(())
}

// Dev tools commands
#[tauri::command]
async fn create_bnp(mod_data: serde_json::Value, output_dir: Option<String>) -> Result<(), String> {
    // TODO: Implement BNP creation
    println!("Creating BNP with data: {:?} to output: {:?}", mod_data, output_dir);
    Ok(())
}

#[tauri::command]
async fn get_existing_meta(path: String) -> Result<Option<serde_json::Value>, String> {
    let mod_dir = Path::new(&path);
    let info_file = mod_dir.join("info.json");
    
    if info_file.exists() {
        if let Ok(content) = fs::read_to_string(&info_file) {
            if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&content) {
                return Ok(Some(meta));
            }
        }
    }
    
    Ok(None)
}

#[tauri::command]
async fn convert_mod(source_dir: String, output_dir: String) -> Result<(), String> {
    // TODO: Implement mod conversion
    println!("Converting mod from {} to {}", source_dir, output_dir);
    Ok(())
}

#[tauri::command]
async fn compare_files(dir1: String, dir2: String) -> Result<serde_json::Value, String> {
    // TODO: Implement file comparison
    println!("Comparing {} and {}", dir1, dir2);
    
    // Return placeholder comparison result
    Ok(serde_json::json!({
        "added": [],
        "modified": [],
        "removed": []
    }))
}

// First-run wizard commands
#[derive(Serialize)]
struct OldSettingsResult {
    exists: bool,
    message: String,
}

#[tauri::command]
async fn check_old_settings() -> Result<OldSettingsResult, String> {
    // Check if settings.json exists
    let settings_file = get_settings_file();
    let exists = settings_file.exists();
    
    let message = if exists {
        "Settings file found and loaded successfully."
    } else {
        "No existing settings found. Starting fresh setup."
    };
    
    Ok(OldSettingsResult {
        exists,
        message: message.to_string(),
    })
}

#[tauri::command]
async fn get_old_mods_count() -> Result<u32, String> {
    // TODO: Check for old BCML mods directory and count mods
    // For now, return 0 as placeholder
    Ok(0)
}

#[tauri::command]
async fn convert_old_mods() -> Result<(), String> {
    // TODO: Implement old mod conversion
    // This would convert mods from an older BCML version
    println!("Converting old mods...");
    Ok(())
}

#[tauri::command]
async fn delete_old_mods() -> Result<(), String> {
    // TODO: Implement old mod deletion
    // This would delete mods from an older BCML version
    println!("Deleting old mods...");
    Ok(())
}

#[tauri::command]
async fn check_settings_exist() -> Result<bool, String> {
    let settings_file = get_settings_file();
    Ok(settings_file.exists())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            get_version,
            sanity_check,
            get_mods,
            get_settings,
            save_settings,
            toggle_mod,
            uninstall_mod,
            find_modified_files,
            save_mod_list,
            update_bcml,
            launch_game,
            install_mod,
            uninstall_all_mods,
            explore_mod,
            reprocess_mod,
            remerge_all,
            export_mods,
            get_backups,
            create_backup,
            restore_backup,
            delete_backup,
            restore_old_backup,
            get_profiles,
            get_current_profile,
            save_profile,
            set_profile,
            delete_profile,
            create_bnp,
            get_existing_meta,
            convert_mod,
            compare_files,
            check_old_settings,
            get_old_mods_count,
            convert_old_mods,
            delete_old_mods,
            check_settings_exist
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
