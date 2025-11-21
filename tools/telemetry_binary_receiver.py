#!/usr/bin/env python3
"""
Simple listener for the binary telemetry payload mode.

Each incoming UDP datagram is interpreted as a packed list of little-endian
float32 values. Optionally provide a layout to break the values per track.
"""

from __future__ import annotations

import argparse
import socket
import struct
from typing import Iterable, List


def _parse_layout(layout: str | None) -> List[int]:
    if not layout:
        return []
    result: List[int] = []
    for part in layout.split(","):
        part = part.strip()
        if not part:
            continue
        result.append(max(0, int(part)))
    return result


def _format_values(values: Iterable[float], layout: List[int]) -> str:
    if not layout:
        return ", ".join(f"{v:.4f}" for v in values)

    formatted = []
    idx = 0
    values_list = list(values)
    for track_idx, count in enumerate(layout):
        chunk = values_list[idx : idx + count] if count > 0 else []
        idx += count
        formatted.append(
            f"track[{track_idx}]: "
            + ", ".join(f"{v:.4f}" for v in chunk)
        )
    return " | ".join(formatted)


def main() -> None:
    parser = argparse.ArgumentParser(description="Binary telemetry receiver")
    parser.add_argument("--port", type=int, default=9000, help="UDP port to bind")
    parser.add_argument(
        "--layout",
        type=str,
        default="",
        help="Comma-separated float counts per track (e.g. '1,1,3')",
    )
    args = parser.parse_args()

    layout = _parse_layout(args.layout)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    print(f"Listening for binary telemetry on udp://0.0.0.0:{args.port}")
    if layout:
        total = sum(layout)
        print(f"Expecting {total} float32 values per packet ({layout=})")

    while True:
        data, addr = sock.recvfrom(65535)
        if len(data) % 4 != 0:
            print(f"[WARN] Dropped packet from {addr} (size {len(data)} not divisible by 4)")
            continue
        count = len(data) // 4
        values = struct.unpack("<" + "f" * count, data)
        print(f"[{addr[0]}:{addr[1]}] { _format_values(values, layout) }")


if __name__ == "__main__":
    main()

