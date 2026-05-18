<# workspace 级通用 YOLO C++ Canvas 启动入口。 #>

param(
    [string]$Size = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "yolo_web_cpp_ws\scripts\windows\start_camera_yolo_cpp_all.ps1"

# 这里只转发常用 Size 参数；模型和标签覆盖请直接使用 yolo_web_cpp_ws 内部脚本。
$ArgsList = @()
if ($Size) {
    $ArgsList += @("-Size", $Size)
}

& powershell -ExecutionPolicy Bypass -File $Target @ArgsList
