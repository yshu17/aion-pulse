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

/// The .wav names in C:\Windows\Media, sorted: the alert sounds to choose from in the settings.
#[tauri::command]
fn windows_sounds() -> Vec<String> {
    let Ok(dir) = fs::read_dir(r"C:\Windows\Media") else { return Vec::new() };
    let mut names: Vec<String> = dir
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.file_name().to_string_lossy().into_owned())
        .filter(|name| name.to_ascii_lowercase().ends_with(".wav"))
        .collect();
    names.sort_by_key(|name| name.to_lowercase());
    names
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

/// The folder PulsePlus, where Pulse+.exe keeps what outlives one build of the app (it passes the path in `PULSE_HOME`).
/// None for a copy not started from Pulse+.exe (the developer's build).
fn home_dir() -> Option<PathBuf> {
    std::env::var_os("PULSE_HOME").map(PathBuf::from).filter(|dir| dir.is_dir())
}

/// In the maps folder: the SHA-256 of the pack (see `MapsPack`) it was made from, written last.
const MAPS_MARKER: &str = "maps.version";

/// Where the map pictures are: `PULSE_MAPS` (a folder, for tests), else the maps folder of the PulsePlus folder (the
/// pictures, 140 MB, are not in Pulse+.exe: they come as a pack of their own, see `maps_install`), else `data/maps/` next
/// to the program or in a folder above it, as pulse.db. The pictures are read from there, not built into the program.
#[tauri::command]
fn maps_dir() -> Option<String> {
    if let Ok(dir) = std::env::var("PULSE_MAPS") {
        return Some(dir);
    }
    if let Some(dir) = home_dir().map(|home| home.join("maps")).filter(|dir| dir.join("maps.json").is_file() && dir.join(MAPS_MARKER).is_file()) {
        return Some(dir.to_string_lossy().into_owned());
    }
    let exe = std::env::current_exe().ok()?;
    exe.ancestors().skip(1).map(|dir| dir.join("data").join("maps")).find(|dir| dir.join("maps.json").is_file())
        .map(|dir| dir.to_string_lossy().into_owned())
}

/// The bestiary's pictures folder (`data/bestiary` with its `icons`): `PULSE_BESTIARY` (for tests), else next to the
/// program or in a folder above it. It travels in the program's own data, apart from the maps.
#[tauri::command]
fn bestiary_dir() -> Option<String> {
    if let Ok(dir) = std::env::var("PULSE_BESTIARY") {
        return Some(dir);
    }
    let exe = std::env::current_exe().ok()?;
    exe.ancestors().skip(1).map(|dir| dir.join("data").join("bestiary")).find(|dir| dir.join("icons").is_dir())
        .map(|dir| dir.to_string_lossy().into_owned())
}

/// The one game database of Pulse+ (docs/ADR-002-pulse-db.md): `data/pulse.db`, built by tools/build_pulse_db.py.
const PULSE_DB: &str = "pulse.db";
const DB_ROWS: usize = 250_000; // the biggest answer a screen asks for (all the points of the map's index: ~70 000)

/// Where pulse.db is: `PULSE_DB` (a file, for tests), else `data/pulse.db` next to the program or in a folder above it.
fn pulse_db_path() -> Option<PathBuf> {
    if let Ok(file) = std::env::var("PULSE_DB") {
        return Some(PathBuf::from(file));
    }
    let exe = std::env::current_exe().ok()?;
    exe.ancestors().skip(1).map(|dir| dir.join("data").join(PULSE_DB)).find(|path| path.is_file())
}

/// One answer of the database, by columns: names once, then the rows (smaller than an object per row).
#[derive(serde::Serialize, Debug, PartialEq)]
struct DbAnswer {
    columns: Vec<String>,
    rows: Vec<Vec<serde_json::Value>>,
}

/// The connection, opened once and only for reading; the queries of the screens run one at a time on it.
static PULSE: std::sync::Mutex<Option<rusqlite::Connection>> = std::sync::Mutex::new(None);

fn to_sql(value: &serde_json::Value) -> rusqlite::types::Value {
    use rusqlite::types::Value;
    match value {
        serde_json::Value::Null => Value::Null,
        serde_json::Value::Bool(b) => Value::Integer(*b as i64),
        serde_json::Value::Number(n) => n.as_i64().map(Value::Integer).unwrap_or_else(|| Value::Real(n.as_f64().unwrap_or(0.0))),
        serde_json::Value::String(s) => Value::Text(s.clone()),
        other => Value::Text(other.to_string()),
    }
}

/// Run a reading query on an open database; anything that would write is refused.
fn query_db(db: &rusqlite::Connection, sql: &str, params: &[serde_json::Value]) -> Result<DbAnswer, String> {
    use rusqlite::types::ValueRef;
    let mut statement = db.prepare(sql).map_err(|e| e.to_string())?;
    if !statement.readonly() {
        return Err("EPERM: pulse.db is read only".into());
    }
    let columns: Vec<String> = statement.column_names().iter().map(|c| c.to_string()).collect();
    let values: Vec<rusqlite::types::Value> = params.iter().map(to_sql).collect();
    let mut rows = statement.query(rusqlite::params_from_iter(values.iter())).map_err(|e| e.to_string())?;
    let mut out = Vec::new();
    while let Some(row) = rows.next().map_err(|e| e.to_string())? {
        if out.len() >= DB_ROWS {
            return Err(format!("E2BIG: more than {DB_ROWS} rows"));
        }
        let mut cells = Vec::with_capacity(columns.len());
        for i in 0..columns.len() {
            cells.push(match row.get_ref(i).map_err(|e| e.to_string())? {
                ValueRef::Null => serde_json::Value::Null,
                ValueRef::Integer(n) => serde_json::Value::from(n),
                ValueRef::Real(f) => serde_json::Value::from(f),
                ValueRef::Text(t) => serde_json::Value::from(String::from_utf8_lossy(t).into_owned()),
                ValueRef::Blob(b) => serde_json::Value::from(b.to_vec()),
            });
        }
        out.push(cells);
    }
    Ok(DbAnswer { columns, rows: out })
}

/// A reading query on pulse.db for the screens' repositories (launcher/src/core/db); `ENOENT` when there is no database.
#[tauri::command]
async fn db_query(sql: String, params: Vec<serde_json::Value>) -> Result<DbAnswer, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let mut held = PULSE.lock().map_err(|e| e.to_string())?;
        if held.is_none() {
            let path = pulse_db_path().filter(|path| path.is_file()).ok_or_else(|| format!("ENOENT: {PULSE_DB}"))?;
            let db = rusqlite::Connection::open_with_flags(&path, rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY | rusqlite::OpenFlags::SQLITE_OPEN_NO_MUTEX)
                .map_err(|e| e.to_string())?;
            *held = Some(db);
        }
        query_db(held.as_ref().unwrap(), &sql, &params)
    })
    .await
    .map_err(|e| e.to_string())?
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
        const NO_COPY_BITS: u32 = 0x0100; // the old picture is not stretched into the new size: nothing flashes while the page repaints
        let hwnd = overlay.hwnd().map_err(|e| e.to_string())?.0 as isize;
        let ok = unsafe { SetWindowPos(hwnd, 0, x, y, width, height, NO_Z_ORDER | NO_ACTIVATE | NO_OWNER_Z_ORDER | NO_COPY_BITS) };
        if ok == 0 { Err("SetWindowPos failed".into()) } else { Ok(()) }
    }
    #[cfg(not(windows))]
    {
        overlay.set_position(tauri::PhysicalPosition::new(x, y)).map_err(|e| e.to_string())?;
        overlay.set_size(tauri::PhysicalSize::new(width.max(0) as u32, height.max(0) as u32)).map_err(|e| e.to_string())
    }
}

/// Clip the overlay window to one rectangle (physical pixels, window coordinates): only that part is drawn and takes the
/// mouse, the rest of the window is as if it were not there (clicks go to the game). Changing the clip is instant: the
/// page is not laid out again, so the hover card, already drawn, appears without a flash or a jump.
#[tauri::command]
fn overlay_clip(app: AppHandle, x: i32, y: i32, width: i32, height: i32) -> Result<(), String> {
    let overlay = app.get_webview_window("overlay").ok_or("no overlay window")?;
    #[cfg(windows)]
    {
        #[link(name = "gdi32")]
        unsafe extern "system" {
            fn CreateRectRgn(x1: i32, y1: i32, x2: i32, y2: i32) -> isize;
        }
        #[link(name = "user32")]
        unsafe extern "system" {
            fn SetWindowRgn(hwnd: isize, region: isize, redraw: i32) -> i32;
        }
        let hwnd = overlay.hwnd().map_err(|e| e.to_string())?.0 as isize;
        // the window owns the region after SetWindowRgn: it is not deleted here
        let region = unsafe { CreateRectRgn(x, y, x + width.max(1), y + height.max(1)) };
        if region == 0 || unsafe { SetWindowRgn(hwnd, region, 1) } == 0 {
            return Err("SetWindowRgn failed".into());
        }
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let _ = (overlay, x, y, width, height);
        Ok(())
    }
}

/// The single file that started this copy: tools/single_exe/Launcher.cs puts its path in `PULSE_LAUNCHER`. None for
/// the developer's build (started directly), which never updates itself.
fn launcher_path() -> Option<PathBuf> {
    std::env::var_os("PULSE_LAUNCHER").map(PathBuf::from).filter(|path| path.is_file())
}

#[derive(serde::Serialize)]
struct UpdateStatus {
    version: String,
    can_install: bool,
}

/// This program's version and whether it can install an update itself (it was started from Pulse+.exe).
#[tauri::command]
fn update_status(app: AppHandle) -> UpdateStatus {
    UpdateStatus { version: app.package_info().version.to_string(), can_install: launcher_path().is_some() }
}

/// The only place an update is downloaded from: a file of this project's GitHub releases.
const RELEASE_FILES: &str = "https://github.com/yshu17/aion-pulse/releases/download/";

fn update_url_ok(url: &str) -> bool {
    url.strip_prefix(RELEASE_FILES)
        .is_some_and(|rest| !rest.is_empty() && !rest.contains("..") && !rest.contains(['?', '#', '@', '\\']))
}

#[derive(Clone, serde::Serialize)]
struct UpdateProgress {
    done: u64,
    total: u64,
}

/// Parts of an update download: one connection to GitHub is slow, several run side by side.
const UPDATE_PARTS: u64 = 8;

/// `size` bytes cut into at most `parts` ranges [from, to] (both ends inclusive), the last one the shortest.
fn split_ranges(size: u64, parts: u64) -> Vec<(u64, u64)> {
    if size == 0 || parts == 0 {
        return Vec::new();
    }
    let chunk = size.div_ceil(parts);
    (0..parts).map(|k| (k * chunk, ((k + 1) * chunk).min(size).saturating_sub(1))).filter(|(from, to)| from <= to && *from < size).collect()
}

enum FetchError {
    /// The server did not answer a range with 206 (or the size is unknown): take the file in one stream.
    NoRanges,
    Failed(String),
}

fn update_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(std::time::Duration::from_secs(15))
        .timeout_read(std::time::Duration::from_secs(60))
        .build()
}

/// One range into the file at its place; `done` counts the bytes of all the parts.
fn fetch_range(url: &str, path: &Path, from: u64, to: u64, done: &std::sync::atomic::AtomicU64) -> Result<(), FetchError> {
    use std::io::Write;
    use std::sync::atomic::Ordering;
    let failed = |e: &dyn std::fmt::Display| FetchError::Failed(e.to_string());
    let response = update_agent().get(url).set("User-Agent", "Pulse+").set("Range", &format!("bytes={from}-{to}")).call().map_err(|e| failed(&e))?;
    if response.status() != 206 {
        return Err(FetchError::NoRanges);
    }
    let mut reader = response.into_reader();
    let mut file = fs::OpenOptions::new().write(true).open(path).map_err(|e| failed(&e))?;
    file.seek(SeekFrom::Start(from)).map_err(|e| failed(&e))?;
    let mut buffer = vec![0u8; 256 * 1024];
    let mut left = to - from + 1;
    while left > 0 {
        let want = (buffer.len() as u64).min(left) as usize;
        let n = reader.read(&mut buffer[..want]).map_err(|e| failed(&e))?;
        if n == 0 {
            return Err(FetchError::Failed("download is incomplete".into()));
        }
        file.write_all(&buffer[..n]).map_err(|e| failed(&e))?;
        done.fetch_add(n as u64, Ordering::Relaxed);
        left -= n as u64;
    }
    file.sync_all().map_err(|e| failed(&e))
}

/// The file in `UPDATE_PARTS` ranges at once; the bytes written (all of `size`) when every part came.
fn fetch_parts(url: &str, size: u64, path: &Path, progress: &(dyn Fn(u64, u64) + Sync)) -> Result<u64, FetchError> {
    use std::sync::atomic::{AtomicU64, Ordering};
    if size == 0 {
        return Err(FetchError::NoRanges);
    }
    File::create(path).and_then(|file| file.set_len(size)).map_err(|e| FetchError::Failed(e.to_string()))?;
    let done = AtomicU64::new(0);
    let ranges = split_ranges(size, UPDATE_PARTS);
    let results: Vec<Result<(), FetchError>> = std::thread::scope(|scope| {
        let handles: Vec<_> = ranges.iter().map(|&(from, to)| { let done = &done; scope.spawn(move || fetch_range(url, path, from, to, done)) }).collect();
        while handles.iter().any(|handle| !handle.is_finished()) {
            progress(done.load(Ordering::Relaxed), size);
            std::thread::sleep(std::time::Duration::from_millis(250));
        }
        handles.into_iter().map(|handle| handle.join().unwrap_or_else(|_| Err(FetchError::Failed("download thread failed".into())))).collect()
    });
    let mut no_ranges = false;
    for result in results {
        match result {
            Ok(()) => {}
            Err(FetchError::NoRanges) => no_ranges = true,
            Err(failure) => return Err(failure),
        }
    }
    if no_ranges { Err(FetchError::NoRanges) } else { Ok(done.load(Ordering::Relaxed)) }
}

/// The file in one stream (the way before ranges); the bytes written.
fn fetch_single(url: &str, size: u64, path: &Path, progress: &dyn Fn(u64, u64)) -> Result<u64, String> {
    use std::io::Write;
    let response = update_agent().get(url).set("User-Agent", "Pulse+").call().map_err(|e| e.to_string())?;
    let total = response.header("Content-Length").and_then(|v| v.parse().ok()).unwrap_or(size);
    let mut reader = response.into_reader();
    let mut file = File::create(path).map_err(|e| e.to_string())?;
    let mut buffer = vec![0u8; 256 * 1024];
    let (mut done, mut shown) = (0u64, 0u64);
    loop {
        let n = reader.read(&mut buffer).map_err(|e| { let _ = fs::remove_file(path); e.to_string() })?;
        if n == 0 {
            break;
        }
        file.write_all(&buffer[..n]).map_err(|e| e.to_string())?;
        done += n as u64;
        if done - shown >= 1 << 20 {
            shown = done;
            progress(done, total);
        }
    }
    file.sync_all().map_err(|e| e.to_string())?;
    Ok(done)
}

fn sha256_of(path: &Path) -> Result<String, String> {
    use sha2::{Digest, Sha256};
    let mut file = File::open(path).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    let mut buffer = vec![0u8; 1 << 20];
    loop {
        let n = file.read(&mut buffer).map_err(|e| e.to_string())?;
        if n == 0 {
            return Ok(format!("{:x}", hasher.finalize()));
        }
        hasher.update(&buffer[..n]);
    }
}

/// A release file into `path`, checked: its size (when known) and its SHA-256. The file is taken from several
/// connections at once when the size is known and the server answers ranges (one GitHub connection gives about
/// 13 MB/s, eight give about 35), else in one stream. Nothing is left at `path` when a check fails.
fn download_checked(url: &str, size: u64, want: &str, path: &Path, progress: &(dyn Fn(u64, u64) + Sync)) -> Result<(), String> {
    let done = match fetch_parts(url, size, path, progress) {
        Ok(done) => done,
        Err(FetchError::NoRanges) => fetch_single(url, size, path, progress)?,
        Err(FetchError::Failed(text)) => { let _ = fs::remove_file(path); return Err(text); }
    };
    progress(done, done);
    let problem = if size > 0 && done != size {
        Some("download is incomplete".to_string())
    } else if sha256_of(path)? != want {
        Some("SHA-256 does not match the release notes".to_string())
    } else {
        None
    };
    match problem {
        Some(problem) => { let _ = fs::remove_file(path); Err(problem) }
        None => Ok(()),
    }
}

/// The pack of the map pictures (the whole of data/maps, zipped) that this build of the program wants: tools/single_exe
/// puts `data/maps_pack.json` into the program's data. It names a file of a release of this project; the pack changes
/// only when a map changes, so an update of the program does not carry the maps again.
#[derive(serde::Deserialize, Clone, Debug, PartialEq)]
struct MapsPack {
    sha256: String,
    size: u64,
    url: String,
}

fn maps_pack() -> Option<MapsPack> {
    let exe = std::env::current_exe().ok()?;
    let file = exe.ancestors().skip(1).map(|dir| dir.join("data").join("maps_pack.json")).find(|path| path.is_file())?;
    serde_json::from_slice(&fs::read(file).ok()?).ok()
}

#[derive(serde::Serialize)]
struct MapsStatus {
    /// The maps folder is missing or made from another pack than this build wants: the pack has to come.
    needed: bool,
    /// Some maps are there already (an older pack): the pictures show while the new pack comes.
    installed: bool,
    size: u64,
}

/// Do the map pictures have to be downloaded? Only a program started from Pulse+.exe that carries a pack decides so.
#[tauri::command]
fn maps_status() -> MapsStatus {
    let (Some(home), Some(pack)) = (home_dir(), maps_pack()) else { return MapsStatus { needed: false, installed: false, size: 0 } };
    let have = fs::read_to_string(home.join("maps").join(MAPS_MARKER)).ok().map(|text| text.trim().to_string());
    MapsStatus { needed: have.as_deref() != Some(pack.sha256.as_str()), installed: have.is_some(), size: pack.size }
}

/// Unpack a zip into `dest`; an entry that would leave `dest` («..», an absolute path) stops it.
fn unzip_safe(zip_path: &Path, dest: &Path) -> Result<(), String> {
    let mut archive = zip::ZipArchive::new(File::open(zip_path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    for i in 0..archive.len() {
        let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let relative = entry.enclosed_name().ok_or("an unsafe path in the archive")?;
        let out = dest.join(relative);
        if entry.is_dir() {
            fs::create_dir_all(&out).map_err(|e| e.to_string())?;
            continue;
        }
        if let Some(parent) = out.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let mut file = File::create(&out).map_err(|e| e.to_string())?;
        std::io::copy(&mut entry, &mut file).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// The whole new maps folder `stage` becomes `home/maps`. The old folder is moved aside first and kept when the new one
/// cannot take its place, so the pictures never vanish; it is deleted once the swap is done.
fn put_maps_in_place(home: &Path, stage: &Path) -> Result<(), String> {
    let target = home.join("maps");
    let old = home.join("maps-old");
    let _ = fs::remove_dir_all(&old);
    if target.exists() {
        fs::rename(&target, &old).map_err(|e| format!("the old maps are in use: {e}"))?;
    }
    if let Err(e) = fs::rename(stage, &target) {
        if old.exists() {
            let _ = fs::rename(&old, &target); // the old pictures stay
        }
        return Err(e.to_string());
    }
    let _ = fs::remove_dir_all(&old);
    Ok(())
}

static MAPS_BUSY: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Download the map pack of this build (progress in «maps-progress» events), check it and put it in place of the old maps
/// folder. The old pictures stay in use until the new folder is whole; nothing is replaced when a check fails.
#[tauri::command]
async fn maps_install(app: AppHandle) -> Result<(), String> {
    use std::sync::atomic::Ordering;
    let home = home_dir().ok_or("this copy was not started from Pulse+.exe: the maps come with the program's data")?;
    let pack = maps_pack().ok_or("this build has no map pack")?;
    if !update_url_ok(&pack.url) {
        return Err(format!("EACCES: not a file of the Pulse+ releases: {}", pack.url));
    }
    let want = pack.sha256.to_ascii_lowercase();
    if want.len() != 64 || !want.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("the map pack has no SHA-256".into());
    }
    if MAPS_BUSY.swap(true, Ordering::SeqCst) {
        return Err("the maps are already coming".into());
    }
    let events = app.clone();
    let result = tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        let work = home.join("maps-download");
        let _ = fs::remove_dir_all(&work);
        fs::create_dir_all(&work).map_err(|e| e.to_string())?;
        let zip_path = work.join("maps.zip");
        download_checked(&pack.url, pack.size, &want, &zip_path, &|done, total| { let _ = events.emit("maps-progress", UpdateProgress { done, total }); })?;
        let stage = work.join("files");
        unzip_safe(&zip_path, &stage)?;
        if !stage.join("maps.json").is_file() {
            return Err("the map pack holds no maps.json".into());
        }
        fs::write(stage.join(MAPS_MARKER), &want).map_err(|e| e.to_string())?; // last: the folder is whole
        put_maps_in_place(&home, &stage)?;
        let _ = fs::remove_dir_all(&work);
        Ok(())
    })
    .await
    .map_err(|e| e.to_string());
    MAPS_BUSY.store(false, Ordering::SeqCst);
    result?
}

/// Download the new Pulse+.exe (progress in «update-progress» events), check its size and its SHA-256 against the
/// release notes, put it in place of the Pulse+.exe that started this copy and start it: it waits for this program to
/// close, unpacks the new build and starts it. This program closes. Nothing is replaced when a check fails.
#[tauri::command]
async fn update_install(app: AppHandle, url: String, size: u64, sha256: String) -> Result<(), String> {
    if !update_url_ok(&url) {
        return Err(format!("EACCES: not a file of the Pulse+ releases: {url}"));
    }
    let want = sha256.to_ascii_lowercase();
    if want.len() != 64 || !want.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("no SHA256 in the release notes".into());
    }
    let launcher = launcher_path().ok_or("this copy was not started from Pulse+.exe: take the update from the release page")?;
    let dir = app.path().app_local_data_dir().map_err(|e| e.to_string())?.join("update");
    let events = app.clone();
    let fresh = tauri::async_runtime::spawn_blocking(move || -> Result<PathBuf, String> {
        fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let part = dir.join("Pulse+.exe.part");
        let done_path = dir.join("Pulse+.exe");
        download_checked(&url, size, &want, &part, &|done, total| { let _ = events.emit("update-progress", UpdateProgress { done, total }); })?;
        fs::rename(&part, &done_path).map_err(|e| e.to_string())?;
        Ok(done_path)
    })
    .await
    .map_err(|e| e.to_string())??;
    // the new file takes the place of the one the user starts (that one is not running: it only started this copy);
    // when that place cannot be written (a protected folder), the new file runs from the update folder
    let target = match fs::copy(&fresh, &launcher) {
        Ok(_) => launcher,
        Err(_) => fresh,
    };
    // started in its own folder: the app folder (this program's) is replaced by it and must not be its current folder
    let folder = target.parent().map(Path::to_path_buf).unwrap_or_else(std::env::temp_dir);
    std::process::Command::new(&target).arg("--wait").arg(std::process::id().to_string()).current_dir(folder)
        .spawn().map_err(|e| e.to_string())?;
    app.exit(0);
    Ok(())
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
        .invoke_handler(tauri::generate_handler![config_path, game_running, pulse_config_candidates, windows_sounds, maps_dir, read_text, file_size, read_range, write_text, http_fetch, db_query, overlay_bounds, overlay_clip, update_status, update_install, bestiary_dir, maps_status, maps_install])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::{allowed_url, has_game, inside, put_maps_in_place, query_db, split_ranges, unzip_safe, update_url_ok, MapsPack};
    use std::io::Write;
    use std::path::Path;

    /// A zip in a fresh temporary folder: (name, bytes) entries; returns the folder and the zip's path.
    fn make_zip(tag: &str, entries: &[(&str, &[u8])]) -> (std::path::PathBuf, std::path::PathBuf) {
        let dir = std::env::temp_dir().join(format!("pulse-test-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("pack.zip");
        let mut writer = zip::ZipWriter::new(std::fs::File::create(&path).unwrap());
        let options = zip::write::SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        for (name, bytes) in entries {
            writer.start_file(*name, options).unwrap();
            writer.write_all(bytes).unwrap();
        }
        writer.finish().unwrap();
        (dir, path)
    }

    #[test]
    fn unpacks_a_map_pack_with_its_folders() {
        let (dir, zip) = make_zip("ok", &[("maps.json", b"{}"), ("client/df1.jpg", b"jpg"), ("world/site/bg.png", b"png")]);
        let out = dir.join("out");
        unzip_safe(&zip, &out).unwrap();
        assert_eq!(std::fs::read(out.join("maps.json")).unwrap(), b"{}");
        assert_eq!(std::fs::read(out.join("client").join("df1.jpg")).unwrap(), b"jpg");
        assert_eq!(std::fs::read(out.join("world").join("site").join("bg.png")).unwrap(), b"png");
        let _ = std::fs::remove_dir_all(dir);
    }

    #[test]
    fn refuses_a_pack_that_would_write_outside_its_folder() {
        for evil in ["../escape.txt", "client/../../escape.txt", "/abs.txt"] {
            let (dir, zip) = make_zip("evil", &[("maps.json", b"{}"), (evil, b"x")]);
            let out = dir.join("out");
            assert!(unzip_safe(&zip, &out).is_err(), "{evil}");
            assert!(!dir.join("escape.txt").exists() && !out.join("escape.txt").exists(), "{evil}");
            let _ = std::fs::remove_dir_all(dir);
        }
    }

    #[test]
    fn a_new_maps_folder_replaces_the_old_one_and_the_old_one_stays_when_that_fails() {
        let home = std::env::temp_dir().join(format!("pulse-test-home-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&home);
        std::fs::create_dir_all(home.join("maps")).unwrap();
        std::fs::write(home.join("maps").join("maps.json"), "old").unwrap();
        let stage = home.join("maps-download").join("files");
        std::fs::create_dir_all(&stage).unwrap();
        std::fs::write(stage.join("maps.json"), "new").unwrap();
        put_maps_in_place(&home, &stage).unwrap();
        assert_eq!(std::fs::read_to_string(home.join("maps").join("maps.json")).unwrap(), "new");
        assert!(!home.join("maps-old").exists() && !stage.exists());
        // no stage folder: the swap fails and the maps of before are back
        assert!(put_maps_in_place(&home, &home.join("missing")).is_err());
        assert_eq!(std::fs::read_to_string(home.join("maps").join("maps.json")).unwrap(), "new");
        assert!(!home.join("maps-old").exists());
        let _ = std::fs::remove_dir_all(home);
    }

    #[test]
    fn reads_the_descriptor_of_a_map_pack() {
        let text = r#"{"sha256":"ab12","size":139000000,"url":"https://github.com/yshu17/aion-pulse/releases/download/v2.0.4/maps-ab12.zip","extra":1}"#;
        let pack: MapsPack = serde_json::from_str(text).unwrap();
        assert_eq!(pack.size, 139_000_000);
        assert!(update_url_ok(&pack.url));
        assert!(serde_json::from_str::<MapsPack>(r#"{"size":1}"#).is_err());
    }

    #[test]
    fn splits_a_download_into_ranges_that_cover_every_byte_once() {
        assert_eq!(split_ranges(10, 4), vec![(0, 2), (3, 5), (6, 8), (9, 9)]);
        assert_eq!(split_ranges(8, 8), (0..8).map(|k| (k, k)).collect::<Vec<_>>());
        assert_eq!(split_ranges(3, 8), vec![(0, 0), (1, 1), (2, 2)]); // fewer bytes than parts
        assert_eq!(split_ranges(184_591_360, 8).last(), Some(&(161_517_440, 184_591_359)));
        assert!(split_ranges(0, 8).is_empty());
        for size in [1u64, 7, 100, 184_591_360] {
            let ranges = split_ranges(size, 8);
            assert_eq!(ranges.first().map(|r| r.0), Some(0));
            assert_eq!(ranges.last().map(|r| r.1), Some(size - 1));
            assert!(ranges.windows(2).all(|w| w[0].1 + 1 == w[1].0));
        }
    }

    #[test]
    fn downloads_updates_only_from_the_project_releases() {
        assert!(update_url_ok("https://github.com/yshu17/aion-pulse/releases/download/v2.1.0/Pulse+.exe"));
        assert!(!update_url_ok("https://github.com/yshu17/aion-pulse/releases/download/"));
        assert!(!update_url_ok("https://github.com/someone/aion-pulse/releases/download/v2.1.0/Pulse+.exe"));
        assert!(!update_url_ok("http://github.com/yshu17/aion-pulse/releases/download/v2.1.0/Pulse+.exe"));
        assert!(!update_url_ok("https://github.com/yshu17/aion-pulse/releases/download/../../evil/x.exe"));
        assert!(!update_url_ok("https://github.com/yshu17/aion-pulse/releases/download/v2/x.exe?redirect=evil"));
        assert!(!update_url_ok("https://github.com.evil.net/yshu17/aion-pulse/releases/download/v2/x.exe"));
    }

    #[test]
    fn answers_reading_queries_on_the_game_database_and_refuses_writes() {
        let db = rusqlite::Connection::open_in_memory().unwrap();
        db.execute_batch("CREATE TABLE npc (id TEXT, name TEXT, level INTEGER); INSERT INTO npc VALUES ('1', 'Теграк', 60), ('2', 'Гера', NULL);").unwrap();
        let answer = query_db(&db, "SELECT id, name, level FROM npc WHERE id = ?1", &[serde_json::json!("1")]).unwrap();
        assert_eq!(answer.columns, vec!["id", "name", "level"]);
        assert_eq!(answer.rows, vec![vec![serde_json::json!("1"), serde_json::json!("Теграк"), serde_json::json!(60)]]);
        assert_eq!(query_db(&db, "SELECT level FROM npc WHERE id = '2'", &[]).unwrap().rows, vec![vec![serde_json::Value::Null]]);
        assert!(query_db(&db, "DELETE FROM npc", &[]).unwrap_err().starts_with("EPERM"));
        assert!(query_db(&db, "INSERT INTO npc VALUES ('3', 'x', 1)", &[]).is_err());
    }

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
}
