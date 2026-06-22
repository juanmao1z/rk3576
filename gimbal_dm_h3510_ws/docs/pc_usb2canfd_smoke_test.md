# PC USB2CANFD smoke test for DM-H3510

This test verifies that the PC can control a DM-H3510 through the DAMIAO
USB2CANFD SDK without opening the DMTool GUI.

## Hardware path

```text
PC USB -> DAMIAO USB2CANFD -> CAN_H/CAN_L/GND -> DM-H3510
DM-H3510 -> separate motor power supply
```

Use a 120 ohm terminal resistor at the bus end when needed. Keep the motor
unloaded or mechanically constrained for the first run.

## Software prerequisites

- Windows x64.
- Python 3.13 x64 is used by the current smoke test with `DM_DeviceSDK`.
- Python 3.10 is only used by the serial-number listing wrapper because it
  reuses the old `pyusb` helper first, then falls back to Windows PnP.
- `pyusb` is needed only for the Python serial-number listing path:

```powershell
py -3.10 -m pip install pyusb
```

The smoke script uses the newer SDK DLLs copied into:

```text
D:/Desktop/rk3576/workspace/gimbal_dm_h3510_ws/src/dlls
```

## Step 1: list USB2CANFD serial number

```powershell
cd D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws
.\scripts\windows\list_usb2canfd.ps1
```

Copy the printed `SN=...` value.

The run wrapper calls `py -3.13` for `DM_DeviceSDK`. The listing wrapper may
call `py -3.10` first and then fall back to Windows PnP.

## Step 2: zero-velocity smoke test

This is the default safe test. It enables the motor, commands velocity `0`,
prints feedback, then disables on exit. The C++ v1.1 smoke test defaults to
the same classic CAN path captured from DMTool: standard frame, classic CAN,
1 Mbps, motor CAN ID `0x001`, master ID `0x011`, velocity command ID `0x201`.

```powershell
.\scripts\windows\run_pc_dm_h3510_smoke.ps1 -SerialNumber "YOUR_USB2CANFD_SN"
```

If your motor IDs differ, pass them explicitly:

```powershell
.\scripts\windows\run_pc_dm_h3510_smoke.ps1 -SerialNumber "YOUR_USB2CANFD_SN" -CanId 1 -MasterId 17
```

## Step 3: low-speed motion test

Run this only after the zero-velocity test prints feedback.

```powershell
.\scripts\windows\run_pc_dm_h3510_smoke.ps1 -SerialNumber "YOUR_USB2CANFD_SN" -AllowMotion -Velocity 0.5 -Duration 2
```

For the C++ v1.1 SDK smoke test that mirrors the DMTool trace:

```powershell
.\scripts\windows\run_dm_h3510_control.ps1 -Velocity 1 -DurationMs 2000
```

Close DMTool before running the SDK smoke test. DMTool and the SDK cannot own
the USB2CANFD adapter at the same time. The C++ runner checks for a running
`DMTool*` process and exits early to avoid a misleading device-open failure.

## What success looks like

The script should print feedback lines like:

```text
feedback pos= ... vel= ... tau= ... dt= ...
```

The exact values depend on motor state and whether motion is allowed. A working
zero-velocity test proves that the PC is controlling through USB2CANFD without
using the official GUI.

## Notes

- The example config is `config/pc_dm_h3510_example.json`.
- The script uses DM-H3510 as `DM_Motor_Type.DMH3510` and velocity mode.
- DMTool's working trace used classic CAN at `1000000`, not CANFD. At `1 rad/s`
  it repeatedly sent `ID=0x201 len=4 data=00 00 80 3F`, which is little-endian
  float `1.0`.
- The C++ smoke runner can still force CANFD with `-CanFd`, and can send the
  `0x7FF` mode-switch frame with `-SwitchMode` when needed.
- If the script cannot import the old SDK on Windows, check that Python is x64
  and compatible with the bundled `.pyd`.
