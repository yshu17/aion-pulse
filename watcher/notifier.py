"""Alert sound."""

import os
import winsound
from pathlib import Path


def default_media_dir() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Media"


def system_sounds(media_dir: Path | None = None) -> list[Path]:
    """WAV files shipped with Windows (Alarm01.wav, Ring01.wav, ...), sorted by name."""
    folder = default_media_dir() if media_dir is None else media_dir
    try:
        return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".wav")
    except OSError:
        return []


class Notifier:
    def __init__(self, sound_path: str | None = None) -> None:
        self.sound_path = sound_path or ""

    def _has_file(self) -> bool:
        return bool(self.sound_path) and os.path.isfile(self.sound_path)

    def play(self) -> None:
        """Play the WAV file if it exists, else (or if it fails) the Windows exclamation sound. Never blocks."""
        if self._has_file():
            try:
                winsound.PlaySound(self.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                return
            except RuntimeError:
                pass
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

    def start_loop(self) -> bool:
        """Loop the WAV file until stop(). False if there is no playable file (caller repeats play())."""
        if not self._has_file():
            return False
        try:
            winsound.PlaySound(
                self.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP
            )
        except RuntimeError:
            return False
        return True

    def stop(self) -> None:
        """Silence any sound started by this process."""
        winsound.PlaySound(None, 0)
