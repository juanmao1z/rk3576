param(
    [string]$SerialNumber = "",
    [int]$CanId = 1,
    [int]$MasterId = 17,
    [double]$Duration = 3.0,
    [double]$Velocity = 0.0,
    [switch]$AllowMotion
)

$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "..\..\src\pc_dm_h3510_smoke.py"
$config = Join-Path $PSScriptRoot "..\..\config\pc_dm_h3510_example.json"

$argsList = @(
    $script,
    "--config", $config,
    "--can-id", $CanId,
    "--master-id", $MasterId,
    "--duration", $Duration
)

if ($SerialNumber) {
    $argsList += @("--sn", $SerialNumber)
}

if ($AllowMotion) {
    $argsList += @("--allow-motion", "--velocity", $Velocity)
}

try {
    py -3.13 @argsList
} catch {
    Write-Error "Python 3.13 is required for the DM_DeviceSDK smoke test. Original error: $_"
}
