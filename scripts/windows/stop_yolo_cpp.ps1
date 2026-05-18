<# workspace 级通用 YOLO C++ Canvas 关闭入口。 #>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "yolo_web_cpp_ws\scripts\windows\stop_camera_yolo_cpp_all.ps1"

& powershell -ExecutionPolicy Bypass -File $Target
