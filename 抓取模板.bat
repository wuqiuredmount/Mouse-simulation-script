@echo off
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

chcp 65001 >nul
echo [Admin] Template grabber. Switch to the game first, then select buttons.
python "%~dp0tools\grab_template.py" --preset
pause
