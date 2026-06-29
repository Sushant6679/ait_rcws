@echo off
setlocal

:: Change to the directory containing this batch file
cd /d %~dp0

:: Run the Python script
python Main.py

:: Pause if there was an error
if %ERRORLEVEL% neq 0 (
    echo An error occurred while running the script.
    pause
)

endlocal