$ErrorActionPreference = 'Stop'
python tools/check_runtime.py
if ($LASTEXITCODE -ne 0) { throw 'Runtime/model verification failed' }
python -m PyInstaller --noconfirm --clean CookingAuto.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
$packagePath = Join-Path $PSScriptRoot 'dist/Collect-Cooking-Auto-v1.1.0'
foreach ($name in @('README.md','README.zh-TW.md','README.zh-CN.md','README.ja.md','README.ko.md','README.id.md','models-manifest.json')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination $packagePath -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs') -Destination $packagePath -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'third-party') -Destination $packagePath -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'docs/packaged-runtime.json') -Destination (Join-Path $packagePath 'runtime-manifest.json') -Force
Write-Host "Built: $((Resolve-Path 'dist/Collect-Cooking-Auto-v1.1.0/Collect-Cooking-Auto-v1.1.0.exe').Path)"
