<# 评估无人机 PT 模型在指定 YOLO 数据集上的指标。 #>

param(
    [Parameter(Mandatory = $true)]
    [string]$Data,
    [string]$Model = "flying_objects_yolov8m",
    [int]$ImgSize = 640,
    [int]$Batch = 8,
    [string]$Device = "",
    [string]$Classes = "",
    [switch]$DroneOnly
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
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "val",
    "--data", $Data,
    "--model", $Model,
    "--imgsz", $ImgSize.ToString(),
    "--batch", $Batch.ToString(),
    "--exist-ok"
)

if ($Device) {
    $ArgsList += @("--device", $Device)
}
if ($Classes) {
    $ArgsList += @("--classes", $Classes)
}
if ($DroneOnly) {
    # DroneOnly 会把评估类别限制到模型注册表里的无人机类别 ID。
    $ArgsList += "--drone-only"
}

& $Python @ArgsList
