<# 下载内置无人机相关 PT 模型。 #>

param(
    [ValidateSet("flying_objects_yolov8m", "visdrone_yolov8n")]
    [string]$ModelName = "flying_objects_yolov8m",
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "py" }
$Script = Join-Path $Root "src\drone_pt_detector.py"

$ArgsList = @()
if (-not (Test-Path $VenvPython)) {
    # 尚未建虚拟环境时使用 py -3.10 直接执行下载入口。
    $ArgsList += "-3.10"
}
$ArgsList += @($Script, "download", "--model-name", $ModelName)
if ($Force) {
    $ArgsList += "--force"
}

& $Python @ArgsList
