<#
关闭 YOLO Python 服务端画框完整链路。
该脚本先调用开发板关闭脚本，再清理 Windows 侧 ADB 端口映射。
#>
$ErrorActionPreference = "Stop"

$remoteScript = "/home/lckfb/workspace/yolo/yolo_web_py_ws/scripts/board/stop_camera_yolo_py_all.sh"

adb shell "chmod +x $remoteScript"
adb shell "bash -lc '$remoteScript'"

adb forward --remove tcp:8090 2>$null
adb forward --remove tcp:8081 2>$null

Write-Host "C++ camera + Python YOLO result-stream services stopped and ADB forwards removed."
