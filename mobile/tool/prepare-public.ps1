$ErrorActionPreference='Stop'
$mobileRoot=Split-Path $PSScriptRoot -Parent
$assets=Join-Path $mobileRoot '.native\public-assets\private'
New-Item -ItemType Directory -Force $assets | Out-Null
$model=Join-Path $assets 'yolox_nano.onnx'
if(!(Test-Path -LiteralPath $model)){
    Invoke-WebRequest 'https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx' -OutFile $model
}
if((Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash -ne 'C789161ED43C8269FCD4E67C67EEEB4E80C622DA2EB296A20BC6007BD18A0B7D'){
    throw '公开模型 SHA-256 不匹配，停止构建。'
}
$files=@(Get-ChildItem (Split-Path $assets -Parent) -File -Recurse)
if($files.Count -ne 1 -or $files[0].FullName -ne $model){throw '公开资源目录包含非预期文件，拒绝打包。'}
Write-Host '公开资源已准备：仅官方 YOLOX 模型，不含个人标定或图片。'
