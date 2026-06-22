# Gimbal Scripts

云台脚本目录。

```text
scripts/
  board/      开发板侧脚本
  windows/    Windows/ADB 侧脚本
```

后续优先添加这些入口：

- `scripts/board/start_gimbal.sh`
- `scripts/board/stop_gimbal.sh`
- `scripts/board/center_gimbal.sh`
- `scripts/board/check_gimbal.sh`
- `scripts/windows/start_gimbal.ps1`
- `scripts/windows/stop_gimbal.ps1`

当前已加入 PC 端 USB2CANFD 验证入口：

- `scripts/windows/list_usb2canfd.ps1`：列出达妙 USB2CANFD 设备 SN。
- `scripts/windows/run_dm_h3510_control.ps1`：构建并运行工程化后的 C++ DM-H3510 控制程序。
- `scripts/windows/run_cpp_v1_1_smoke.ps1`：旧名称兼容包装，内部转调用 `run_dm_h3510_control.ps1`。
- `scripts/windows/run_pc_dm_h3510_smoke.ps1`：运行 DM-H3510 零速/低速 SDK 验证例程。
