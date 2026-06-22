<#
启动无人机 YOLO C++ Canvas 完整链路。
流程：通过 ADB 在开发板启动摄像头和 drone_yolo_web_cpp，随后映射 8081/8092 到本机并等待健康检查。
#>
param(
  [ValidateSet("usb", "rtsp")]
  [string]$Source = "usb",
  [string]$RtspUrl = "",
  [string]$Size = "640x480",
  [Nullable[int]]$Fps = $null,
  [string]$Model = "/home/lckfb/workspace/drone_yolo_web_cpp_ws/models/yolo11n.rknn",
  [string]$Labels = "drone"
)

$ErrorActionPreference = "Stop"

# 本机和开发板使用相同端口，浏览器统一访问 127.0.0.1。
$cameraPort = 8081
$yoloPort = 8092
$remoteRoot = "/home/lckfb/workspace/drone_yolo_web_cpp_ws"
$remoteCameraRoot = "/home/lckfb/workspace/ros/camera_web_cpp_ws"
$remoteScript = "$remoteRoot/scripts/board/start_drone_yolo_cpp_all.sh"
$remoteScripts = @(
  "$remoteRoot/scripts/board/start_drone_yolo_cpp_all.sh",
  "$remoteRoot/scripts/board/start_drone_yolo_web_cpp.sh",
  "$remoteRoot/scripts/board/stop_drone_yolo_cpp_all.sh",
  "$remoteRoot/scripts/board/stop_drone_yolo_web_cpp.sh",
  "$remoteCameraRoot/start_rtsp_camera_web_cpp.sh"
)

function ConvertTo-BashSingleQuoted($Value) {
  return "'" + $Value.Replace("'", "'\''") + "'"
}

adb shell "chmod +x $($remoteScripts -join ' ')"
$cameraArgs = @("--source", $Source, "--size", $Size)
if ($null -ne $Fps) {
  $cameraArgs += @("--fps", "$Fps")
}
if ($Source -eq "rtsp") {
  if ([string]::IsNullOrWhiteSpace($RtspUrl)) {
    throw "-RtspUrl is required when -Source rtsp is selected."
  }
  $cameraArgs += @("--rtsp-url", $RtspUrl)
}
$cameraArgsText = ($cameraArgs | ForEach-Object { ConvertTo-BashSingleQuoted $_ }) -join " "
$modelArg = ConvertTo-BashSingleQuoted $Model
$labelsArg = ConvertTo-BashSingleQuoted $Labels
$scriptArg = ConvertTo-BashSingleQuoted $remoteScript
$remoteStarter = @"
#!/usr/bin/env bash
set -e
: >/tmp/start_drone_yolo_cpp_all.log
RKNN_MODEL=$modelArg DETECTION_LABELS=$labelsArg nohup $scriptArg $cameraArgsText >/tmp/start_drone_yolo_cpp_all.log 2>&1 &
echo STARTED
"@
$remoteStarter = $remoteStarter -replace "`r", ""
$localStarter = [System.IO.Path]::GetTempFileName()
try {
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($localStarter, $remoteStarter, $utf8NoBom)
  adb push $localStarter /tmp/start_drone_yolo_cpp_all_remote.sh | Out-Null
  adb shell "chmod +x /tmp/start_drone_yolo_cpp_all_remote.sh"
  adb shell "bash /tmp/start_drone_yolo_cpp_all_remote.sh"
} finally {
  Remove-Item -LiteralPath $localStarter -Force -ErrorAction SilentlyContinue
}

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
Wait-HttpFrames "drone_yolo_web_cpp" "http://127.0.0.1:$yoloPort/health"

Write-Host "Open: http://127.0.0.1:$yoloPort/"
