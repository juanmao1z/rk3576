<# 将本地 Anti-UAV VOC/XML 数据集转换成 YOLO 格式。 #>

param(
    [string]$TrainRoot = "D:\Desktop\rk3576\datasets\drone-voc\raw\DroneTrainDataset",
    [string]$TestRoot = "D:\Desktop\rk3576\datasets\drone-voc\raw\DroneTestDataset",
    [string]$Output = "D:\Desktop\rk3576\workspace\drone_pt_detector\data\prepared\DroneTrainDataset_yolo",
    [double]$ValRatio = 0.1,
    [switch]$Copy,
    [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Script = Join-Path $PSScriptRoot "prepare_drone_voc_dataset.py"

if (-not (Test-Path $Python)) {
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "--train-images", (Join-Path $TrainRoot "Drone_TrainSet"),
    "--train-xmls", (Join-Path $TrainRoot "Drone_TrainSet_XMLs"),
    "--test-images", (Join-Path $TestRoot "Drone_TestSet"),
    "--test-xmls", (Join-Path $TestRoot "Drone_TestSet_XMLs"),
    "--output", $Output,
    "--val-ratio", $ValRatio.ToString([Globalization.CultureInfo]::InvariantCulture)
)

if ($Copy) {
    $ArgsList += "--copy"
}
if ($Clean) {
    $ArgsList += "--clean"
}

& $Python @ArgsList
