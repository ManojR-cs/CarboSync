param(
    [string]$PythonExe,
    [switch]$WithYolo,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        $PythonExe = $venvPython
    }
    else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($null -eq $pythonCommand) {
            throw "Python 3.11 or 3.12 was not found. Install 64-bit Python and retry."
        }
        $basePython = $pythonCommand.Source
        $versionText = & $basePython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        if ($LASTEXITCODE -ne 0) { throw "Could not query the selected Python interpreter." }
        if ($versionText -notmatch '^3\.(11|12)$') {
            throw "Python 3.11 or 3.12 is required; found $versionText."
        }
        $venvRoot = Join-Path $projectRoot ".venv"
        & $basePython -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) { throw "Virtual-environment creation failed." }
        $PythonExe = $venvPython
    }
}
elseif (-not [System.IO.Path]::IsPathRooted($PythonExe)) {
    $PythonExe = Join-Path $projectRoot $PythonExe
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python interpreter not found: $PythonExe"
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$versionText = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { throw "Could not query the selected Python interpreter." }
if ($versionText -notmatch '^3\.(11|12)$') {
    throw "Python 3.11 or 3.12 is required; found $versionText."
}

if (-not $SkipInstall) {
    $requirementsFile = if ($WithYolo) { "requirements-yolo.txt" } else { "requirements.txt" }
    & $PythonExe -m pip install -r (Join-Path $projectRoot $requirementsFile)
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed; see pip output above." }
}
else {
    & $PythonExe -c "import fastapi, multipart, PIL, pydantic, uvicorn"
    if ($LASTEXITCODE -ne 0) { throw "The selected interpreter is missing a core backend dependency." }
    if ($WithYolo) {
        & $PythonExe -c "import ultralytics, torch"
        if ($LASTEXITCODE -ne 0) { throw "-WithYolo -SkipInstall requires an already configured Ultralytics/PyTorch runtime." }
    }
}

Write-Host "Backend setup is ready with Python $versionText at $PythonExe"
if (-not $WithYolo) {
    Write-Host "YOLO was not installed by this command. Use -WithYolo only when needed; weights are configured separately."
}
