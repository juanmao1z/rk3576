<# 下载内置开源无人机测试数据集。 #>

param(
    [ValidateSet("kc34251_drone_detection")]
    [string]$DatasetName = "kc34251_drone_detection",
    [int]$Limit = 0,
    [int]$Workers = 8,
    [switch]$Force
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
    # 数据集下载也依赖 Python 工具包，缺少 .venv 时先初始化环境。
    & (Join-Path $PSScriptRoot "setup_env.ps1")
}

$ArgsList = @(
    $Script,
    "download-dataset",
    "--dataset-name", $DatasetName,
    "--limit", $Limit.ToString(),
    "--workers", $Workers.ToString()
)

if ($Force) {
    $ArgsList += "--force"
}

& $Python @ArgsList
