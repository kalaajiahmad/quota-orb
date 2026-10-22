param([string]$Port, [ValidateSet('codex','claude')][string]$Provider)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run Run Quota Orb.cmd first.' }
$runtimePath = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$existingMutex = $null
try { $existingMutex = [System.Threading.Mutex]::OpenExisting('Local\QuotaOrbBridge') }
catch [System.Threading.WaitHandleCannotBeOpenedException] { }
if ($existingMutex) {
    $existingMutex.Dispose()
    Write-Host 'Quota Orb is already running. Look for its notification icon, including under the taskbar overflow arrow.'
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
$launchedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
$monitorProcess = Start-Process -FilePath $pythonPath -ArgumentList $launchArguments -WorkingDirectory $projectRoot `
    -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'stdout.log') `
    -RedirectStandardError (Join-Path $runtimePath 'stderr.log') -PassThru
$deadline = (Get-Date).AddSeconds(25)
while ((Get-Date) -lt $deadline) {
    if ($monitorProcess.HasExited) { throw 'Quota Orb exited. Open setup or inspect the local bridge log.' }
    $statusFile = Join-Path $runtimePath 'status.json'
    if (Test-Path -LiteralPath $statusFile) {
        try {
            $status = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
            if ($status.running -and $status.tray_registered -and $status.updated_at -ge $launchedAt) {
                Write-Host 'Quota Orb is running with a notification icon. Right-click it for status, Pause/Resume, or Quit. Check the taskbar overflow arrow.'
                return
            }
        } catch { } # Atomic replacement can coincide with this read; retry.
    }
    Start-Sleep -Milliseconds 250
}
Set-Content -LiteralPath (Join-Path $runtimePath 'stop') -Value 'stop' -Encoding ASCII
throw 'The visible monitor did not confirm startup. Shutdown requested; inspect the local bridge log.'
