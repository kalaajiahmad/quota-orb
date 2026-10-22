$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$OutputEncoding = New-Object System.Text.UTF8Encoding $false
$payload = [Console]::In.ReadToEnd()
Push-Location -LiteralPath $projectRoot
try { $payload | & $pythonPath -m bridge.claude }
finally { Pop-Location }
