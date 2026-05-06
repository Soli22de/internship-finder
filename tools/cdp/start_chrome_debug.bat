@echo off
echo Starting Chrome in Remote Debugging Mode (Port 9222)
echo Please ensure no other Chrome instances are running.

set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
set USER_DATA_DIR="C:\chrome_debug_profile"

if not exist %CHROME_PATH% (
    echo Chrome not found at %CHROME_PATH%
    echo Please modify the script with your actual Chrome path.
    pause
    exit /b
)

echo User Data Directory: %USER_DATA_DIR%
%CHROME_PATH% --remote-debugging-port=9222 --user-data-dir=%USER_DATA_DIR%

echo Chrome started. Please manually log in and navigate to target sites.
pause
