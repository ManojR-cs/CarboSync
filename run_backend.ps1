param(
    [string]$PythonExe = ".\.venv\Scripts\python.exe",
    [string]$EnvFile = ".env",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot

if (-not [System.IO.Path]::IsPathRooted($PythonExe)) {
    $PythonExe = Join-Path $projectRoot $PythonExe
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python interpreter not found: $PythonExe. Run setup_backend.ps1 first or pass -PythonExe."
}

if (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
    $EnvFile = Join-Path $projectRoot $EnvFile
}
if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
    foreach ($line in Get-Content -LiteralPath $EnvFile -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $separator = $trimmed.IndexOf('=')
        if ($separator -lt 1) { continue }
        $name = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [Environment]::SetEnvironmentVariable($name, $value, 'Process')
    }
}

& $PythonExe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port $Port
