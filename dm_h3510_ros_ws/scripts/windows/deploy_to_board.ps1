param(
    [string]$BoardWorkspace = "/home/lckfb/workspace/dm_h3510_ros_ws"
)

$ErrorActionPreference = "Stop"

# 定位工作区根目录，保证脚本可以从任意目录执行。
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Resolve-Path (Join-Path $scriptDir "..\..")

if (-not (Get-Command adb -ErrorAction SilentlyContinue)) {
    throw "未找到 adb，请先安装 Android platform-tools 并加入 PATH。"
}

$devices = adb devices
if (-not ($devices -match "`tdevice")) {
    throw "未发现已连接的 RK3576 adb 设备。"
}

Write-Host "创建板端目录: $BoardWorkspace"
adb shell "mkdir -p '$BoardWorkspace'"

Write-Host "推送 Python ROS 工作区..."
adb shell "rm -rf '$BoardWorkspace/python'"
adb push (Join-Path $workspaceRoot "python") "$BoardWorkspace/"
adb shell "rm -rf '$BoardWorkspace/python/build' '$BoardWorkspace/python/install' '$BoardWorkspace/python/log'"

Write-Host "推送 C++ ROS 工作区..."
adb shell "rm -rf '$BoardWorkspace/cpp'"
adb push (Join-Path $workspaceRoot "cpp") "$BoardWorkspace/"
adb shell "rm -rf '$BoardWorkspace/cpp/build' '$BoardWorkspace/cpp/install' '$BoardWorkspace/cpp/log'"

Write-Host "推送脚本和文档..."
adb shell "rm -rf '$BoardWorkspace/scripts' '$BoardWorkspace/docs'"
adb push (Join-Path $workspaceRoot "scripts") "$BoardWorkspace/"
adb push (Join-Path $workspaceRoot "docs") "$BoardWorkspace/"
adb push (Join-Path $workspaceRoot "README.md") "$BoardWorkspace/README.md"

Write-Host "设置板端脚本可执行权限..."
adb shell "chmod +x '$BoardWorkspace'/scripts/board/*.sh"

Write-Host "部署完成: $BoardWorkspace"
