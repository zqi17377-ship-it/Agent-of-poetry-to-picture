$ErrorActionPreference = 'Stop'
$studioRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $studioRoot
New-Item -ItemType Directory -Path '.tmp' -Force | Out-Null
$env:TEMP = Join-Path $studioRoot '.tmp'
$env:TMP = $env:TEMP
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundledPython) { $studioPython = $bundledPython } else { $studioPython = 'python' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    & $studioPython -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed. Python 3.11+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'pip setup failed.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.lock --cache-dir .tmp/pip-cache
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
try {
    & npm.cmd ci --no-audit --no-fund --cache ../.tmp/npm-cache
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Node.js 24+ is recommended.' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
Write-Output 'Setup complete. Run 启动.cmd to open the studio.'
