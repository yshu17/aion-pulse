# Builds one file: Pulse+.exe = Launcher.cs + payload.zip (the RELEASE Pulse+Local.exe and the data folder).
# Usage: powershell -ExecutionPolicy Bypass -File tools\single_exe\build_single_exe.ps1
param(
    [string]$App = "$PSScriptRoot\..\..\local\Pulse+Release\Pulse+Local.exe",  # the build for the users, without the developer tools
    [string]$Data = "$PSScriptRoot\..\..\data",
    [string]$Out = "$PSScriptRoot\..\..\local\Pulse+Single\Pulse+.exe",
    [string]$Icon = "$PSScriptRoot\pulse.ico"  # made by make_icon.py
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

    # the zip with forward slashes in its entries (Compress-Archive of Windows PowerShell 5.1 writes backslashes)
    $zip = "$stage\payload.zip"
    [IO.Compression.ZipFile]::CreateFromDirectory("$stage\pkg", $zip)
    $build = (Get-FileHash -Algorithm SHA256 $zip).Hash.Substring(0, 16).ToLower()

    $src = Get-Content "$PSScriptRoot\Launcher.cs" -Raw -Encoding UTF8
    $src = $src.Replace("__BUILD__", $build)
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
