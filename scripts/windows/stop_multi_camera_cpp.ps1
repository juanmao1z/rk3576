<#
workspace 级双路 C++ 摄像头关闭入口。
通过 SSH 停止开发板双路 camera_web_cpp。
#>
param(
    [string]$HostName = "192.168.137.217",
    [string]$User = "lckfb"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sshTarget = "$User@$HostName"
$remoteStopScript = "/home/lckfb/workspace/ros/camera_web_cpp_ws/stop_multi_camera_web_cpp.sh"

ssh -o BatchMode=yes -o StrictHostKeyChecking=no $sshTarget "chmod +x $remoteStopScript; $remoteStopScript || true"

Write-Host "Multi-camera C++ services stopped."
