@echo off
echo Building Single Executable File (No External Dependencies)
echo ==========================================================

echo Step 1: Clean previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo Step 2: Building single executable (this may take 5-10 minutes)...
pyinstaller --onefile --windowed --name="RCWS_7.62_12.7" ^
    --add-data="rangetable.csv;." ^
    --add-data="rangetableNSVT.csv;." ^
    --add-data="config.ini;." ^
    --add-data="default.ini;." ^
    --add-data="pre_registered_targets.json;." ^
    --add-data="assets;assets" ^
    --add-data="api;api" ^
    --add-data="utils;utils" ^
    --add-data="qt_utils;qt_utils" ^
    --add-data="TinyFrame.dll;." ^
    --add-data="TinyFrame.so;." ^
    --add-data="tinyframe_python.dll;." ^
    --hidden-import=win32gui --hidden-import=win32api --hidden-import=win32ui --hidden-import=win32con ^
    --hidden-import=requests --hidden-import=numba --hidden-import=pygame --hidden-import=PyQt5.QtWidgets ^
    --hidden-import=numpy --hidden-import=cv2 --hidden-import=vlc --hidden-import=pandas ^
    --hidden-import=configparser_crypt --hidden-import=pydash --hidden-import=ctypes ^
    --hidden-import=threading --hidden-import=json --hidden-import=hashlib --hidden-import=math ^
    --hidden-import=serial --hidden-import=serial.tools.list_ports ^
    --hidden-import=tinyframe --hidden-import=utils.tinyframe ^
    --icon="assets\logo.png" ^
    "Main.py"

if exist "dist\RCWS_7.62_12.7.exe" (
    echo.
    echo ✓ SUCCESS! Single executable created: dist\RCWS_7.62_12.7.exe
    echo.
    echo File size:
    for %%I in ("dist\RCWS_7.62_12.7.exe") do echo   RCWS_7.62_12.7.exe: %%~zI bytes
    echo.
    echo ✓ This single file contains EVERYTHING - no other files needed!
    echo ✓ Just copy RCWS_7.62_12.7.exe to any Windows machine and run it.
    echo.
    echo Note: First startup may be slower as it extracts files to temp folder.
) else (
    echo ✗ Build failed! Check errors above.
)

pause
explorer "dist"