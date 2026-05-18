<# 
workspace 级 C++ 摄像头启动入口。
该脚本转发到 camera_web_cpp_ws 的板端脚本，并自动映射 8081 端口。
#>
param(
    [string]$Size = "640x480",
    [Nullable[int]]$Fps = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# 本文件只做统一入口转发，实际 ROS 启动逻辑位于开发板 start_camera_web_cpp.sh。
$cameraPort = 8081
$remoteRoot = "/home/lckfb/workspace/ros/camera_web_cpp_ws"
$remoteScript = "$remoteRoot/start_camera_web_cpp.sh"
$remoteStopScript = "$remoteRoot/stop_camera_web_cpp.sh"

adb shell "chmod +x $remoteScript $remoteStopScript"

$cameraArgs = "--size $Size"
if ($null -ne $Fps) {
    $cameraArgs += " --fps $Fps"
}

adb shell "bash -lc ': >/tmp/start_camera_web_cpp.log; nohup $remoteScript $cameraArgs >/tmp/start_camera_web_cpp.log 2>&1 & echo STARTED'"
adb forward "tcp:$cameraPort" "tcp:$cameraPort" | Out-Null

for ($i = 0; $i -lt 30; $i++) {
    # /health 中 frames 大于 0 才表示摄像头已经真正产出帧。
    try {
        $content = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://127.0.0.1:$cameraPort/health" | Select-Object -ExpandProperty Content
        if ($content -match 'frames=(\d+)' -and [int]$Matches[1] -gt 0) {
            Write-Host "camera_web_cpp ready: $content"
            Write-Host "Open: http://127.0.0.1:$cameraPort/"
            return
        }
    } catch {
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 1
}

throw "camera_web_cpp did not become ready: http://127.0.0.1:$cameraPort/health"
