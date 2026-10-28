$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw 'Install Python 3.10+ from python.org with Tcl/Tk and PATH enabled, then run this launcher again.'
    }
    python -c "import sys, tkinter; assert sys.version_info >= (3,10)"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10+ with Tcl/Tk is required. Install it from python.org.' }
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}
& $pythonPath -m pip install --disable-pip-version-check -r requirements-bridge.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed. Check the network and retry.' }
& $pythonPath -m bridge.launch
if ($LASTEXITCODE -ne 0) { throw 'Quota Orb exited with an error.' }
