<# 
workspace 级无人机数据集验证入口。
按固定顺序验证当前保存的 Maciullo snippet 和 kc34251 测试集。
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Validate = Join-Path $Workspace "drone_pt_detector\scripts\validate.ps1"
$Maciullo = Join-Path $Workspace "drone_pt_detector\data\open_datasets\maciullo_snippet\data.yaml"
$Kc34251 = Join-Path $Workspace "drone_pt_detector\data\open_datasets\kc34251_drone_detection\data.yaml"

Write-Host "Validating Maciullo snippet..."
& powershell -ExecutionPolicy Bypass -File $Validate -Data $Maciullo -ImgSize 640 -Batch 8 -DroneOnly

Write-Host "Validating kc34251 dataset..."
& powershell -ExecutionPolicy Bypass -File $Validate -Data $Kc34251 -ImgSize 320 -Batch 16 -DroneOnly
