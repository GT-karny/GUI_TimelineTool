#!/usr/bin/env python3
"""
Test script for Playback Sync Mode.
Sends a float time value to localhost:9001 (default) and listens for telemetry on localhost:9000.
"""
import json
import socket
import struct
import threading
import time

SYNC_HOST = "127.0.0.1"
SYNC_PORT = 9001
TELEMETRY_PORT = 9000

def telemetry_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", TELEMETRY_PORT))
    print(f"Listening for telemetry on port {TELEMETRY_PORT}...")
    
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            text = data.decode("utf-8")
            payload = json.loads(text)
            print(f"[Recv] {payload}")
        except Exception as e:
            print(f"Error receiving: {e}")

def main():
    # Start listener thread
    t = threading.Thread(target=telemetry_listener, daemon=True)
    t.start()

    # Sender loop
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    current_time = 0.0
    print(f"Sending sync packets to {SYNC_HOST}:{SYNC_PORT} (Ctrl+C to stop)...")
    
    try:
        while True:
            # Pack float as 4 bytes (Little Endian)
            packet = struct.pack("<f", current_time)
            sock.sendto(packet, (SYNC_HOST, SYNC_PORT))
            print(f"[Send] Time: {current_time:.2f}s")
            
            current_time += 0.5
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
