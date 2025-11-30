"""Threaded UDP receiver service for sync mode."""
from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable, Optional

class UdpReceiverService:
    """A background thread that listens for float values on a UDP port."""

    def __init__(self, port: int, on_receive: Callable[[float], None]):
        self.port = port
        self.on_receive = on_receive
        self._stop = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the receiver thread if it is not already running."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="UdpReceiverService",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the receiver thread and close the socket."""
        self._stop.set()
        if self._sock:
            try:
                # Closing the socket will unblock recvfrom
                self._sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._sock = None

    def reconfigure(self, port: int) -> None:
        """Restart the service with a new port if it changed."""
        if self.port == port and self._thread and self._thread.is_alive():
            return
        
        self.stop()
        self.port = port
        self.start()

    def _run(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("0.0.0.0", self.port))
        # Set a timeout so we can check the stop event periodically if no data comes
        self._sock.settimeout(0.5)

        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(1024)
                if len(data) == 4:
                    # Expecting a 4-byte float (Little Endian)
                    value = struct.unpack("<f", data)[0]
                    self.on_receive(value)
            except socket.timeout:
                continue
            except OSError:
                # Socket closed or error
                break
            except Exception:
                # Ignore malformed packets
                continue
