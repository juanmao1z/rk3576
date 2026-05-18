<# 
启动通用 YOLO C++ Canvas 完整链路。
流程：通过 ADB 在开发板启动摄像头和 YOLO，随后映射 8081/8092 到本机并等待健康检查。
#>
param(
  [string]$Size = "640x480",
  [Nullable[int]]$Fps = $null,
  [string]$Model = "/home/lckfb/workspace/yolo/yolo_web_cpp_ws/models/yolo11.rknn",
  [string]$Labels = "coco"
)

$ErrorActionPreference = "Stop"

# 本机和开发板使用相同端口，浏览器统一访问 127.0.0.1。
$cameraPort = 8081
$yoloPort = 8092
$remoteRoot = "/home/lckfb/workspace/yolo/yolo_web_cpp_ws"
$remoteScript = "$remoteRoot/scripts/board/start_camera_yolo_cpp_all.sh"
$remoteScripts = @(
  "$remoteRoot/scripts/board/start_camera_yolo_cpp_all.sh",
  "$remoteRoot/scripts/board/start_yolo_web_cpp.sh",
  "$remoteRoot/scripts/board/stop_camera_yolo_cpp_all.sh",
  "$remoteRoot/scripts/board/stop_yolo_web_cpp.sh"
)

adb shell "chmod +x $($remoteScripts -join ' ')"
$cameraArgs = "--size $Size"
if ($null -ne $Fps) {
  $cameraArgs += " --fps $Fps"
}
# RKNN_MODEL 和 DETECTION_LABELS 通过环境变量传给板端 YOLO 启动脚本。
adb shell "bash -lc ': >/tmp/start_camera_yolo_cpp_all.log; RKNN_MODEL=$Model DETECTION_LABELS=$Labels nohup $remoteScript $cameraArgs >/tmp/start_camera_yolo_cpp_all.log 2>&1 & echo STARTED'"

adb forward "tcp:$cameraPort" "tcp:$cameraPort" | Out-Null
adb forward "tcp:$yoloPort" "tcp:$yoloPort" | Out-Null

function Wait-HttpFrames($Name, $Url) {
  # camera 和 yolo 的 /health 都包含 frames 字段；大于 0 才说明链路已经跑起来。
  for ($i = 0; $i -lt 30; $i++) {
    try {
      $content = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $Url | Select-Object -ExpandProperty Content
      if ($content -match 'frames=(\d+)' -and [int]$Matches[1] -gt 0) {
        Write-Host "$Name ready: $content"
        return
      }
    } catch {
      Start-Sleep -Seconds 1
    }
    Start-Sleep -Seconds 1
  }
  throw "$Name did not become ready: $Url"
}

Wait-HttpFrames "camera_web_cpp" "http://127.0.0.1:$cameraPort/health"
Wait-HttpFrames "yolo_web_cpp" "http://127.0.0.1:$yoloPort/health"

Write-Host "Open: http://127.0.0.1:$yoloPort/"
