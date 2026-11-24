"""The build stamp stays on this machine: a local build is stamped, the users' Pulse+.exe never is (TG task 27).

tools/single_exe/build_single_exe.ps1 refuses to pack a build marked with stamped.txt (the developer's tree stamps its local builds). Windows PowerShell 5.1 reads the scripts by code page,
so they stay ASCII.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "tools" / "build_pulse_plus.ps1"
SINGLE = ROOT / "tools" / "single_exe" / "build_single_exe.ps1"


def test_scripts_are_ascii():
    for script in (BUILD, SINGLE):
        script.read_bytes().decode("ascii")


def test_single_exe_never_packs_a_stamped_build():
    text = SINGLE.read_text(encoding="ascii")
    guard = text.index('"stamped.txt"')
    assert "throw" in text[guard:guard + 200]
    assert guard < text.index('Copy-Item $app "$stage\\pkg\\Pulse+Local.exe"')
