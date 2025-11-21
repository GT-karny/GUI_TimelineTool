"""Threaded UDP receiver service for sync mode."""
from __future__ import annotations

import logging
import math
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

        logger = logging.getLogger(__name__)

        while not self._stop.is_set():
            try:
                data, _ = self._sock.recvfrom(1024)
                value = self._decode_payload(data)
                if value is not None:
                    self.on_receive(value)
                else:
                    logger.warning(
                        "UdpReceiverService received unexpected packet size: %s bytes", len(data)
                    )
            except socket.timeout:
                continue
            except OSError:
                # Socket closed or error
                break
            except Exception:
                # Ignore malformed packets
                continue

    def _decode_payload(self, data: bytes) -> Optional[float]:
        """Decode a UDP payload into a float, supporting both endiannesses.

        Sync mode senders may transmit timestamps as little-endian floats even
        though network byte order is big-endian. We attempt to decode in
        network order first and fall back to little-endian when the value looks
        like a near-zero artifact from swapped bytes.
        """

        if len(data) == 4:
            return self._decode_number(
                data, "f", small_threshold=1e-4, large_threshold=1e30
            )
        if len(data) == 8:
            return self._decode_number(
                data, "d", small_threshold=1e-9, large_threshold=1e100
            )
        return None

    @staticmethod
    def _decode_number(
        data: bytes, fmt: str, *, small_threshold: float, large_threshold: float
    ) -> float:
        """Decode a float/double with fallback for little-endian packets."""

        network_value = struct.unpack(f"!{fmt}", data)[0]

        # An all-zero payload is unambiguous, so skip little-endian heuristics
        # to keep the fastest path for the common case.
        if data == b"\x00" * len(data):
            return network_value

        little_value = struct.unpack(f"<{fmt}", data)[0]

        # Prefer little-endian when network order decodes to a denormal/near-zero
        # value but little-endian yields a meaningful magnitude.
        if abs(network_value) < small_threshold and abs(little_value) >= small_threshold:
            return little_value

        # If network order produces an extremely large magnitude (a common
        # artifact of swapped bytes) but the little-endian interpretation is
        # finite and notably smaller, treat the packet as little-endian.
        if (
            (not math.isfinite(network_value)
            or abs(network_value) > large_threshold)
            and math.isfinite(little_value)
            and abs(little_value) < abs(network_value)
        ):
            return little_value

        return network_value
