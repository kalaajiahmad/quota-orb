$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $projectRoot '.runtime'
$processFile = Join-Path $runtimePath 'process.json'
if (-not (Test-Path -LiteralPath $processFile)) {
    Write-Host 'No running bridge recorded.'
    return
}
Set-Content -LiteralPath (Join-Path $runtimePath 'stop') -Value 'stop' -Encoding ASCII
$deadline = (Get-Date).AddSeconds(36)
while ((Test-Path -LiteralPath $processFile) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
if (Test-Path -LiteralPath $processFile) {
    throw 'The bridge has not acknowledged shutdown. Inspect .runtime\bridge.log.'
}
Write-Host 'Quota Orb stopped. The OLED shows USB OFFLINE within six seconds.'
