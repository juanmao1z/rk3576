$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "..\..\src\pc_dm_h3510_smoke.py"

try {
    py -3.10 $script --list-devices
    if ($LASTEXITCODE -eq 0) {
        exit 0
    }
} catch {
    Write-Warning "Python USB enumeration failed, falling back to Windows PnP: $_"
}

$devices = Get-PnpDevice -PresentOnly |
    Where-Object { $_.InstanceId -match '^USB\\VID_34B7&PID_6877\\(.+)$' }

if (-not $devices) {
    Write-Error "No DAMIAO USB2CANFD device found by Python or Windows PnP."
}

foreach ($dev in $devices) {
    $serial = [regex]::Match($dev.InstanceId, '^USB\\VID_34B7&PID_6877\\(.+)$').Groups[1].Value
    Write-Output "U2CANFD_DEV PnP: FriendlyName=$($dev.FriendlyName) SN=$serial"
}
