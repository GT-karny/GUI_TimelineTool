#!/usr/bin/env python3
"""Minimal UDP telemetry receiver for local testing."""

import json
import socket


def main() -> None:
    host = "127.0.0.1"
    port = 9000
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"Listening for telemetry on {host}:{port} (Ctrl+C to exit)")

    try:
        while True:
            data, addr = sock.recvfrom(65535)
            try:
                text = data.decode("utf-8")
                payload = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                preview = data[:200]
                print(
                    f"{addr} decode error: {exc} (length={len(data)}) preview={preview!r}"
                )
                continue

            print(f"{addr} -> {json.dumps(payload, ensure_ascii=False)}")
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
