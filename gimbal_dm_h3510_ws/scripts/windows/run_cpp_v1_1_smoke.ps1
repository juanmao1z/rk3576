param(
    [double]$Velocity = 0.0,
    [int]$DurationMs = 2000,
    [int]$PeriodMs = 20,
    [int]$CanId = 1,
    [int]$MasterId = 17,
    [int]$NominalBaud = 1000000,
    [int]$DataBaud = 5000000,
    [switch]$ClassicCan,
    [switch]$CanFd,
    [switch]$SwitchMode,
    [switch]$AllowDmToolRunning
)

$argsList = @(
    "-Velocity", $Velocity,
    "-DurationMs", $DurationMs,
    "-PeriodMs", $PeriodMs,
    "-CanId", $CanId,
    "-MasterId", $MasterId,
    "-NominalBaud", $NominalBaud,
    "-DataBaud", $DataBaud
)

if ($CanFd) {
    $argsList += "-CanFd"
}
if ($SwitchMode) {
    $argsList += "-SwitchMode"
}
if ($AllowDmToolRunning) {
    $argsList += "-AllowDmToolRunning"
}

& (Join-Path $PSScriptRoot "run_dm_h3510_control.ps1") @argsList
