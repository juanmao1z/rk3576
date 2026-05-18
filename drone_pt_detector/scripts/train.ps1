<# 使用指定 YOLO 数据集继续训练无人机检测模型。 #>

param(
    [Parameter(Mandatory = $true)]
    [string]$Data,
    [string]$Model = "flying_objects_yolov8m",
    [int]$Epochs = 100,
    [int]$ImgSize = 960,
    [int]$Batch = 8,
    [string]$Device = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Script = Join-Path $Root "src\drone_pt_detector.py"

if (-not (Test-Path $Python)) {
    # 训练命令依赖 Ultralytics，缺少 .venv 时先初始化环境。
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "train",
    "--data", $Data,
    "--model", $Model,
    "--epochs", $Epochs.ToString(),
    "--imgsz", $ImgSize.ToString(),
    "--batch", $Batch.ToString()
)

if ($Device) {
    $ArgsList += @("--device", $Device)
}

& $Python @ArgsList
