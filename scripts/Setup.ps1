$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m platformio run
if ($LASTEXITCODE -ne 0) { throw 'Firmware compilation failed.' }
Write-Host 'Setup complete. See README.md before flashing a board.'
