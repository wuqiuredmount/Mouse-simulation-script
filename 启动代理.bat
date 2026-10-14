@echo off
cd /d "%~dp0"

fltmc >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

chcp 65001 >nul
echo [Admin] Starting AI agent daemon (keep this window open)...
echo It will handle all click/capture commands without further UAC prompts.
echo Press F1 or run agent_client quit to stop.
python "%~dp0tools\agent_daemon.py"
pause
