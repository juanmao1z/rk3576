<# workspace 级 YOLO Python 服务端画框关闭入口。 #>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Workspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Target = Join-Path $Workspace "yolo_web_py_ws\scripts\windows\stop_camera_yolo_py_all.ps1"

& powershell -ExecutionPolicy Bypass -File $Target
