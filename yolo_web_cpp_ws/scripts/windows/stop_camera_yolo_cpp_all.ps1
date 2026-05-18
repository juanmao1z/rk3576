<# 
关闭通用 YOLO C++ Canvas 完整链路。
该脚本先调用开发板关闭脚本，再清理 Windows 侧 ADB 端口映射。
#>
$ErrorActionPreference = "Stop"

$remoteScript = "/home/lckfb/workspace/yolo/yolo_web_cpp_ws/scripts/board/stop_camera_yolo_cpp_all.sh"

adb shell "chmod +x $remoteScript"
adb shell "bash -lc '$remoteScript'"

adb forward --remove tcp:8092 2>$null
adb forward --remove tcp:8081 2>$null

Write-Host "C++ camera + YOLO overlay services stopped and ADB forwards removed."
