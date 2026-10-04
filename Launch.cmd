@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "gui.py"
) else (
  echo Install the virtual environment and models first. See README.md.
  pause
)
