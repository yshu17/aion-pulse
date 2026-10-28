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
use tauri::{AppHandle, Emitter, Manager};

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

/// Is a game client among the processes (name, thread count)? A client without threads has exited: something still
/// holds its process (seen for days after the game was closed), so it does not count.
fn has_game(processes: &[(String, u32)]) -> bool {
    processes.iter().any(|(name, threads)| *threads > 0 && GAME_PROCESSES.contains(&name.to_lowercase().as_str()))
}

/// Names and thread counts of the running processes, from the ToolHelp snapshot (no console window, no rights on the
/// processes); None when the list cannot be read.
#[cfg(windows)]
fn process_names() -> Option<Vec<(String, u32)>> {
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
            names.push((String::from_utf16_lossy(&entry.exe_file[..len]), entry.threads));
            ok = Process32NextW(snapshot, &mut entry);
        }
        CloseHandle(snapshot);
        Some(names)
    }
}

#[cfg(not(windows))]
fn process_names() -> Option<Vec<(String, u32)>> {
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

/// Names that only mean this computer or a local network.
const LOCAL_SUFFIXES: [&str; 6] = [".local", ".localhost", ".internal", ".lan", ".home", ".arpa"];

/// The schedule check may ask a public https address (the user pastes the link): no plain http, no login in the
/// address, no IP address (so not this computer or its network), no local names.
fn allowed_url(url: &str) -> bool {
    let Some(rest) = url.strip_prefix("https://") else { return false };
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    if authority.is_empty() || authority.contains('@') || authority.starts_with('[') {
        return false;
    }
    let host = authority.split(':').next().unwrap_or("").to_ascii_lowercase();
    if host.parse::<std::net::IpAddr>().is_ok() || host.is_empty() || !host.contains('.') || host == "localhost" {
        return false;
    }
    !LOCAL_SUFFIXES.iter().any(|suffix| host.ends_with(suffix))
}

/// GET (the page text, at most 2 MB) or HEAD of a knowledge-base address, with the response headers.
/// ETag and Last-Modified keep their usual spelling, as the core reads them.
#[tauri::command]
async fn http_fetch(url: String, method: String) -> Result<(String, std::collections::HashMap<String, String>), String> {
    if !allowed_url(&url) {
        return Err(format!("EACCES: only a public https address can be asked: {url}"));
    }
    if method != "GET" && method != "HEAD" {
        return Err(format!("unsupported method {method}"));
    }
    tauri::async_runtime::spawn_blocking(move || {
        let agent = ureq::AgentBuilder::new().timeout(std::time::Duration::from_secs(10)).build();
        let response = agent.request(&method, &url).set("User-Agent", "Pulse").set("Accept-Language", "ru")
            .call().map_err(|e| e.to_string())?;
        let mut headers = std::collections::HashMap::new();
        for name in response.headers_names() {
            let key = match name.to_ascii_lowercase().as_str() {
                "etag" => "ETag".to_string(),
                "last-modified" => "Last-Modified".to_string(),
                _ => name.clone(),
            };
            if let Some(value) = response.header(&name) {
                headers.insert(key, value.to_string());
            }
        }
        let mut body = String::new();
        if method == "GET" {
            response.into_reader().take(2_000_000).read_to_string(&mut body).map_err(|e| e.to_string())?;
        }
        Ok((body, headers))
    })
    .await
    .map_err(|e| e.to_string())?
}

/// The drops of data/game (1.4 million rows, too many for a JSON file): `drops.sqlite`, built by tools/build_game_data.py.
const DROPS_FILE: &str = "drops.sqlite";
const DROPS_LIMIT: i64 = 10_000; // a popular item can drop from thousands of NPCs: a screen never needs more

/// Where drops.sqlite is: `PULSE_GAME_DATA` (a folder, for tests), else `data/game/` next to the program or in a folder
/// above it (the repository: Pulse+Local sits in `local/`, the dev build in `launcher/src-tauri/target/…`).
fn drops_path() -> Option<PathBuf> {
    if let Ok(dir) = std::env::var("PULSE_GAME_DATA") {
        return Some(PathBuf::from(dir).join(DROPS_FILE));
    }
    let exe = std::env::current_exe().ok()?;
    exe.ancestors().skip(1).map(|dir| dir.join("data").join("game").join(DROPS_FILE)).find(|path| path.is_file())
}

#[derive(serde::Serialize, Debug, PartialEq)]
struct Drop {
    npc_id: i64,
    item_id: i64,
    chance_min: Option<f64>,
    chance_max: Option<f64>,
    count_min: Option<i64>,
    count_max: Option<i64>,
}

/// Drops of an NPC (`by` = "npc") or the NPCs dropping an item (`by` = "item"), read-only.
fn query_drops(path: &Path, by: &str, id: i64) -> Result<Vec<Drop>, String> {
    let (column, order) = match by {
        "npc" => ("npc_id", "item_id"),
        "item" => ("item_id", "npc_id"),
        _ => return Err(format!("unknown drops query: {by}")),
    };
    let db = rusqlite::Connection::open_with_flags(path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY | rusqlite::OpenFlags::SQLITE_OPEN_NO_MUTEX)
        .map_err(|e| e.to_string())?;
    let sql = format!("SELECT npc_id, item_id, chance_min, chance_max, count_min, count_max FROM drops WHERE {column} = ?1 ORDER BY {order} LIMIT ?2");
    let mut statement = db.prepare(&sql).map_err(|e| e.to_string())?;
    let rows = statement
        .query_map(rusqlite::params![id, DROPS_LIMIT], |row| {
            Ok(Drop { npc_id: row.get(0)?, item_id: row.get(1)?, chance_min: row.get(2)?, chance_max: row.get(3)?, count_min: row.get(4)?, count_max: row.get(5)? })
        })
        .map_err(|e| e.to_string())?;
    rows.collect::<Result<Vec<_>, _>>().map_err(|e| e.to_string())
}

/// The drops for the game data reader; an error text that starts with `ENOENT` when drops.sqlite is not there.
#[tauri::command]
async fn game_drops(by: String, id: i64) -> Result<Vec<Drop>, String> {
    let path = drops_path().filter(|path| path.is_file()).ok_or_else(|| format!("ENOENT: {DROPS_FILE}"))?;
    tauri::async_runtime::spawn_blocking(move || query_drops(&path, &by, id)).await.map_err(|e| e.to_string())?
}

/// Move and resize the overlay window in one step (physical pixels). Two separate calls (position, then size) show one
/// frame with the content in the wrong place while the window grows upwards: the strip jumps.
#[tauri::command]
fn overlay_bounds(app: AppHandle, x: i32, y: i32, width: i32, height: i32) -> Result<(), String> {
    let overlay = app.get_webview_window("overlay").ok_or("no overlay window")?;
    #[cfg(windows)]
    {
        #[link(name = "user32")]
        unsafe extern "system" {
            fn SetWindowPos(hwnd: isize, after: isize, x: i32, y: i32, cx: i32, cy: i32, flags: u32) -> i32;
        }
        const NO_Z_ORDER: u32 = 0x0004;
        const NO_ACTIVATE: u32 = 0x0010;
        const NO_OWNER_Z_ORDER: u32 = 0x0200;
        let hwnd = overlay.hwnd().map_err(|e| e.to_string())?.0 as isize;
        let ok = unsafe { SetWindowPos(hwnd, 0, x, y, width, height, NO_Z_ORDER | NO_ACTIVATE | NO_OWNER_Z_ORDER) };
        if ok == 0 { Err("SetWindowPos failed".into()) } else { Ok(()) }
    }
    #[cfg(not(windows))]
    {
        overlay.set_position(tauri::PhysicalPosition::new(x, y)).map_err(|e| e.to_string())?;
        overlay.set_size(tauri::PhysicalSize::new(width.max(0) as u32, height.max(0) as u32)).map_err(|e| e.to_string())
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        // one program at a time: starting it again brings the running one back from the overlay
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(overlay) = app.get_webview_window("overlay") {
                let _ = overlay.hide();
            }
            if let Some(main) = app.get_webview_window("main") {
                let _ = main.emit("pulse-show-main", ());
                let _ = main.show();
                let _ = main.unminimize();
                let _ = main.set_focus();
            }
        }))
        .plugin(tauri_plugin_opener::init())
        // closing the main window ends the program: the hidden overlay must not keep it running
        .on_window_event(|window, event| {
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    window.app_handle().exit(0);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![config_path, game_running, pulse_config_candidates, read_text, file_size, read_range, write_text, http_fetch, game_drops, overlay_bounds])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{allowed_url, has_game, inside, query_drops, Drop};
    use std::path::Path;

    #[test]
    fn finds_the_game_process_whatever_the_case() {
        let list = |names: &[&str]| names.iter().map(|n| (n.to_string(), 40)).collect::<Vec<_>>();
        assert!(has_game(&list(&["explorer.exe", "Aion.bin"])));
        assert!(has_game(&list(&["AION.BIN"])));
        assert!(!has_game(&list(&["explorer.exe", "aion.bin.exe", "aion.exe"])));
        assert!(!has_game(&[]));
    }

    #[test]
    fn a_closed_game_left_without_threads_is_not_running() {
        // the client exited, but something still holds its process: no threads, no window
        assert!(!has_game(&[("aion.bin".to_string(), 0), ("aion.bin".to_string(), 0)]));
        assert!(has_game(&[("aion.bin".to_string(), 0), ("aion.bin".to_string(), 57)]));
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

    #[test]
    fn asks_only_public_https_addresses() {
        assert!(allowed_url("https://kb.aionempire.com/article/rasapisanie"));
        assert!(allowed_url("https://news.aionempire.net/storage/app/media/schedule-20ru.jpg"));
        assert!(allowed_url("https://example.org:8443/a/b.png?x=1"));
        assert!(!allowed_url("http://kb.aionempire.com/")); // no plain http
        assert!(!allowed_url("https://aionempire.com@evil.net/")); // a login in the address hides the real host
        assert!(!allowed_url("https://127.0.0.1/"));
        assert!(!allowed_url("https://192.168.0.1:8080/router"));
        assert!(!allowed_url("https://[::1]/"));
        assert!(!allowed_url("https://localhost/"));
        assert!(!allowed_url("https://printer.local/"));
        assert!(!allowed_url("https://intranet/")); // no dot: not a public name
        assert!(!allowed_url("https:///nohost"));
        assert!(!allowed_url("file:///C:/Windows/system.ini"));
    }

    #[test]
    fn reads_drops_by_npc_and_by_item() {
        let dir = std::env::temp_dir().join(format!("pulse-drops-test-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("drops.sqlite");
        let _ = std::fs::remove_file(&path);
        let db = rusqlite::Connection::open(&path).unwrap();
        db.execute_batch(
            "CREATE TABLE drops(npc_id INTEGER, item_id INTEGER, chance_min REAL, chance_max REAL, count_min INTEGER, count_max INTEGER,
               PRIMARY KEY(npc_id, item_id)) WITHOUT ROWID;
             INSERT INTO drops VALUES (210065, 100000002, NULL, NULL, NULL, NULL), (210065, 100000001, 0.5, 0.7, 1, 2), (203060, 100000001, NULL, NULL, NULL, NULL);",
        )
        .unwrap();
        drop(db);
        let of_npc = query_drops(&path, "npc", 210065).unwrap();
        assert_eq!(of_npc.iter().map(|d| d.item_id).collect::<Vec<_>>(), vec![100000001, 100000002]);
        assert_eq!(of_npc[0], Drop { npc_id: 210065, item_id: 100000001, chance_min: Some(0.5), chance_max: Some(0.7), count_min: Some(1), count_max: Some(2) });
        assert_eq!(query_drops(&path, "item", 100000001).unwrap().iter().map(|d| d.npc_id).collect::<Vec<_>>(), vec![203060, 210065]);
        assert!(query_drops(&path, "npc", 1).unwrap().is_empty());
        assert!(query_drops(&path, "zone", 1).is_err());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
