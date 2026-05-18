<# 初始化 drone_pt_detector 的 Windows Python 虚拟环境。 #>

param(
    [string]$PythonVersion = "3.10"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"

if (-not (Test-Path $Python)) {
    # 固定使用 Python 3.10，和当前 Ultralytics/RKNN 相关工具兼容性最好。
    py "-$PythonVersion" -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r $Requirements

Write-Host "Environment ready:"
Write-Host "  $Python"
Write-Host ""
Write-Host "Next:"
Write-Host "  powershell -ExecutionPolicy Bypass -File $Root\scripts\download_model.ps1"
Write-Host "  powershell -ExecutionPolicy Bypass -File $Root\scripts\detect.ps1 -Source 0 -Show"
