$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$modelDirectory = Join-Path $projectRoot 'backend\models'
$modelPath = Join-Path $modelDirectory 'yolo11n.pt'
if (Test-Path -LiteralPath $modelPath -PathType Leaf) {
    throw "Model already exists and was not overwritten: $modelPath. Set CARBOSYNC_YOLO_MODEL_PATH in .env to select it."
}
& (Join-Path $projectRoot 'setup_backend.ps1') -WithYolo
New-Item -ItemType Directory -Force -Path $modelDirectory | Out-Null
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $modelDirectory
try {
    & $python -c "from ultralytics import YOLO; YOLO('yolo11n.pt'); print('Downloaded YOLO11n weights to the backend/models folder.')"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
        throw 'Model download/initialization failed. Check network access to GitHub releases and rerun after resolving the reported issue.'
    }
} finally { Pop-Location }
Write-Host "YOLO11n installed at $modelPath. This is a one-time explicit download; the server never downloads weights at startup."
Write-Host 'The model is a COCO pretrained nano detector. It recognizes bicycle, car, motorcycle, bus, and truck among COCO classes.'
