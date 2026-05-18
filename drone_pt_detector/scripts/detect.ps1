<# 
运行无人机 PT 模型检测。
该脚本负责确保虚拟环境存在，并把 PowerShell 参数转发给 src/drone_pt_detector.py detect。
#>
param(
    [string]$Source = "0",
    [string]$Model = "flying_objects_yolov8m",
    [double]$Conf = 0.25,
    [double]$Iou = 0.7,
    [int]$ImgSize = 960,
    [string]$Device = "",
    [string]$Classes = "",
    [switch]$DroneOnly,
    [switch]$Show,
    [switch]$SaveTxt,
    [switch]$SaveConf
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
    # 首次运行时自动创建本工作区 .venv，避免用户手动准备环境。
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "detect",
    "--source", $Source,
    "--model", $Model,
    "--conf", $Conf.ToString([Globalization.CultureInfo]::InvariantCulture),
    "--iou", $Iou.ToString([Globalization.CultureInfo]::InvariantCulture),
    "--imgsz", $ImgSize.ToString()
)

if ($Device) {
    $ArgsList += @("--device", $Device)
}
if ($Classes) {
    $ArgsList += @("--classes", $Classes)
}
if ($DroneOnly) {
    # DroneOnly 会在 Python 入口中展开为当前模型配置的无人机类别 ID。
    $ArgsList += "--drone-only"
}
if ($Show) {
    $ArgsList += "--show"
}
if ($SaveTxt) {
    $ArgsList += "--save-txt"
}
if ($SaveConf) {
    $ArgsList += "--save-conf"
}

& $Python @ArgsList
