<# workspace 级 YOLO Python Canvas 关闭入口。 #>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "yolo_web_py_canvas_ws\scripts\windows\stop_camera_yolo_py_canvas_all.ps1"

& powershell -ExecutionPolicy Bypass -File $Target
