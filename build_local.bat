@echo off
rem Test build with the NPC / Bestiary tab: local\Pulse-Local\Pulse-Local.exe. It reads the data from local\bestiary
rem (not bundled, not in the repository). The stable Pulse.exe comes from build_exe.bat and has no such data.
rem One folder instead of one file: the program starts at once instead of unpacking ~100 MB on every launch.
cd /d "%~dp0"
python -c "import PyInstaller, PIL" 2>nul || python -m pip install -r requirements.txt || goto :error
if not exist "local\bestiary\npcs.sqlite" python tools\build_bestiary_index.py || goto :error
python -m PyInstaller --noconfirm --clean --onedir --windowed --name Pulse-Local ^
  --icon "%~dp0data\ui\bestiary_app.ico" ^
  --distpath "%~dp0local" --workpath "%TEMP%\pulse-local-work" --specpath "%TEMP%\pulse-local-work" ^
  --add-data "%~dp0data;data" ^
  --exclude-module numpy --exclude-module PIL.ImageQt --exclude-module PyQt5 --exclude-module PyQt6 ^
  --exclude-module PySide6 --exclude-module matplotlib --exclude-module IPython ^
  --exclude-module PIL._avif --exclude-module PIL._webp --exclude-module PIL._imagingcms ^
  --exclude-module PIL._imagingft --exclude-module _zstd --exclude-module compression.zstd ^
  main.py || goto :error
echo.
echo Done: %~dp0local\Pulse-Local\Pulse-Local.exe  (data: %~dp0local\bestiary)
exit /b 0
:error
echo Build failed.
exit /b 1
