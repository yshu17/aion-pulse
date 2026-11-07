# Builds one file: Pulse+.exe = Launcher.cs + payload.zip (the RELEASE Pulse+Local.exe and the data folder without the sources of pulse.db).
# Usage: powershell -ExecutionPolicy Bypass -File tools\single_exe\build_single_exe.ps1
# The map pictures (data\maps, 140 MB) are NOT in the file: they are a pack of their own (maps-<id>.zip) that the program
# downloads when it has no maps or they changed, so an update of the program is 35 MB, not 175. maps_pack.json (next to this
# script, kept in git) records the pack that is current: its content id (a hash of the files), its zip and the release asset
# it lives at. While the maps do not change the record stays and no pack is built. When they change, pass -Tag vX.Y.Z (the release
# the new pack is uploaded to with Pulse+.exe): the script builds maps-<id>.zip next to Pulse+.exe and records it.
param(
    [string]$App = "$PSScriptRoot\..\..\local\Pulse+Release\Pulse+Local.exe",  # the build for the users, without the developer tools
    [string]$Data = "$PSScriptRoot\..\..\data",
    [string]$Out = "$PSScriptRoot\..\..\local\Pulse+Single\Pulse+.exe",
    [string]$Icon = "$PSScriptRoot\pulse.ico",  # made by make_icon.py
    [string]$Tag = "",                          # the release the new map pack goes to, only needed when the maps changed
    [string]$Repo = "yshu17/aion-pulse"
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$csc = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "csc.exe not found: $csc" }

if (-not (Test-Path $App)) { throw "no release build: run tools\build_pulse_plus.ps1 -Variant release first (the developer build is never packed)" }
if ((Resolve-Path $App).Path -notlike ("*" + [IO.Path]::DirectorySeparatorChar + "Pulse+Release" + [IO.Path]::DirectorySeparatorChar + "*")) { throw "only the release build is packed (local\Pulse+Release); the developer build is never packed" }
$app = (Resolve-Path $App).Path
$data = (Resolve-Path $Data).Path
$out = [IO.Path]::GetFullPath($Out)
$stage = Join-Path $env:TEMP ("pulse-single-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path "$stage\pkg" | Out-Null
try {
    Copy-Item $app "$stage\pkg\Pulse+Local.exe"
    Copy-Item $data "$stage\pkg\data" -Recurse
    # the sources of data/pulse.db are not needed by the program (every tab reads the database): they stay out of the package
    foreach ($source in @("game", "bestiary\npcs.sqlite", "item_names.tsv", "watch_items.csv", "item_specs.json.gz", "quest_names.tsv")) {
        Remove-Item (Join-Path "$stage\pkg\data" $source) -Recurse -Force -ErrorAction SilentlyContinue
    }
    if (-not (Test-Path "$stage\pkg\data\pulse.db")) { throw "data\pulse.db is missing: run tools\build_pulse_db.py first" }

    # the maps leave the payload: they are a pack of their own
    Remove-Item "$stage\pkg\data\maps" -Recurse -Force
    $mapsDir = Join-Path $data "maps"
    if (-not (Test-Path (Join-Path $mapsDir "maps.json"))) { throw "no data\maps\maps.json: nothing to pack" }
    $lines = @(Get-ChildItem $mapsDir -Recurse -File | ForEach-Object {
        "{0}|{1}|{2}" -f $_.FullName.Substring($mapsDir.Length + 1).Replace("\", "/"), $_.Length, (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
    })
    [Array]::Sort($lines, [StringComparer]::Ordinal)
    $sha = [Security.Cryptography.SHA256]::Create()
    $content = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes([string]::Join("`n", $lines)))) -replace "-", "").ToLower()
    $recordPath = Join-Path $PSScriptRoot "maps_pack.json"
    $record = $null
    if (Test-Path $recordPath) { $record = Get-Content $recordPath -Raw -Encoding UTF8 | ConvertFrom-Json }
    if ($record -and $record.content -eq $content) {
        "maps unchanged: pack {0} ({1:N1} MB) stays where it is: {2}" -f $record.sha256.Substring(0, 12), ($record.size / 1MB), $record.url
    } else {
        if (-not $Tag) { throw "the maps changed (or there is no maps_pack.json): pass -Tag vX.Y.Z, the release the new map pack is uploaded to" }
        $outDir = Split-Path ([IO.Path]::GetFullPath($Out))
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
        $tmpZip = Join-Path $outDir "maps-new.zip"
        Remove-Item $tmpZip -ErrorAction SilentlyContinue
        # the pictures do not shrink: the fastest level, entries with forward slashes (.NET 4.6.1 and newer)
        [IO.Compression.ZipFile]::CreateFromDirectory($mapsDir, $tmpZip, [IO.Compression.CompressionLevel]::Fastest, $false)
        $zipSha = (Get-FileHash -Algorithm SHA256 $tmpZip).Hash.ToLower()
        $name = "maps-" + $zipSha.Substring(0, 12) + ".zip"
        Move-Item $tmpZip (Join-Path $outDir $name) -Force
        $record = [ordered]@{ content = $content; sha256 = $zipSha; size = (Get-Item (Join-Path $outDir $name)).Length
            url = "https://github.com/$Repo/releases/download/$Tag/$name" }
        [IO.File]::WriteAllText($recordPath, ($record | ConvertTo-Json) + "`n", (New-Object Text.UTF8Encoding($false)))
        "NEW MAP PACK: upload {0} to the release {1}; maps_pack.json is updated: commit it" -f (Join-Path $outDir $name), $Tag
    }
    # the descriptor the program reads (data\maps_pack.json): which pack this build wants, and where it is
    $descriptor = [ordered]@{ sha256 = $record.sha256; size = $record.size; url = $record.url }
    [IO.File]::WriteAllText("$stage\pkg\data\maps_pack.json", ($descriptor | ConvertTo-Json) + "`n", (New-Object Text.UTF8Encoding($false)))

    # the zip with forward slashes in its entries (Compress-Archive of Windows PowerShell 5.1 writes backslashes)
    $zip = "$stage\payload.zip"
    [IO.Compression.ZipFile]::CreateFromDirectory("$stage\pkg", $zip)
    $build = (Get-FileHash -Algorithm SHA256 $zip).Hash.Substring(0, 16).ToLower()

    $src = Get-Content "$PSScriptRoot\Launcher.cs" -Raw -Encoding UTF8
    $src = $src.Replace("__BUILD__", $build).Replace("__MAPS__", $record.sha256)
    [IO.File]::WriteAllText("$stage\Launcher.cs", $src, (New-Object Text.UTF8Encoding($false)))

    New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
    $iconArg = @(); if (Test-Path $Icon) { $iconArg = @("/win32icon:$((Resolve-Path $Icon).Path)") }
    & $csc /nologo /target:winexe /codepage:65001 /optimize+ "/out:$out" "/resource:$zip,payload.zip" @iconArg `
        /r:System.Windows.Forms.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll "$stage\Launcher.cs"
    if ($LASTEXITCODE -ne 0) { throw "csc failed: $LASTEXITCODE" }
    "{0} build {1} {2:N1} MB, packed from {3}" -f $out, $build, ((Get-Item $out).Length / 1MB), $app
}
finally {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
}
