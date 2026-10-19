param(
    [string]$PythonExe,
    [switch]$WithYolo,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

function Invoke-Python([string]$Executable, [string[]]$Prefix, [string[]]$Arguments) {
    & $Executable @Prefix @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE." }
}

if ($PythonExe) {
    if (-not [System.IO.Path]::IsPathRooted($PythonExe)) { $PythonExe = Join-Path $projectRoot $PythonExe }
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Python interpreter not found: $PythonExe" }
    $basePython = (Resolve-Path -LiteralPath $PythonExe).Path
    $prefix = @()
} else {
    $venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $basePython = $venvPython
        $prefix = @()
    } else {
        $venvDirectory = Join-Path $projectRoot '.venv'
        if (Test-Path -LiteralPath $venvDirectory) {
            throw "An existing .venv folder has no Python executable. It was left untouched; move or repair it yourself, then rerun setup."
        }
        $basePython = $null
        $prefix = @()
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            foreach ($version in @('3.12', '3.11')) {
                try {
                    $testMinor = & $launcher.Source "-$version" -c 'import sys; print(sys.version_info.minor)' 2>&1
                    if ($LASTEXITCODE -eq 0 -and "$testMinor" -match '^\d+$') {
                        $basePython = $launcher.Source
                        $prefix = @("-$version")
                        break
                    }
                } catch {}
            }
        }
        if (-not $basePython) {
            $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
            if ($pythonCommand) {
                $candidate = $pythonCommand.Source
                $version = & $candidate -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))' 2>$null
                if ($LASTEXITCODE -eq 0 -and $version -match '^3\.(11|12)$') { $basePython = $candidate }
            }
        }
        if (-not $basePython) {
            $winget = Get-Command winget -ErrorAction SilentlyContinue
            if ($winget) {
                $answer = Read-Host 'Python 3.12 is required. Install it from the official Python package through Windows Package Manager now? (y/N)'
                if ($answer -match '^(y|yes)$') {
                    & $winget.Source install --id Python.Python.3.12 --exact --source winget
                    if ($LASTEXITCODE -ne 0) { throw 'Python installation did not complete. Install Python 3.12 from https://www.python.org/downloads/ and rerun this script.' }
                    throw 'Python 3.12 was installed. Close and reopen PowerShell, then rerun setup_backend.ps1.'
                }
            }
            throw 'Python 3.11 or 3.12 was not found. Install 64-bit Python 3.12 from https://www.python.org/downloads/ and rerun this script. No project files were changed.'
        }
        $version = Invoke-Python $basePython $prefix @('-c', 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))')
        if ($version -notmatch '^3\.(11|12)$') { throw "Python 3.11 or 3.12 is required; found $version." }
        Invoke-Python $basePython $prefix @('-m', 'venv', (Join-Path $projectRoot '.venv'))
        $basePython = $venvPython
        $prefix = @()
    }
}

$version = Invoke-Python $basePython $prefix @('-c', 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))')
if ($version -notmatch '^3\.(11|12)$') { throw "Python 3.11 or 3.12 is required; found $version." }

if (-not $SkipInstall) {
    $requirements = if ($WithYolo) { 'requirements-yolo.txt' } else { 'requirements.txt' }
    Invoke-Python $basePython $prefix @('-m', 'pip', 'install', '-r', (Join-Path $projectRoot $requirements))
} else {
    Invoke-Python $basePython $prefix @('-c', 'import fastapi, multipart, PIL, pydantic, uvicorn')
    if ($WithYolo) { Invoke-Python $basePython $prefix @('-c', 'import ultralytics, torch') }
}

Write-Host "Backend setup is ready with Python $version at $basePython"
if (-not $WithYolo) { Write-Host 'YOLO is optional. Run .\setup_yolo.ps1 only when you want real image inference.' }
