$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

try {
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $hasYolo = (Test-Path (Join-Path $projectRoot 'backend\models\yolo11n.pt')) -or (Test-Path (Join-Path $projectRoot 'yolo11n.pt'))
        $setupArgs = if ($hasYolo) { @('-WithYolo') } else { @() }
        & (Join-Path $projectRoot 'setup_backend.ps1') @setupArgs
    }

    $envFile = Join-Path $projectRoot '.env'
    if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
        Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envFile
        Write-Host 'Created .env from the safe example. Review it any time; existing settings are never overwritten.'
    }
    foreach ($line in Get-Content -LiteralPath $envFile -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $separator = $trimmed.IndexOf('=')
        if ($separator -lt 1) { continue }
        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
    if (-not (Select-String -LiteralPath $envFile -Pattern '^\s*CARBOSYNC_SERVE_FRONTEND\s*=' -Quiet)) {
        $env:CARBOSYNC_SERVE_FRONTEND = '1'
    }
    $port = if ($env:CARBOSYNC_PORT -match '^\d+$') { [int]$env:CARBOSYNC_PORT } else { 8001 }

    try {
        $existing = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
        if ($existing.status -eq 'healthy') { throw "A CarboSync-compatible server already answers on port $port. Stop it before launching another instance." }
    } catch {
        if ($_.Exception.Message -like 'A CarboSync-compatible server already answers*') { throw }
    }

    $stdoutPath = Join-Path $projectRoot 'backend.stdout.log'
    $stderrPath = Join-Path $projectRoot 'backend.stderr.log'
    $server = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',"$port") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        if ($server.HasExited) { throw "Backend exited during startup (code $($server.ExitCode)). Check backend.stderr.log, Python dependencies, and whether port $port is already in use." }
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 2
            if ($response.status -eq 'healthy') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw "Backend did not become ready at http://127.0.0.1:$port. Check port conflicts and backend.stderr.log." }
    Write-Host "CarboSync is running at http://127.0.0.1:$port/"
    Write-Host 'Health: /health   API docs: /docs   Close this PowerShell window to stop the server.'
    Start-Process "http://127.0.0.1:$port/"
    Wait-Process -Id $server.Id
} catch {
    Write-Error $_
    exit 1
} finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue }
}
