"""Alert sound."""

import os
import winsound


class Notifier:
    def __init__(self, sound_path: str | None = None) -> None:
        self.sound_path = sound_path or ""

    def play(self) -> None:
        """Play the WAV file if it exists, else the Windows exclamation sound. Never blocks."""
        if self.sound_path and os.path.isfile(self.sound_path):
            winsound.PlaySound(self.sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
