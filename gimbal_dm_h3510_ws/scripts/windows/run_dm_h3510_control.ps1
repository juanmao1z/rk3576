param(
    [double]$Velocity = 0.0,
    [int]$DurationMs = 2000,
    [int]$PeriodMs = 20,
    [int]$CanId = 1,
    [int]$MasterId = 17,
    [int]$NominalBaud = 1000000,
    [int]$DataBaud = 5000000,
    [switch]$CanFd,
    [switch]$SwitchMode,
    [switch]$AllowDmToolRunning
)

$ErrorActionPreference = "Stop"

if (-not $AllowDmToolRunning) {
    $dmTool = Get-Process | Where-Object { $_.ProcessName -like "DMTool*" } | Select-Object -First 1
    if ($dmTool) {
        throw "DMTool is still running (PID=$($dmTool.Id)). Close DMTool before using the SDK control program."
    }
}

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..\cpp_v1_1_smoke")
$build = Join-Path $root "build"

$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path -LiteralPath $vcvars)) {
    throw "vcvars64.bat not found: $vcvars"
}

cmd.exe /d /c "`"$vcvars`" >nul && cmake -S `"$root`" -B `"$build`" -G Ninja -DCMAKE_BUILD_TYPE=Release"
if ($LASTEXITCODE -ne 0) {
    throw "CMake configure failed with exit code $LASTEXITCODE"
}

cmd.exe /d /c "`"$vcvars`" >nul && cmake --build `"$build`" --config Release"
if ($LASTEXITCODE -ne 0) {
    throw "CMake build failed with exit code $LASTEXITCODE"
}

$dll = Join-Path $build "dm_device.dll"
$exeAlias = Join-Path $build "dm_device.exe"
if (Test-Path -LiteralPath $dll) {
    Copy-Item -LiteralPath $dll -Destination $exeAlias -Force
}

$runArgs = @(
    "--velocity", $Velocity,
    "--duration-ms", $DurationMs,
    "--period-ms", $PeriodMs,
    "--can-id", $CanId,
    "--master-id", $MasterId,
    "--nominal-baud", $NominalBaud,
    "--data-baud", $DataBaud
)

if ($CanFd) {
    $runArgs += "--canfd"
} else {
    $runArgs += "--classic-can"
}

if ($SwitchMode) {
    $runArgs += "--switch-mode"
}

& (Join-Path $build "dm_h3510_control.exe") @runArgs
