@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Start.ps1" -Provider codex -ShowWindow
if errorlevel 1 (
    pause
    exit /b 1
)
