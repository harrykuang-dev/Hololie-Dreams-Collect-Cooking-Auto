@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "outputs\kitchen-bot\启动独立版.pyw"
) else (
  echo Install the virtual environment and models first. See README.md.
  pause
)
