"""Alert sound."""

import ctypes
import os
import winsound
from pathlib import Path

_BEEP_FILES = ("Windows Exclamation.wav", "Windows Background.wav", "Windows Ding.wav")


def default_media_dir() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Media"


def system_sounds(media_dir: Path | None = None) -> list[Path]:
    """WAV files shipped with Windows (Alarm01.wav, Ring01.wav, ...), sorted by name."""
    folder = default_media_dir() if media_dir is None else media_dir
    try:
        return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".wav")
    except OSError:
        return []


def default_beep_path(media_dir: Path | None = None) -> str | None:
    """WAV used for «Системный сигнал»: a file (unlike MessageBeep) follows the volume slider."""
    folder = default_media_dir() if media_dir is None else media_dir
    for name in _BEEP_FILES:
        if (folder / name).is_file():
            return str(folder / name)
    return None


def _wave_out_set_volume(value: int) -> None:
    """Volume of this program's own sounds (Windows mixer: per-application)."""
    try:
        ctypes.windll.winmm.waveOutSetVolume(None, ctypes.c_uint32(value))
    except (AttributeError, OSError):
        pass


class Notifier:
    def __init__(self, sound_path: str | None = None, volume: int = 100) -> None:
        self.sound_path = sound_path or ""
        self.volume = 100
        self.set_volume(volume)

    def set_volume(self, percent: float) -> None:
        """0..100 %, applied to both channels."""
        self.volume = max(0, min(100, int(round(percent))))
        level = 0xFFFF * self.volume // 100
        _wave_out_set_volume((level << 16) | level)

    def _file(self) -> str | None:
        if self.sound_path and os.path.isfile(self.sound_path):
            return self.sound_path
        if not self.sound_path:
            return default_beep_path()
        return None

    def play(self) -> None:
        """Play the WAV file (or the system one), else the Windows exclamation beep. Never blocks."""
        path = self._file()
        if path:
            try:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except RuntimeError:
                pass
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    def start_loop(self) -> bool:
        """Loop the WAV file until stop(). False if there is no playable file (caller repeats play())."""
        path = self._file()
        if not path:
            return False
        try:
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        except RuntimeError:
            return False
        return True

    def stop(self) -> None:
        """Silence any sound started by this process."""
        winsound.PlaySound(None, 0)
