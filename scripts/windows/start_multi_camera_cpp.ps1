<#
workspace 级双路 C++ 摄像头启动入口。
通过 SSH 在开发板启动双路 camera_web_cpp，并直接访问开发板 8081/8082 预览端口。
#>
param(
    [string]$HostName = "192.168.137.217",
    [string]$User = "lckfb",
    [string]$FrontDevice = "/dev/video73",
    [string]$LeftDevice = "/dev/video75",
    [string]$Size = "640x480",
    [int]$Fps = 25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$remoteRoot = "/home/lckfb/workspace/ros/camera_web_cpp_ws"
$remoteScript = "$remoteRoot/start_multi_camera_web_cpp.sh"
$remoteStopScript = "$remoteRoot/stop_multi_camera_web_cpp.sh"
$sshTarget = "$User@$HostName"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no $sshTarget "chmod +x $remoteScript $remoteStopScript"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no $sshTarget "$remoteStopScript || true"

$startCommand = ": >/tmp/start_multi_camera_web_cpp.log; nohup $remoteScript --front-device $FrontDevice --left-device $LeftDevice --size $Size --fps $Fps >/tmp/start_multi_camera_web_cpp.log 2>&1 & echo STARTED"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no $sshTarget $startCommand

function Wait-HttpFrames($Name, $Url) {
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

Wait-HttpFrames "front camera" "http://${HostName}:8081/health"
Wait-HttpFrames "left camera" "http://${HostName}:8082/health"

Write-Host "Open front: http://${HostName}:8081/"
Write-Host "Open left : http://${HostName}:8082/"
