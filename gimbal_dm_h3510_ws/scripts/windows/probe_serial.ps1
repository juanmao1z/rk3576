param(
    [string]$Port = "COM16",
    [int]$Baud = 921600,
    [double]$Duration = 5.0
)

$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "..\..\src\serial_probe.py"
python $script --port $Port --baud $Baud --duration $Duration
