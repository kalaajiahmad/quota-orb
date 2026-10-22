param([string]$Port, [ValidateSet('codex','claude')][string]$Provider)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\Setup.ps1 first.' }
$runtimePath = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$existingMutex = $null
try { $existingMutex = [System.Threading.Mutex]::OpenExisting('Local\QuotaOrbBridge') }
catch [System.Threading.WaitHandleCannotBeOpenedException] { }
if ($existingMutex) {
    $existingMutex.Dispose()
    Write-Host 'Quota Orb is already running. Status: .runtime\status.json.'
    return
}
$preferenceFile = Join-Path $runtimePath 'preferences.json'
if (-not $Provider -and (Test-Path -LiteralPath $preferenceFile)) {
    $preferences = Get-Content -LiteralPath $preferenceFile -Raw | ConvertFrom-Json
    if ($preferences.provider -in @('codex','claude')) { $Provider = $preferences.provider }
    if (-not $Port -and $preferences.port -match '^COM\d+$') { $Port = $preferences.port }
}
if (-not $Provider) { $Provider = 'codex' }
$launchArguments = @('-m', 'bridge', '--quiet', '--provider', $Provider)
if ($Port) {
    if ($Port -notmatch '^COM\d+$') { throw 'Port must look like COM4.' }
    $launchArguments += @('--port', $Port)
}
Start-Process -FilePath $pythonPath -ArgumentList $launchArguments -WorkingDirectory $projectRoot `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'stdout.log') `
    -RedirectStandardError (Join-Path $runtimePath 'stderr.log') | Out-Null
Write-Host 'Quota Orb launched. Status: .runtime\status.json. Stop: scripts\Stop.ps1.'
