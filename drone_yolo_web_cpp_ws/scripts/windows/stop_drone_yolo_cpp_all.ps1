<#
关闭无人机 YOLO C++ Canvas 完整链路。
该脚本先调用开发板关闭脚本，再清理 Windows 侧 ADB 端口映射。
#>
$ErrorActionPreference = "Stop"

$remoteScript = "/home/lckfb/workspace/drone_yolo_web_cpp_ws/scripts/board/stop_drone_yolo_cpp_all.sh"

adb shell "chmod +x $remoteScript"
adb shell "bash -lc '$remoteScript'"

adb forward --remove tcp:8092 2>$null
adb forward --remove tcp:8081 2>$null

Write-Host "C++ camera + Drone YOLO overlay services stopped and ADB forwards removed."
