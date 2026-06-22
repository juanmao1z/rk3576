# DM-H3510 engineering notes

This workspace now has a small C++ control project instead of a one-file smoke
test. The current PC path is:

```text
PC -> DAMIAO USB2CANFD -> classic CAN 1 Mbps -> DM-H3510
```

The defaults match the verified DMTool trace:

| Item | Value |
| --- | --- |
| CAN type | Classic CAN, standard frame |
| Baud | 1 Mbps |
| Motor CAN ID | `0x001` |
| Master feedback ID | `0x011` |
| Velocity command ID | `0x201` |
| Enable payload | `FF FF FF FF FF FF FF FC` |
| Disable payload | `FF FF FF FF FF FF FF FD` |
| `1 rad/s` payload | `00 00 80 3F` |
| `5 rad/s` payload | `00 00 A0 40` |

## Project layout

```text
cpp_v1_1_smoke/
  CMakeLists.txt
  include/dm_h3510/
    protocol.hpp              Shared config, feedback, and stats types
    usb2canfd_device.hpp      DM_DeviceSDK transport wrapper
    dm_h3510_controller.hpp   DM-H3510 velocity-mode commands
  src/
    usb2canfd_device.cpp
    dm_h3510_controller.cpp
    main.cpp                  CLI entry point
  vendor/dm_device_sdk/       Vendor DLL, LIB, and header
```

`dm_h3510_driver` is the reusable library target. `dm_h3510_control` is the
PC-side CLI target used for validation.

## Windows run commands

Close DMTool first; the SDK and DMTool cannot own the USB2CANFD adapter at the
same time.

```powershell
cd D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws
.\scripts\windows\run_dm_h3510_control.ps1 -Velocity 0 -DurationMs 200
.\scripts\windows\run_dm_h3510_control.ps1 -Velocity 5 -DurationMs 2000
```

The old smoke script is still available as a compatibility wrapper:

```powershell
.\scripts\windows\run_cpp_v1_1_smoke.ps1 -Velocity 5 -DurationMs 2000
```

## RK3576 migration direction

The controller layer is independent of Windows except for `Usb2CanfdDevice`,
which wraps the DAMIAO `DM_DeviceSDK`. For RK3576 over USB, the next engineering
step is to replace or port the transport layer while keeping:

- `protocol.hpp`
- `dm_h3510_controller.hpp`
- `dm_h3510_controller.cpp`

If a Linux/RK3576 DAMIAO SDK is available, implement another transport class
with the same `send(...)`, `stats()`, and `latest_feedback()` behavior. If only
a serial CDC protocol is available, keep the controller command semantics but
replace the CAN frame send/receive implementation.
