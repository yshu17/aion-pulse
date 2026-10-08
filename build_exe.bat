@echo off
rem Build AionChatWatcher.exe into this folder (next to config.json).
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed --name AionChatWatcher ^
  --distpath . --workpath build --specpath build ^
  main.py || goto :error
echo.
echo Done: %~dp0AionChatWatcher.exe
exit /b 0
:error
echo Build failed.
exit /b 1
