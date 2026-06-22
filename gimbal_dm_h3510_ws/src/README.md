# Gimbal Source

这里放 DM-H3510 驱动、控制节点或协议适配代码。

建议实现顺序：

1. 最小设备通信测试。
2. 归中、停止、角度或速度控制。
3. 状态读取和故障处理。
4. ROS2 节点或轻量控制进程。
5. 订阅 `/yolo/detections` 后的目标跟踪控制。

## PC 端 SDK 验证例程

- `pc_dm_h3510_smoke.py`：通过达妙 `DM_DeviceSDK` 控制 DM-H3510，不依赖 DMTool 图形上位机。
- 默认执行零速速度控制并打印反馈；需要真实转动时显式加 `--allow-motion`。
