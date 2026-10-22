$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$startupPath = [Environment]::GetFolderPath('Startup')
$launcherPath = Join-Path $startupPath 'Quota Orb.vbs'
$scriptPath = Join-Path $PSScriptRoot 'Start.ps1'
$command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $scriptPath + '"'
$escaped = $command.Replace('"', '""')
$content = 'CreateObject("WScript.Shell").Run "' + $escaped + '", 0, False'
Set-Content -LiteralPath $launcherPath -Value $content -Encoding Unicode
Write-Host "Enabled for your Windows login: $launcherPath"
