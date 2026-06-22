#!/usr/bin/env python3
"""
PC-side DM-H3510 smoke test through DAMIAO USB2CANFD, without DMTool GUI.

Default behavior is intentionally conservative: open the USB2CANFD device,
enable one DM-H3510 in velocity mode, command 0 rad/s, and print feedback.
Pass --allow-motion to send a non-zero test velocity.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib
import json
import os
import signal
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = WORKSPACE_ROOT / "config" / "pc_dm_h3510_example.json"
DEFAULT_SDK_ROOT = Path(
    "D:/Desktop/\u6a21\u5757\u8d44\u6599/\u7535\u673a\u9a71\u52a8\u8d44\u6599/dm-tools/USB2CANFD/SDK/\u65e7\u7248/Python"
)

running = True


@dataclass
class SmokeConfig:
    sdk_root: Path
    serial_number: str
    nominal_baud: int
    data_baud: int
    can_id: int
    master_id: int
    safe_velocity_rad_s: float
    motion_velocity_rad_s: float
    duration_s: float
    period_s: float


class UsbRxFrameHead(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("can_id", ctypes.c_uint32, 29),
        ("esi", ctypes.c_uint32, 1),
        ("ext", ctypes.c_uint32, 1),
        ("rtr", ctypes.c_uint32, 1),
        ("timestamp", ctypes.c_uint64),
        ("channel", ctypes.c_uint8),
        ("canfd", ctypes.c_uint8, 1),
        ("dir", ctypes.c_uint8, 1),
        ("brs", ctypes.c_uint8, 1),
        ("ack", ctypes.c_uint8, 1),
        ("dlc", ctypes.c_uint8, 4),
        ("reserved", ctypes.c_uint16),
    ]


class UsbRxFrame(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("head", UsbRxFrameHead),
        ("payload", ctypes.c_uint8 * 64),
    ]


class CanInfo(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("channel", ctypes.c_uint8),
        ("canfd", ctypes.c_bool),
        ("can_baudrate", ctypes.c_uint32),
        ("canfd_baudrate", ctypes.c_uint32),
        ("can_sp", ctypes.c_float),
        ("canfd_sp", ctypes.c_float),
    ]


class NewDmDevice:
    """Small direct ctypes wrapper around DM_DeviceSDK v1.1.0.

    The packaged Python wrapper currently creates the SDK context incorrectly on
    this host, so this smoke test calls the DLL directly.
    """

    def __init__(self, dll_dir: Path):
        self.dll_dir = dll_dir
        self.ctx = ctypes.c_void_p()
        self.dev = ctypes.c_void_p()
        self._recv_cb = None
        self.feedback: dict[str, float] = {}
        self.any_rx_count = 0

    def __enter__(self) -> "NewDmDevice":
        os.chdir(self.dll_dir.parent)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(self.dll_dir))
            os.add_dll_directory(str(self.dll_dir.parent))
        self.dll = ctypes.CDLL(str(self.dll_dir / "libdm_device.dll"), winmode=0)
        self._init_funcs()
        self.dll.dmcan_context_create(ctypes.byref(self.ctx))
        if not self.ctx.value:
            raise RuntimeError("dmcan_context_create returned null")
        count = self.dll.dmcan_find_devices(self.ctx)
        if count <= 0:
            raise RuntimeError("DM_DeviceSDK found no USB2CANFD devices")
        if not self.dll.dmcan_device_get(self.ctx, ctypes.byref(self.dev), 0):
            raise RuntimeError("dmcan_device_get(0) failed")
        if not self.dev.value:
            raise RuntimeError("dmcan_device_get returned null device")
        if not self.dll.dmcan_device_open(self.dev):
            raise RuntimeError("dmcan_device_open failed")
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        # Do not call dmcan_device_close or dmcan_context_destroy here. The
        # current Windows DLL can crash on teardown after callback/send use; the
        # process exit releases the handle after we send the motor disable frame.
        return None

    def _init_funcs(self) -> None:
        self.dll.dmcan_context_create.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        self.dll.dmcan_context_create.restype = None
        self.dll.dmcan_find_devices.argtypes = [ctypes.c_void_p]
        self.dll.dmcan_find_devices.restype = ctypes.c_int
        self.dll.dmcan_device_get.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_int,
        ]
        self.dll.dmcan_device_get.restype = ctypes.c_bool
        self.dll.dmcan_device_open.argtypes = [ctypes.c_void_p]
        self.dll.dmcan_device_open.restype = ctypes.c_bool
        self.dll.dmcan_device_close.argtypes = [ctypes.c_void_p]
        self.dll.dmcan_device_close.restype = None
        self.dll.dmcan_device_enable_channel.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        self.dll.dmcan_device_enable_channel.restype = ctypes.c_bool
        self.dll.dmcan_device_set_channel_baudrate.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint8,
            CanInfo,
        ]
        self.dll.dmcan_device_set_channel_baudrate.restype = ctypes.c_bool
        self.dll.dmcan_device_send_can.argtypes = [
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
        self.dll.dmcan_device_send_can.restype = ctypes.c_bool
        self.recv_cb_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(UsbRxFrame))
        self.dll.dmcan_device_hook_recv_callback.argtypes = [ctypes.c_void_p, self.recv_cb_type]
        self.dll.dmcan_device_hook_recv_callback.restype = None

    def configure_channel(self, nominal_baud: int, data_baud: int) -> None:
        if not self.dll.dmcan_device_enable_channel(self.dev, 0):
            raise RuntimeError("dmcan_device_enable_channel(0) failed")
        info = CanInfo(
            channel=0,
            canfd=True,
            can_baudrate=nominal_baud,
            canfd_baudrate=data_baud,
            can_sp=ctypes.c_float(0.875),
            canfd_sp=ctypes.c_float(0.75),
        )
        if not self.dll.dmcan_device_set_channel_baudrate(self.dev, 0, info):
            raise RuntimeError("dmcan_device_set_channel_baudrate failed")

    def hook_feedback(self, master_id: int) -> None:
        def uint_to_float(value: int, min_value: float, max_value: float, bits: int) -> float:
            return float(value) / ((1 << bits) - 1) * (max_value - min_value) + min_value

        def callback(_handle, frame_ptr) -> None:
            if not frame_ptr:
                return
            frame = frame_ptr.contents
            self.any_rx_count += 1
            if frame.head.can_id != master_id:
                if self.any_rx_count <= 10:
                    dlc = min(frame.head.dlc, 8)
                    payload = " ".join(f"{frame.payload[i]:02X}" for i in range(dlc))
                    print(f"rx other id=0x{frame.head.can_id:X} dlc={frame.head.dlc} data={payload}")
                return
            data = list(frame.payload[:8])
            q_uint = (data[1] << 8) | data[2]
            dq_uint = (data[3] << 4) | (data[4] >> 4)
            tau_uint = ((data[4] & 0xF) << 8) | data[5]
            self.feedback = {
                "pos": uint_to_float(q_uint, -12.5, 12.5, 16),
                "vel": uint_to_float(dq_uint, -280.0, 280.0, 12),
                "tau": uint_to_float(tau_uint, -1.0, 1.0, 12),
                "timestamp": time.monotonic(),
            }

        self._recv_cb = self.recv_cb_type(callback)
        self.dll.dmcan_device_hook_recv_callback(self.dev, self._recv_cb)

    def send(self, can_id: int, payload: bytes, canfd: bool = True, brs: bool = True) -> bool:
        data = (ctypes.c_uint8 * len(payload))(*payload)
        return self.dll.dmcan_device_send_can(
            self.dev,
            0,
            can_id,
            canfd,
            False,
            False,
            brs,
            len(payload),
            data,
        )

    def send_checked(self, can_id: int, payload: bytes, label: str) -> None:
        if not self.send(can_id, payload):
            raise RuntimeError(f"send failed: {label}, can_id=0x{can_id:X}, payload={payload.hex(' ')}")


def _stop(_signum: int, _frame: object) -> None:
    global running
    running = False


def load_config(path: Path) -> SmokeConfig:
    raw: dict[str, Any] = {}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))

    motor = raw.get("motor", {})
    test = raw.get("test", {})

    return SmokeConfig(
        sdk_root=Path(raw.get("sdk_root") or DEFAULT_SDK_ROOT),
        serial_number=str(raw.get("serial_number") or ""),
        nominal_baud=int(raw.get("nominal_baud", 1_000_000)),
        data_baud=int(raw.get("data_baud", 5_000_000)),
        can_id=int(motor.get("can_id", 1)),
        master_id=int(motor.get("master_id", 0x11)),
        safe_velocity_rad_s=float(motor.get("safe_velocity_rad_s", 0.0)),
        motion_velocity_rad_s=float(motor.get("motion_velocity_rad_s", 0.5)),
        duration_s=float(test.get("duration_s", 3.0)),
        period_s=float(test.get("period_s", 0.02)),
    )


def list_usb2canfd_devices() -> int:
    try:
        import usb.core
        import usb.util
    except Exception as exc:
        print(f"pyusb is required for --list-devices: {exc}", file=sys.stderr)
        return 2

    devices = list(usb.core.find(find_all=True, idVendor=0x34B7, idProduct=0x6877))
    if not devices:
        print("No DAMIAO USB2CANFD device found. Check USB connection and driver.")
        return 1

    for index, dev in enumerate(devices):
        serial = "[No serial number]"
        if dev.iSerialNumber:
            try:
                serial = usb.util.get_string(dev, dev.iSerialNumber)
            except Exception as exc:
                serial = f"[Failed to read serial: {exc}]"
        print(f"U2CANFD_DEV {index}: VID=0x{dev.idVendor:04x} PID=0x{dev.idProduct:04x} SN={serial}")
    return 0


def import_damiao(sdk_root: Path):
    sdk_root = sdk_root.resolve()
    if not sdk_root.exists():
        raise FileNotFoundError(f"SDK root does not exist: {sdk_root}")
    if not (sdk_root / "damiao.py").exists():
        raise FileNotFoundError(f"damiao.py not found under SDK root: {sdk_root}")

    sys.path.insert(0, str(sdk_root))
    return importlib.import_module("damiao")


def run_smoke(cfg: SmokeConfig, allow_motion: bool, velocity_override: float | None) -> int:
    if not cfg.serial_number:
        print(
            "USB2CANFD serial_number is empty. Run with --list-devices, then pass --sn or edit config.",
            file=sys.stderr,
        )
        return 2

    velocity = cfg.safe_velocity_rad_s
    if allow_motion:
        velocity = cfg.motion_velocity_rad_s if velocity_override is None else velocity_override
    elif velocity_override not in (None, 0.0):
        print("Ignoring non-zero --velocity because --allow-motion was not set.", file=sys.stderr)

    print("Opening DAMIAO USB2CANFD and DM-H3510 through DM_DeviceSDK:")
    print(f"  sdk_root      = {cfg.sdk_root}")
    print(f"  sn            = {cfg.serial_number}")
    print(f"  baud          = {cfg.nominal_baud}/{cfg.data_baud}")
    print(f"  can_id/mst_id = 0x{cfg.can_id:X}/0x{cfg.master_id:X}")
    print(f"  velocity_cmd  = {velocity:.4f} rad/s")
    print("Press Ctrl+C to stop. The context manager will send disable on exit.")

    dll_dir = WORKSPACE_ROOT / "src" / "dlls"
    if not (dll_dir / "libdm_device.dll").exists():
        raise FileNotFoundError(f"Missing {dll_dir / 'libdm_device.dll'}")
    if not (dll_dir / "libusb-1.0.dll").exists():
        raise FileNotFoundError(f"Missing {dll_dir / 'libusb-1.0.dll'}")

    vel_mode_offset = 0x200
    vel_can_id = cfg.can_id + vel_mode_offset
    deadline = time.monotonic() + cfg.duration_s
    with NewDmDevice(dll_dir) as device:
        device.configure_channel(cfg.nominal_baud, cfg.data_baud)
        device.hook_feedback(cfg.master_id)

        # Switch to velocity mode, then enable. This follows the vendor
        # damiao.py protocol but uses the newer USB2CANFD SDK transport.
        switch_to_vel = bytes([cfg.can_id & 0xFF, (cfg.can_id >> 8) & 0xFF, 0x55, 10, 3, 0, 0, 0])
        device.send_checked(0x7FF, switch_to_vel, "switch velocity mode")
        time.sleep(0.02)
        enable = bytes([0xFF] * 7 + [0xFC])
        for _ in range(5):
            device.send_checked(vel_can_id, enable, "enable")
            time.sleep(0.002)

        while running and time.monotonic() < deadline:
            start = time.monotonic()
            device.send_checked(vel_can_id, struct.pack("<f", velocity), "velocity command")
            fb = device.feedback
            if fb:
                age = time.monotonic() - fb["timestamp"]
                print(
                    "feedback "
                    f"pos={fb['pos']: .6f} "
                    f"vel={fb['vel']: .6f} "
                    f"tau={fb['tau']: .6f} "
                    f"age={age: .3f}s"
                )
            else:
                print("feedback pending")
            sleep_time = cfg.period_s - (time.monotonic() - start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        device.send_checked(vel_can_id, struct.pack("<f", 0.0), "zero velocity")
        time.sleep(0.05)
        disable = bytes([0xFF] * 7 + [0xFD])
        for _ in range(5):
            device.send_checked(vel_can_id, disable, "disable")
            time.sleep(0.002)

    print("Smoke test finished.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PC DM-H3510 USB2CANFD smoke test")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="JSON config path")
    parser.add_argument("--sdk-root", type=Path, help="Override DAMIAO old Python SDK root")
    parser.add_argument("--sn", help="USB2CANFD serial number")
    parser.add_argument("--can-id", type=lambda value: int(value, 0), help="DM-H3510 CAN ID")
    parser.add_argument("--master-id", type=lambda value: int(value, 0), help="DM-H3510 master feedback ID")
    parser.add_argument("--duration", type=float, help="Test duration in seconds")
    parser.add_argument("--period", type=float, help="Command period in seconds")
    parser.add_argument("--velocity", type=float, help="Velocity command in rad/s, used only with --allow-motion")
    parser.add_argument("--allow-motion", action="store_true", help="Allow non-zero velocity command")
    parser.add_argument("--list-devices", action="store_true", help="List connected DAMIAO USB2CANFD devices")
    return parser.parse_args()


def main() -> int:
    signal.signal(signal.SIGINT, _stop)
    args = parse_args()

    if args.list_devices:
        return list_usb2canfd_devices()

    cfg = load_config(args.config)
    if args.sdk_root:
        cfg.sdk_root = args.sdk_root
    if args.sn:
        cfg.serial_number = args.sn
    if args.can_id is not None:
        cfg.can_id = args.can_id
    if args.master_id is not None:
        cfg.master_id = args.master_id
    if args.duration is not None:
        cfg.duration_s = args.duration
    if args.period is not None:
        cfg.period_s = args.period

    return run_smoke(cfg, args.allow_motion, args.velocity)


if __name__ == "__main__":
    raise SystemExit(main())
