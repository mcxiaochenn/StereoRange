param([string]$Python)
$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path $PSScriptRoot -Parent
$repoRoot = Split-Path $mobileRoot -Parent
if (!$Python) { $Python = Join-Path $repoRoot '.venv\Scripts\python.exe' }
$model = Join-Path $repoRoot 'private-data\models\yolox_nano.onnx'
if (!(Test-Path $model)) { throw '缺少私有模型，请先取得 private-data 子模块访问权并初始化。' }
if ((Get-FileHash $model -Algorithm SHA256).Hash -ne 'C789161ED43C8269FCD4E67C67EEEB4E80C622DA2EB296A20BC6007BD18A0B7D') { throw 'YOLOX 模型 SHA-256 不匹配。' }
$assets = Join-Path $mobileRoot 'android\app\src\main\assets\private'
New-Item -ItemType Directory -Force $assets | Out-Null
Copy-Item -LiteralPath $model -Destination (Join-Path $assets 'yolox_nano.onnx')
& $Python "$repoRoot\calibrate.py" export-mobile --input "$repoRoot\private-data\calibration.npz" --output "$assets\calibration.json"
if ($LASTEXITCODE -ne 0) { throw '标定导出失败。' }
