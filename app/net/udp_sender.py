"""Threaded UDP sender service used for telemetry packets."""
from __future__ import annotations

import queue
import socket
import threading
import time
from dataclasses import dataclass


@dataclass
class Endpoint:
    """Simple UDP endpoint descriptor."""

    ip: str
    port: int


class UdpSenderService:
    """A background thread that sends the latest payload to an endpoint."""

    def __init__(self, endpoint: Endpoint):
        self.endpoint = endpoint
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the sender thread if it is not already running."""

        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="UdpSenderService",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the sender thread and close the socket."""

        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        self._thread = None
        self._sock = None

    def reconfigure(self, endpoint: Endpoint) -> None:
        """Update the target endpoint used for subsequent packets."""

        with self._lock:
            self.endpoint = endpoint

    def submit(self, payload: bytes) -> None:
        """Submit a payload for sending, keeping only the latest one."""

        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        try:
            self._q.put_nowait(payload)
        except queue.Full:
            pass

    def _run(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(True)
        while not self._stop.is_set():
            try:
                payload = self._q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                with self._lock:
                    addr = (self.endpoint.ip, self.endpoint.port)
                assert self._sock is not None
                self._sock.sendto(payload, addr)
            except OSError:
                time.sleep(0.05)
