# Workspace Scripts

workspace 级统一入口脚本目录。这里的脚本只负责转发到各工作区内部脚本，不替代具体项目的启动逻辑。

## 项目定位

- Windows 日常入口统一放在 `scripts\windows`。
- 启动脚本负责调用对应工作区脚本、设置 ADB 端口转发、等待健康检查。
- 停止脚本负责调用板端关闭逻辑，并清理本机 ADB 转发。

## 目录结构

```text
scripts/
  windows/
    start_camera_cpp.ps1
    stop_camera_cpp.ps1
    start_multi_camera_cpp.ps1
    stop_multi_camera_cpp.ps1
    start_yolo_cpp.ps1
    stop_yolo_cpp.ps1
    start_yolo_py.ps1
    stop_yolo_py.ps1
    start_yolo_py_canvas.ps1
    stop_yolo_py_canvas.ps1
    test_drone_pt.ps1
    validate_drone_datasets.ps1
    # 后续可添加 start_gimbal_dm_h3510.ps1 / stop_gimbal_dm_h3510.ps1
```

## 常用命令

启动 C++ 摄像头：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_camera_cpp.ps1
```

启动双路 C++ 摄像头：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_multi_camera_cpp.ps1
```

启动通用 YOLO C++ Canvas：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_cpp.ps1
```

启动 YOLO Python 服务端画框版：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_py.ps1
```

启动 YOLO Python Canvas 版：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_yolo_py_canvas.ps1
```

停止对应服务：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_yolo_cpp.ps1
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_yolo_py.ps1
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_yolo_py_canvas.ps1
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_camera_cpp.ps1
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_multi_camera_cpp.ps1
```

PC 端无人机模型快速测试：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\test_drone_pt.ps1 -Source 0 -Show
```

DM-H3510 云台后续入口：

```powershell
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\start_gimbal_dm_h3510.ps1
powershell -ExecutionPolicy Bypass -File D:\Desktop\rk3576\workspace\scripts\windows\stop_gimbal_dm_h3510.ps1
```

具体云台通信和控制逻辑应放在 `D:\Desktop\rk3576\workspace\gimbal_dm_h3510_ws`，workspace 级脚本只做转发和 ADB 辅助。

## 端口约定

| 服务 | 本机端口 |
| --- | --- |
| 摄像头原始 MJPEG | `8081` |
| 双路摄像头 left MJPEG | `8082` |
| YOLO Python 服务端画框 | `8090` |
| YOLO Python Canvas | `8091` |
| YOLO C++ Canvas | `8092` |

## 验证

```powershell
adb forward --list
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8081/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8092/health
```

双路摄像头通过 SSH 直接访问开发板端口：

```powershell
Invoke-WebRequest -UseBasicParsing http://192.168.137.217:8081/health
Invoke-WebRequest -UseBasicParsing http://192.168.137.217:8082/health
```
