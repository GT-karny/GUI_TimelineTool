#!/usr/bin/env python3
"""
Utility that sends repeated binary float payloads for testing receivers.

Each datagram is little-endian float32 values. You can provide an explicit list
of floats or let the script generate a ramp that advances every tick.
"""

from __future__ import annotations

import argparse
import socket
import struct
import time
from typing import List


def _parse_values(values: str | None) -> List[float]:
    if not values:
        return [0.0]
    parsed: List[float] = []
    for part in values.split(","):
        part = part.strip()
        if not part:
            continue
        parsed.append(float(part))
    return parsed or [0.0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Binary telemetry test sender")
    parser.add_argument("--host", default="127.0.0.1", help="Destination host")
    parser.add_argument("--port", type=int, default=9000, help="Destination UDP port")
    parser.add_argument(
        "--values",
        type=str,
        default="",
        help="Comma-separated float list (default: [0.0])",
    )
    parser.add_argument(
        "--increment",
        type=float,
        default=0.0,
        help="Value added to each float after every send",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="Delay between packets in seconds",
    )
    args = parser.parse_args()

    values = _parse_values(args.values)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    destination = (args.host, args.port)
    print(f"Sending {len(values)} float32 values to udp://{args.host}:{args.port}")

    fmt = "<" + "f" * len(values)
    while True:
        packet = struct.pack(fmt, *values)
        sock.sendto(packet, destination)
        print("sent:", values)
        if args.increment:
            values = [v + args.increment for v in values]
        time.sleep(max(0.0, args.interval))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")

