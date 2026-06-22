"""达妙 USB2CANFD 用户态 SDK 封装。"""

from __future__ import annotations

import ctypes
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


class UsbRxFrameHead(ctypes.Structure):
    """对应 DM_DeviceSDK 的 usb_rx_frame_head_t 位域结构。"""

    _pack_ = 1
    _fields_ = [
        ("can_id", ctypes.c_uint32, 29),
        ("esi", ctypes.c_uint32, 1),
        ("ext", ctypes.c_uint32, 1),
        ("rtr", ctypes.c_uint32, 1),
        ("time_stamp", ctypes.c_uint64),
        ("channel", ctypes.c_uint8),
        ("canfd", ctypes.c_uint8, 1),
        ("dir", ctypes.c_uint8, 1),
        ("brs", ctypes.c_uint8, 1),
        ("ack", ctypes.c_uint8, 1),
        ("dlc", ctypes.c_uint8, 4),
        ("reserved", ctypes.c_uint16),
    ]


class UsbRxFrame(ctypes.Structure):
    """对应 DM_DeviceSDK 的 usb_rx_frame_t。"""

    _pack_ = 1
    _fields_ = [
        ("head", UsbRxFrameHead),
        ("payload", ctypes.c_uint8 * 64),
    ]


class CanInfo(ctypes.Structure):
    """对应 DM_DeviceSDK 的 dmcan_channel_can_info_t。"""

    _pack_ = 1
    _fields_ = [
        ("channel", ctypes.c_uint8),
        ("canfd", ctypes.c_bool),
        ("can_baudrate", ctypes.c_uint32),
        ("canfd_baudrate", ctypes.c_uint32),
        ("can_sp", ctypes.c_float),
        ("canfd_sp", ctypes.c_float),
    ]


@dataclass
class Feedback:
    """DM-H3510 反馈量。"""

    position_rad: float
    velocity_rad_s: float
    torque_nm: float


def decode_feedback(data: bytes) -> Feedback:
    """把 DM-H3510 8 字节反馈帧解码为物理量。"""

    q_uint = (data[1] << 8) | data[2]
    dq_uint = (data[3] << 4) | (data[4] >> 4)
    tau_uint = ((data[4] & 0x0F) << 8) | data[5]
    return Feedback(
        position_rad=q_uint / 65535.0 * 25.0 - 12.5,
        velocity_rad_s=dq_uint / 4095.0 * 560.0 - 280.0,
        torque_nm=tau_uint / 4095.0 * 2.0 - 1.0,
    )


class DmUsb2Canfd:
    """通过 DM_DeviceSDK 控制 USB2CANFD。

    当前默认配置来自板端实测成功链路：
    经典 CAN、1 Mbps、position-speed 命令 ID 0x101、反馈 ID 0x11。
    """

    _callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(UsbRxFrame))

    def __init__(
        self,
        library_path: str,
        channel: int,
        canfd: bool,
        brs: bool,
        nominal_baud: int,
        data_baud: int,
        master_id: int,
        feedback_callback: Optional[Callable[[Feedback], None]] = None,
    ) -> None:
        self.library_path = str(Path(library_path))
        self.channel = channel
        self.canfd = canfd
        self.brs = brs
        self.nominal_baud = nominal_baud
        self.data_baud = data_baud
        self.master_id = master_id
        self.feedback_callback = feedback_callback
        self.rx_count = 0
        self.master_rx_count = 0
        self._ctx = ctypes.c_void_p()
        self._dev = ctypes.c_void_p()
        self._recv_cb = self._callback_type(self._on_recv)
        self._lib = ctypes.CDLL(self.library_path)
        self._bind_api()

    def _bind_api(self) -> None:
        """声明 ctypes 参数类型，避免 Python 按 int 错传指针。"""

        self._lib.dmcan_context_create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self._lib.dmcan_find_devices.argtypes = [ctypes.c_void_p]
        self._lib.dmcan_find_devices.restype = ctypes.c_int
        self._lib.dmcan_device_get.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_int,
        ]
        self._lib.dmcan_device_get.restype = ctypes.c_bool
        self._lib.dmcan_device_open.argtypes = [ctypes.c_void_p]
        self._lib.dmcan_device_open.restype = ctypes.c_bool
        self._lib.dmcan_device_enable_channel.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        self._lib.dmcan_device_enable_channel.restype = ctypes.c_bool
        self._lib.dmcan_device_set_channel_baudrate.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint8,
            CanInfo,
        ]
        self._lib.dmcan_device_set_channel_baudrate.restype = ctypes.c_bool
        self._lib.dmcan_device_hook_recv_callback.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self._lib.dmcan_device_send_can.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint8,
            ctypes.c_uint32,
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_bool,
            ctypes.c_uint8,
            ctypes.POINTER(ctypes.c_uint8),
        ]
        self._lib.dmcan_device_send_can.restype = ctypes.c_bool

    def open(self) -> None:
        """打开 USB2CANFD 并配置 CAN 通道。"""

        self._lib.dmcan_context_create(ctypes.byref(self._ctx))
        count = self._lib.dmcan_find_devices(self._ctx)
        if count <= 0:
            raise RuntimeError("未找到 DM USB2CANFD 设备")
        if not self._lib.dmcan_device_get(self._ctx, ctypes.byref(self._dev), 0):
            raise RuntimeError("dmcan_device_get(0) 失败")
        if not self._lib.dmcan_device_open(self._dev):
            raise RuntimeError("dmcan_device_open 失败")
        if not self._lib.dmcan_device_enable_channel(self._dev, self.channel):
            raise RuntimeError(f"使能 CAN 通道 {self.channel} 失败")

        info = CanInfo(
            self.channel,
            self.canfd,
            self.nominal_baud,
            self.data_baud,
            ctypes.c_float(0.875),
            ctypes.c_float(0.75),
        )
        if not self._lib.dmcan_device_set_channel_baudrate(self._dev, self.channel, info):
            raise RuntimeError("设置 CAN 波特率失败")
        self._lib.dmcan_device_hook_recv_callback(self._dev, self._recv_cb)

    def send_can(self, can_id: int, payload: bytes) -> bool:
        """发送一帧经典 CAN/CANFD 数据。"""

        data = (ctypes.c_uint8 * len(payload))(*payload)
        return bool(
            self._lib.dmcan_device_send_can(
                self._dev,
                self.channel,
                can_id,
                self.canfd,
                False,
                False,
                self.brs,
                len(payload),
                data,
            )
        )

    def switch_control_mode(self, motor_can_id: int, mode_code: int) -> bool:
        """通过 0x7FF 写 CTRL_MODE 寄存器切换控制模式。

        mode_code: 1=MIT, 2=position-speed cascade, 3=speed, 4=hybrid/pos-force。
        """

        payload = bytes([
            motor_can_id & 0xFF,
            (motor_can_id >> 8) & 0xFF,
            0x55,
            10,
        ]) + struct.pack("<I", int(mode_code))
        ok = self.send_can(0x7FF, payload)
        time.sleep(0.02)
        return ok

    def enable_mode(self, control_can_id: int, repeats: int = 5) -> None:
        """发送当前控制模式使能帧。"""

        for _ in range(repeats):
            self.send_can(control_can_id, bytes([0xFF] * 7 + [0xFC]))
            time.sleep(0.005)

    def disable(self, control_can_id: int, repeats: int = 5) -> None:
        """发送失能帧。"""

        for _ in range(repeats):
            self.send_can(control_can_id, bytes([0xFF] * 7 + [0xFD]))
            time.sleep(0.005)

    def send_position_velocity(
        self,
        position_velocity_can_id: int,
        position_rad: float,
        velocity_rad_s: float,
    ) -> bool:
        """发送 position-speed cascade 命令，payload 为小端 pos + vel。"""

        payload = struct.pack("<ff", float(position_rad), float(velocity_rad_s))
        return self.send_can(position_velocity_can_id, payload)

    def _on_recv(self, _dev: int, frame_ptr: ctypes.POINTER(UsbRxFrame)) -> None:
        """SDK 接收回调：解析 master_id 反馈并转发给 ROS 节点。"""

        frame = frame_ptr.contents
        length = int(frame.head.dlc)
        data = bytes(frame.payload[:length])
        self.rx_count += 1
        if frame.head.can_id != self.master_id or length < 8:
            return
        self.master_rx_count += 1
        feedback = decode_feedback(data)
        if self.feedback_callback is not None:
            self.feedback_callback(feedback)
