@echo off
setlocal
where python >nul 2>nul
if errorlevel 1 (
    echo Python not found in PATH
    exit /b 1
)
for /f "tokens=2 delims=." %%a in ('python --version 2^>^&1') do set "pyver=%%a"
if %pyver% LSS 9 (
    echo Python 3.9+ required
    exit /b 1
)
python make_icon.py
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
python -m pip install pyinstaller
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Keypointer --icon keypointer.ico main.py
if errorlevel 1 exit /b 1
echo Build complete: dist\Keypointer.exe
endlocal