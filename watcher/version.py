"""Application name, version and the GitHub repository that publishes releases."""

APP_NAME = "Pulse"
VERSION = "1.2.0"
REPO = "yshu17/aion-pulse"


def build_label() -> str:
    """«» for the stable Pulse.exe, « (локальная)» for the test build Pulse-Local.exe that reads local data."""
    import sys
    from pathlib import Path

    frozen = getattr(sys, "frozen", False)
    return " (локальная)" if frozen and Path(sys.executable).stem.lower().endswith("-local") else ""
