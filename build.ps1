$ErrorActionPreference = 'Stop'
python tools/check_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime/model verification failed' }
python -m PyInstaller --noconfirm --clean CookingAuto.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
Write-Host "Built: $((Resolve-Path 'dist/Collect-Cooking-Auto-v0.2.0/Collect-Cooking-Auto-v0.2.0.exe').Path)"
