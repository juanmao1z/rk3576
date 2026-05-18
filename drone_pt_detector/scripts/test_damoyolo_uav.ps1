<# 
测试 DAMO-YOLO UAV checkpoint。
该 checkpoint 不是 Ultralytics 格式，必须进入 third_party/DAMO-YOLO-master 使用专用脚本。
#>
param(
    [string]$Data = "data\open_datasets\maciullo_snippet\data.yaml",
    [string]$Source = "data\open_datasets\maciullo_snippet\images\test",
    [double]$Conf = 0.25,
    [int]$ImgSize = 640,
    [string]$Device = "cpu",
    [int]$Limit = 0,
    [switch]$EvalOnly,
    [switch]$DetectOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$Root = Split-Path -Parent $PSScriptRoot
$Workspace = Split-Path -Parent $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$DamoRoot = Join-Path $Workspace "third_party\DAMO-YOLO-master"
$Config = Join-Path $DamoRoot "configs\damoyolo_tinynasL25_S_uav.py"
$Checkpoint = Join-Path $Root "models\damoyolo_tinynasL25_S_uav.pt"
$DetectScript = Join-Path $DamoRoot "tools\damoyolo_uav_test.py"
$EvalScript = Join-Path $DamoRoot "tools\damoyolo_uav_eval_yolo.py"

if (-not (Test-Path $Python)) {
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}
if (-not (Test-Path $DamoRoot)) {
    throw "DAMO-YOLO source is missing: $DamoRoot"
}
if (-not (Test-Path $Checkpoint)) {
    throw "Checkpoint is missing: $Checkpoint"
}

# 支持相对路径，默认相对 drone_pt_detector 根目录解析。
if (-not [IO.Path]::IsPathRooted($Data)) {
    $Data = Join-Path $Root $Data
}
if (-not [IO.Path]::IsPathRooted($Source)) {
    $Source = Join-Path $Root $Source
}

if (-not $EvalOnly) {
    # DetectOnly/EvalOnly 用于分开验证可视化推理和 YOLO 标签评估。
    $DetectArgs = @(
        $DetectScript,
        "--config", $Config,
        "--ckpt", $Checkpoint,
        "--source", $Source,
        "--output-dir", (Join-Path $Root "runs\damoyolo_uav_detect"),
        "--conf", $Conf.ToString([Globalization.CultureInfo]::InvariantCulture),
        "--device", $Device,
        "--infer-size", $ImgSize.ToString(), $ImgSize.ToString()
    )
    if ($Limit -gt 0) {
        $DetectArgs += @("--limit", $Limit.ToString())
    }
    Push-Location $DamoRoot
    try {
        & $Python @DetectArgs
    }
    finally {
        Pop-Location
    }
}

if (-not $DetectOnly) {
    $EvalArgs = @(
        $EvalScript,
        "--config", $Config,
        "--ckpt", $Checkpoint,
        "--data", $Data,
        "--output-dir", (Join-Path $Root "runs\damoyolo_uav_eval"),
        "--conf", $Conf.ToString([Globalization.CultureInfo]::InvariantCulture),
        "--nms-conf", "0.001",
        "--device", $Device,
        "--infer-size", $ImgSize.ToString(), $ImgSize.ToString()
    )
    if ($Limit -gt 0) {
        $EvalArgs += @("--limit", $Limit.ToString())
    }
    Push-Location $DamoRoot
    try {
        & $Python @EvalArgs
    }
    finally {
        Pop-Location
    }
}
