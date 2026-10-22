param([Parameter(Mandatory=$true)][ValidatePattern('^COM\d+$')][string]$Port)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& (Join-Path $PSScriptRoot 'Stop.ps1')
& (Join-Path $PSScriptRoot 'Setup.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Firmware setup failed.' }
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$esptoolPath = Join-Path $projectRoot '.pio\core\packages\tool-esptoolpy\esptool.py'
$flashInfo = (& $pythonPath $esptoolPath --chip esp32 --port $Port flash_id 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $flashInfo -notmatch 'Detected flash size:\s*8MB') {
    throw 'This supplied target requires a verified 8 MB ESP32 board. Detection failed or the capacity differs. No erase/upload was performed.'
}
$backupFolder = Join-Path $projectRoot 'backups'
New-Item -ItemType Directory -Force -Path $backupFolder | Out-Null
$backupPath = Join-Path $backupFolder ('before-quota-orb-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bin')
& $pythonPath $esptoolPath --chip esp32 --port $Port --baud 460800 read_flash 0x0 0x800000 $backupPath
if ($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $backupPath).Length -ne 8388608) {
    throw 'Full flash backup failed. No upload was performed.'
}
$digest = (Get-FileHash -LiteralPath $backupPath -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($backupPath + '.sha256') -Value $digest -Encoding ASCII
& $pythonPath -m platformio run --target upload --upload-port $Port
if ($LASTEXITCODE -ne 0) { throw 'Upload failed. The previous firmware backup is in the private backups folder.' }
Write-Host 'Firmware uploaded. Return to the wizard and check USB again. Keep the backup private.'
Read-Host 'Press Enter to close'
