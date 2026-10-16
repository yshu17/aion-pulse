@echo off
rem Build Pulse.exe into this folder (next to config.json).
cd /d "%~dp0"
rem install from the pinned requirements.txt only when a build package is missing (no network on a normal build)
python -c "import PyInstaller, PIL, pytest" 2>nul || python -m pip install -r requirements.txt || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Pulse --icon "%~dp0client_extract\raw\aion_client_icon.ico" ^
  --distpath . --workpath build --specpath build ^
  --add-data "%~dp0data;data" ^
  --exclude-module numpy --exclude-module PIL.ImageQt --exclude-module PyQt5 --exclude-module PyQt6 ^
  --exclude-module PySide6 --exclude-module matplotlib --exclude-module IPython ^
  main.py || goto :error
echo.
echo Done: %~dp0Pulse.exe
exit /b 0
:error
echo Build failed.
exit /b 1
