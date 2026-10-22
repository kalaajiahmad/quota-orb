$ErrorActionPreference = 'Stop'
$launcherPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Quota Orb.vbs'
if (Test-Path -LiteralPath $launcherPath) { Remove-Item -LiteralPath $launcherPath }
Write-Host 'Quota Orb login startup disabled. The current bridge is unaffected.'
