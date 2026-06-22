#!/usr/bin/env python3
"""Read raw serial text/hex from a DM motor or USB2CANFD CDC port."""

from __future__ import annotations

import argparse
import time

import serial


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a serial port for DM motor boot/config output")
    parser.add_argument("--port", default="COM16")
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()

    deadline = time.monotonic() + args.duration
    print(f"Opening {args.port} @ {args.baud} for {args.duration}s")
    with serial.Serial(args.port, baudrate=args.baud, timeout=0.2) as ser:
        while time.monotonic() < deadline:
            data = ser.read(256)
            if not data:
                continue
            text = data.decode("utf-8", errors="replace")
            hex_text = " ".join(f"{b:02X}" for b in data)
            print(f"TEXT: {text.rstrip()}")
            print(f"HEX : {hex_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
