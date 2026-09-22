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
for /f "delims=" %%d in ('python -c "import uiautomation,os;print(os.path.join(os.path.dirname(uiautomation.__file__),'bin'))"') do set "UA_BIN=%%d"
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed --name Keypointer --icon keypointer.ico --add-binary "%UA_BIN%\UIAutomationClient_VC140_X64.dll;uiautomation\bin" --add-binary "%UA_BIN%\UIAutomationClient_VC140_X86.dll;uiautomation\bin" main.py
if errorlevel 1 exit /b 1
echo Build complete: dist\Keypointer.exe
endlocal