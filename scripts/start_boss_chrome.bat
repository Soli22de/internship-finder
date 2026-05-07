@echo off
echo Starting Chrome for BOSS crawler...
echo Login to BOSS after Chrome opens.
echo Keep this window running in background.
echo.
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --remote-debugging-port=9222 ^
    --user-data-dir="%~dp0..\chrome_dev_profile\boss" ^
    --no-first-run ^
    --no-default-browser-check ^
    "https://www.zhipin.com/web/user/?ka=header-login"
echo Chrome started on port 9222.
echo.
echo TO LOGIN: Scan QR code with BOSS app
echo TO VERIFY: http://localhost:9222/json/version
echo.
pause
