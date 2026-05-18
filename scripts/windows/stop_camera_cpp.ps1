<# workspace 级 C++ 摄像头关闭入口。 #>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$remoteScript = "/home/lckfb/workspace/ros/camera_web_cpp_ws/stop_camera_web_cpp.sh"

adb shell "chmod +x $remoteScript"
adb shell "bash -lc '$remoteScript || true'"

Write-Host "camera_web_cpp stopped."
