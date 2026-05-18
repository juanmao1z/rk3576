<# 导出无人机 PT 模型到 ONNX、RKNN 或其他 Ultralytics 支持格式。 #>

param(
    [string]$Model = "flying_objects_yolov8m",
    [ValidateSet("onnx", "rknn", "engine", "openvino")]
    [string]$Format = "onnx",
    [int]$ImgSize = 960,
    [string]$Device = "",
    [string]$RknnTarget = "rk3576"
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
    # 导出依赖 Ultralytics 环境，缺少 .venv 时先初始化环境。
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "export",
    "--model", $Model,
    "--format", $Format,
    "--imgsz", $ImgSize.ToString(),
    "--rknn-target", $RknnTarget
)

if ($Device) {
    $ArgsList += @("--device", $Device)
}

& $Python @ArgsList
