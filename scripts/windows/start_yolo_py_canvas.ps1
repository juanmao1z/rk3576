<# workspace 级 YOLO Python Canvas 启动入口。 #>

param(
    [string]$Size = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "yolo_web_py_canvas_ws\scripts\windows\start_camera_yolo_py_canvas_all.ps1"

# 这里只转发常用 Size 参数，保持统一入口简单。
$ArgsList = @()
if ($Size) {
    $ArgsList += @("-Size", $Size)
}

& powershell -ExecutionPolicy Bypass -File $Target @ArgsList
