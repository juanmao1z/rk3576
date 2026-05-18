<# 
workspace 级无人机 PT 快速检测入口。
默认转发到 drone_pt_detector/scripts/detect.ps1，并启用 -DroneOnly 过滤。
#>
param(
    [string]$Source = "0",
    [switch]$Show
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "drone_pt_detector\scripts\detect.ps1"

# 默认只看无人机类别，减少飞机、鸟等类别对快速预览的干扰。
$ArgsList = @("-Source", $Source, "-DroneOnly")
if ($Show) {
    $ArgsList += "-Show"
}

& powershell -ExecutionPolicy Bypass -File $Target @ArgsList
