@echo off
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

chcp 65001 >nul
echo [Admin] Starting AI web control panel...
echo Keep this window open. Browser will open automatically.
echo Press F1 or click STOP in the web page to stop the script.
python "%~dp0tools\web_panel.py"
pause
