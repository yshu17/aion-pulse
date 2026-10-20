@echo off
rem pulse-core.exe: the portable core alone (no window, no Tk, no Pillow), JSON over stdin / stdout - core\API.md.
rem The launcher starts it as a sidecar process and passes the data folder in «data.open».
rem Output: build\core\pulse-core.exe, then a self-check with JSON requests (tools\check_core_exe.py).
cd /d "%~dp0"
python -c "import PyInstaller" 2>nul || python -m pip install pyinstaller || goto :error
python -m PyInstaller --noconfirm --clean --onefile --console --name pulse-core ^
  --distpath "%~dp0build\core" --workpath "%TEMP%\pulse-core-work" --specpath "%TEMP%\pulse-core-work" ^
  --exclude-module tkinter --exclude-module PIL --exclude-module numpy --exclude-module matplotlib ^
  --exclude-module IPython --exclude-module _zstd --exclude-module compression.zstd ^
  pulse_core.py || goto :error
python tools\check_core_exe.py "%~dp0build\core\pulse-core.exe" "%~dp0data" || goto :error
echo.
echo Done: %~dp0build\core\pulse-core.exe
exit /b 0
:error
echo Build failed.
exit /b 1
