$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogsDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogsDir "telegram_ai_bot.pid"

function Get-BotProcesses {
    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine `
            -and $_.CommandLine.Contains("telegram_ai_bot.py") `
            -and $_.CommandLine.Contains($Root)
        }
}

$botProcesses = @(Get-BotProcesses)

if (-not (Test-Path $PidFile) -and $botProcesses.Count -eq 0) {
    Write-Host "PID file not found and no bot process is running."
    exit 0
}

if ($botProcesses.Count -eq 0) {
    $botPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if (-not $botPid) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "PID file was empty and has been removed."
        exit 0
    }

    $process = Get-Process -Id ([int]$botPid) -ErrorAction SilentlyContinue
    if (-not $process) {
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "Bot process was not found. Stale PID file has been removed."
        exit 0
    }

    $botProcesses = @($process)
}

foreach ($processInfo in $botProcesses) {
    $targetPid = if ($processInfo.ProcessId) { [int]$processInfo.ProcessId } else { [int]$processInfo.Id }
    Stop-Process -Id $targetPid -ErrorAction Stop
    Write-Host "Telegram bot stopped. PID: $targetPid" -ForegroundColor Green
}

Start-Sleep -Seconds 1
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
