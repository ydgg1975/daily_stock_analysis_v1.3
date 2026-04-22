param(
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BotScript = Join-Path $Root "scripts\telegram_ai_bot.py"
$LogsDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogsDir "telegram_ai_bot.pid"
$OutLog = Join-Path $LogsDir "telegram_ai_bot.out.log"
$ErrLog = Join-Path $LogsDir "telegram_ai_bot.err.log"

function Get-BotProcessInfos {
    return Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.CommandLine `
            -and $_.CommandLine.Contains("telegram_ai_bot.py") `
            -and $_.CommandLine.Contains($Root)
        }
}

function Get-BotRootProcessInfo {
    $infos = @(Get-BotProcessInfos)
    if ($infos.Count -eq 0) {
        return $null
    }

    $ids = @($infos | ForEach-Object { [int]$_.ProcessId })
    $root = $infos |
        Where-Object { $ids -notcontains ([int]$_.ParentProcessId) } |
        Select-Object -First 1
    if ($root) {
        return $root
    }

    return $infos[0]
}

function Get-ExistingBotProcess {
    if (Test-Path $PidFile) {
        $existingPid = (Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
        if ($existingPid) {
            $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$existingPid" -ErrorAction SilentlyContinue
            if (
                $processInfo `
                -and $processInfo.CommandLine `
                -and $processInfo.CommandLine.Contains("telegram_ai_bot.py") `
                -and $processInfo.CommandLine.Contains($Root)
            ) {
                return Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
            }
        }
    }

    $candidate = Get-BotRootProcessInfo

    if ($candidate) {
        return Get-Process -Id ([int]$candidate.ProcessId) -ErrorAction SilentlyContinue
    }

    return $null
}

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Host "Missing .env. Please configure Telegram and AI keys in the project root first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $Python)) {
    Write-Host "Missing virtualenv Python: $Python" -ForegroundColor Red
    Write-Host "Run in the project root first: python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt"
    exit 1
}

$existing = Get-ExistingBotProcess
if ($existing) {
    $botInfos = @(Get-BotProcessInfos)
    $relatedIds = @([int]$existing.Id)
    $relatedIds += @(
        $botInfos |
            Where-Object { [int]$_.ParentProcessId -eq [int]$existing.Id } |
            ForEach-Object { [int]$_.ProcessId }
    )
    $duplicates = @($botInfos | Where-Object { $relatedIds -notcontains ([int]$_.ProcessId) })
    foreach ($duplicate in $duplicates) {
        Stop-Process -Id ([int]$duplicate.ProcessId) -ErrorAction SilentlyContinue
        Write-Host "Stopped duplicate Telegram bot process. PID: $($duplicate.ProcessId)" -ForegroundColor Yellow
    }
    Set-Content -Path $PidFile -Value $existing.Id -Encoding ASCII
    Write-Host "Telegram bot is already running. PID: $($existing.Id)" -ForegroundColor Green
    Write-Host "Log: $ErrLog"
    exit 0
}

if ($Foreground) {
    Write-Host "Starting Telegram bot in foreground mode. Closing this window will stop it." -ForegroundColor Yellow
    & $Python -u $BotScript
    exit $LASTEXITCODE
}

$process = Start-Process `
    -FilePath $Python `
    -ArgumentList @("-u", $BotScript) `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII
Start-Sleep -Seconds 3

$running = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
if (-not $running) {
    Write-Host "Telegram bot failed to start. Recent error log:" -ForegroundColor Red
    if (Test-Path $ErrLog) {
        Get-Content $ErrLog -Tail 40
    }
    exit 1
}

Write-Host "Telegram bot started in background. PID: $($process.Id)" -ForegroundColor Green
Write-Host "You can close this window; the bot will keep running."
Write-Host "Error log: $ErrLog"
