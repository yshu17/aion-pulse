//! File access for the launcher's TypeScript core.
//!
//! The core never touches a path: it gets text and bytes. These commands are the whole bridge:
//! - reading is allowed anywhere (the game's Chat.log lives in the game folder) and is read-only;
//! - writing is allowed only inside the launcher's own config folder (config.json and its backups), so the game
//!   folder and game files can never be changed through the launcher.
//!
//! A missing file is reported as an error text that starts with `ENOENT`, as the core's reader expects.

use std::fs::{self, File};
use std::io::{ErrorKind, Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

use tauri::ipc::Response;
use tauri::{AppHandle, Manager};

const MAX_READ: u64 = 64 * 1024 * 1024; // one request never asks for more than 64 MiB

fn io_error(path: &str, error: std::io::Error) -> String {
    if error.kind() == ErrorKind::NotFound {
        format!("ENOENT: {path}")
    } else {
        format!("{:?}: {path}: {error}", error.kind())
    }
}

/// The folder of the launcher's own files: `PULSE_CONFIG_DIR` (development) or the app config folder.
fn config_dir(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(dir) = std::env::var("PULSE_CONFIG_DIR") {
        return Ok(PathBuf::from(dir));
    }
    app.path().app_config_dir().map_err(|e| e.to_string())
}

#[tauri::command]
fn config_path(app: AppHandle) -> Result<String, String> {
    Ok(config_dir(&app)?.join("config.json").to_string_lossy().into_owned())
}

/// The client process of the game: bin32 and bin64 clients have the same name.
const GAME_PROCESSES: [&str; 1] = ["aion.bin"];

fn has_game(names: &[String]) -> bool {
    names.iter().any(|name| GAME_PROCESSES.contains(&name.to_lowercase().as_str()))
}

/// Names of the running processes, from the ToolHelp snapshot (no console window, no rights on the processes); None
/// when the list cannot be read.
#[cfg(windows)]
fn process_names() -> Option<Vec<String>> {
    #[repr(C)]
    struct ProcessEntry {
        size: u32,
        usage: u32,
        process_id: u32,
        default_heap_id: usize,
        module_id: u32,
        threads: u32,
        parent_process_id: u32,
        priority: i32,
        flags: u32,
        exe_file: [u16; 260],
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn CreateToolhelp32Snapshot(flags: u32, process_id: u32) -> isize;
        fn Process32FirstW(snapshot: isize, entry: *mut ProcessEntry) -> i32;
        fn Process32NextW(snapshot: isize, entry: *mut ProcessEntry) -> i32;
        fn CloseHandle(handle: isize) -> i32;
    }
    const SNAPSHOT_PROCESSES: u32 = 0x2;
    unsafe {
        let snapshot = CreateToolhelp32Snapshot(SNAPSHOT_PROCESSES, 0);
        if snapshot == 0 || snapshot == -1 {
            return None;
        }
        let mut entry: ProcessEntry = std::mem::zeroed();
        entry.size = std::mem::size_of::<ProcessEntry>() as u32;
        let mut names = Vec::new();
        let mut ok = Process32FirstW(snapshot, &mut entry);
        while ok != 0 {
            let len = entry.exe_file.iter().position(|&c| c == 0).unwrap_or(entry.exe_file.len());
            names.push(String::from_utf16_lossy(&entry.exe_file[..len]));
            ok = Process32NextW(snapshot, &mut entry);
        }
        CloseHandle(snapshot);
        Some(names)
    }
}

#[cfg(not(windows))]
fn process_names() -> Option<Vec<String>> {
    None
}

/// Is the game running? None when the process list is unavailable (the caller then must not stop anything).
#[tauri::command]
fn game_running() -> Option<bool> {
    process_names().map(|names| has_game(&names))
}

/// Where an old Pulse may keep its settings: config.json in the launcher's folder and in up to five folders above
/// it (Pulse.exe keeps config.json next to itself; a development build of the launcher sits deep inside the
/// project). Only files that exist, nearest first; the caller checks that they are Pulse settings.
#[tauri::command]
fn pulse_config_candidates() -> Vec<String> {
    let Ok(exe) = std::env::current_exe() else { return Vec::new() };
    exe.ancestors()
        .skip(1)
        .take(6)
        .map(|dir| dir.join("config.json"))
        .filter(|path| path.is_file())
        .map(|path| path.to_string_lossy().into_owned())
        .collect()
}

/// The whole text of a file (UTF-8, a BOM dropped), or None when there is no such file.
#[tauri::command]
fn read_text(path: String) -> Result<Option<String>, String> {
    match fs::read(&path) {
        Ok(bytes) => {
            let text = String::from_utf8_lossy(&bytes);
            Ok(Some(text.strip_prefix('\u{feff}').unwrap_or(&text).to_owned()))
        }
        Err(e) if e.kind() == ErrorKind::NotFound => Ok(None),
        Err(e) => Err(io_error(&path, e)),
    }
}

#[tauri::command]
fn file_size(path: String) -> Result<u64, String> {
    fs::metadata(&path).map(|m| m.len()).map_err(|e| io_error(&path, e))
}

/// `length` bytes from `position` (fewer at the end of the file), as raw bytes.
#[tauri::command]
fn read_range(path: String, position: u64, length: u64) -> Result<Response, String> {
    let mut file = File::open(&path).map_err(|e| io_error(&path, e))?;
    file.seek(SeekFrom::Start(position)).map_err(|e| io_error(&path, e))?;
    let mut data = Vec::new();
    file.take(length.min(MAX_READ)).read_to_end(&mut data).map_err(|e| io_error(&path, e))?;
    Ok(Response::new(data))
}

/// True for a file directly in `dir`: no «..» or «.» anywhere in the path, the parent is exactly `dir`.
fn inside(dir: &Path, path: &Path) -> bool {
    use std::path::Component;
    let plain = path.components().all(|c| !matches!(c, Component::ParentDir | Component::CurDir));
    plain && path.parent() == Some(dir) && path.file_name().is_some()
}

/// Write a file in the launcher's config folder: a temporary file, then a rename, so a crash never leaves half a file.
#[tauri::command]
fn write_text(app: AppHandle, path: String, text: String) -> Result<(), String> {
    let dir = config_dir(&app)?;
    let target = PathBuf::from(&path);
    if !inside(&dir, &target) {
        return Err(format!("EACCES: writing outside the launcher's config folder is not allowed: {path}"));
    }
    fs::create_dir_all(&dir).map_err(|e| io_error(&path, e))?;
    let temporary = target.with_extension("tmp");
    fs::write(&temporary, text).map_err(|e| io_error(&path, e))?;
    fs::rename(&temporary, &target).map_err(|e| io_error(&path, e))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![config_path, game_running, pulse_config_candidates, read_text, file_size, read_range, write_text])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{has_game, inside};
    use std::path::Path;

    #[test]
    fn finds_the_game_process_whatever_the_case() {
        let list = |names: &[&str]| names.iter().map(|n| n.to_string()).collect::<Vec<_>>();
        assert!(has_game(&list(&["explorer.exe", "Aion.bin"])));
        assert!(has_game(&list(&["AION.BIN"])));
        assert!(!has_game(&list(&["explorer.exe", "aion.bin.exe", "aion.exe"])));
        assert!(!has_game(&[]));
    }

    #[test]
    fn writes_only_files_directly_in_the_config_folder() {
        let dir = Path::new(r"C:\Users\x\AppData\Roaming\com.pulse.launcher");
        assert!(inside(dir, &dir.join("config.json")));
        assert!(inside(dir, &dir.join("config.json.broken")));
        assert!(!inside(dir, &dir.join("..").join("escape.json")));
        assert!(!inside(dir, Path::new(r"C:\Users\x\AppData\Roaming\com.pulse.launcher\..\escape.json")));
        assert!(!inside(dir, &dir.join("sub").join("config.json")));
        assert!(!inside(dir, Path::new(r"C:\aMain\Games\AION Imperia\Aion Empire\test.txt")));
        assert!(!inside(dir, dir));
    }
}
