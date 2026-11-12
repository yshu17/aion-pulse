# Builds the Pulse+ release for the users: copied to local\Pulse+Release, the one tools\single_exe packs.
# The script is ASCII only on purpose: Windows PowerShell 5.1 reads files by code page.
# Usage: powershell -ExecutionPolicy Bypass -File tools\build_pulse_plus.ps1
$ErrorActionPreference = "Stop"

$root = (Resolve-Path "$PSScriptRoot\..").Path
$launcher = Join-Path $root "launcher"
$built = Join-Path $launcher "src-tauri\target\release\tauri-app.exe"
$target = Join-Path $root "local\Pulse+Release"

# a running copy of this build holds data/pulse.db open: it is closed first (it is replaced below anyway)
Get-CimInstance Win32_Process -Filter "Name='Pulse+Local.exe'" | Where-Object { $_.ExecutablePath -like "$target\*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
# the one game database first (data/pulse.db, docs/ADR-002-pulse-db.md): every tab reads it, the build packs it
& python (Join-Path $root "tools\build_pulse_db.py")
if ($LASTEXITCODE -ne 0) { throw "build_pulse_db failed: $LASTEXITCODE" }
# the record of this database as a pack (data\db_pack.json, also in the program): it is compared with the newest pack on the release
& python (Join-Path $root "tools\pack_pulse_db.py")
if ($LASTEXITCODE -ne 0) { throw "pack_pulse_db failed: $LASTEXITCODE" }

Push-Location $launcher
try {
    & npx tauri build --no-bundle
    if ($LASTEXITCODE -ne 0) { throw "tauri build failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path $target -Force | Out-Null
$exe = Join-Path $target "Pulse+Local.exe"
Get-CimInstance Win32_Process -Filter "Name='Pulse+Local.exe'" | Where-Object { $_.ExecutablePath -like "$target\*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 1
if (Test-Path "$exe.old") { Remove-Item "$exe.old" -Force }
if (Test-Path $exe) { Rename-Item $exe "Pulse+Local.exe.old" }
Copy-Item $built $exe
"release build: {0} ({1:N1} MB)" -f $exe, ((Get-Item $exe).Length / 1MB)
