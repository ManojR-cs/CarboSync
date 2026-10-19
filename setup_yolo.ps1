param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$modelDirectory = Join-Path $projectRoot 'backend\models'
$modelPath = Join-Path $modelDirectory 'yolo11n.pt'
$rootModelPath = Join-Path $projectRoot 'yolo11n.pt'

New-Item -ItemType Directory -Force -Path $modelDirectory | Out-Null

# 1. Ensure backend dependencies with YOLO are installed
& (Join-Path $projectRoot 'setup_backend.ps1') -WithYolo

# 2. Resolve Python executable (prefer .venv, fallback to system Python 3.11/3.12)
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $python = $pythonCmd.Source
    } else {
        throw 'Python executable not found. Run setup_backend.ps1 first.'
    }
}

# 3. Handle model weights: verify existing or copy from root or download
if ((Test-Path -LiteralPath $modelPath -PathType Leaf) -and (-not $Force)) {
    Write-Host "Model weights already present at $modelPath."
} elseif ((Test-Path -LiteralPath $rootModelPath -PathType Leaf) -and (-not $Force)) {
    Copy-Item -LiteralPath $rootModelPath -Destination $modelPath -Force
    Write-Host "Copied existing yolo11n.pt from project root to $modelPath."
} else {
    Push-Location -LiteralPath $modelDirectory
    try {
        & $python -c "from ultralytics import YOLO; YOLO('yolo11n.pt'); print('Downloaded YOLO11n weights to backend/models.')"
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
            throw 'Model download/initialization failed. Check network access to GitHub releases and rerun after resolving the reported issue.'
        }
    } finally { Pop-Location }
}

# 4. Verify model loads cleanly with Ultralytics
& $python -c "from ultralytics import YOLO; m = YOLO(r'$modelPath'); print(f'Successfully loaded YOLO model with {len(m.names)} classes.')"
if ($LASTEXITCODE -ne 0) {
    throw "Model verification failed for $modelPath."
}

Write-Host "YOLO11n is ready at $modelPath."
Write-Host 'The model is a COCO pretrained nano detector recognizing bicycle, car, motorcycle, bus, and truck.'

