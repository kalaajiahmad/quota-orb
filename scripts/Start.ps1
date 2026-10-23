param([string]$Port, [ValidateSet('codex','claude')][string]$Provider, [switch]$ShowWindow)
$ErrorActionPreference = 'Stop'
if ($Port -and $Port -notmatch '^COM\d+$') { throw 'Port must look like COM4.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run Run Quota Orb.cmd first.' }
$runtimePath = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$existingMutex = $null
try { $existingMutex = [System.Threading.Mutex]::OpenExisting('Local\QuotaOrbBridge') }
catch [System.Threading.WaitHandleCannotBeOpenedException] { }
$alreadyRunning = $null -ne $existingMutex
if ($existingMutex) { $existingMutex.Dispose() }
$preferenceFile = Join-Path $runtimePath 'preferences.json'
if (-not $alreadyRunning -and -not $Provider -and (Test-Path -LiteralPath $preferenceFile)) {
    $preferences = Get-Content -LiteralPath $preferenceFile -Raw | ConvertFrom-Json
    if ($preferences.provider -in @('codex','claude')) { $Provider = $preferences.provider }
    if (-not $Port -and $preferences.port -match '^COM\d+$') { $Port = $preferences.port }
}
if (-not $Provider) { $Provider = 'codex' }
$launchArguments = @('-m', 'bridge', '--quiet', '--provider', $Provider)
if ($Port) {
    $launchArguments += @('--port', $Port)
}
$launchedAt = 0
$monitorProcess = $null
if (-not $alreadyRunning) {
    $launchedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
    $monitorProcess = Start-Process -FilePath $pythonPath -ArgumentList $launchArguments -WorkingDirectory $projectRoot `
        -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimePath 'stdout.log') `
        -RedirectStandardError (Join-Path $runtimePath 'stderr.log') -PassThru
}
$deadline = (Get-Date).AddSeconds($(if ($alreadyRunning) { 6 } else { 25 }))
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($monitorProcess -and $monitorProcess.HasExited) { throw 'Quota Orb exited. Open setup or inspect the local bridge log.' }
    $statusFile = Join-Path $runtimePath 'status.json'
    if (Test-Path -LiteralPath $statusFile) {
        try {
            $status = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
            $age = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0 - $status.updated_at
            if ($status.running -and $status.tray_registered -and $status.updated_at -ge $launchedAt -and
                $age -ge -5 -and $age -le 6 -and $status.pid -gt 0 -and
                (Get-Process -Id $status.pid -ErrorAction SilentlyContinue)) { $ready = $true }
        } catch { } # Atomic replacement can coincide with this read; retry.
    }
    if ($ready) { break }
    Start-Sleep -Milliseconds 250
}
if (-not $ready) {
    if ($monitorProcess) {
        Set-Content -LiteralPath (Join-Path $runtimePath 'stop') -Value 'stop' -Encoding ASCII
        throw 'The visible monitor did not confirm startup. Shutdown requested; inspect the local bridge log.'
    }
    throw 'The existing monitor is not responding with a registered icon. Inspect the local bridge log before restarting it.'
}
if ($ShowWindow) {
    # The running monitor owns desktop launches and focuses its existing window.
    Set-Content -LiteralPath (Join-Path $runtimePath 'open-display') -Value 'show' -Encoding ASCII
    Write-Host 'Quota Orb is running with a notification icon. Opening its desktop window; close it to keep monitoring in the tray.'
} else {
    Write-Host 'Quota Orb is running with a notification icon. Click it to open the desktop window; check the taskbar overflow arrow.'
}
