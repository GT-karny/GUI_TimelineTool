import logging
import socket
import struct
import threading
import time

import pytest

from app.net.udp_receiver import UdpReceiverService


def _get_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.mark.parametrize("fmt,expected", [("!f", 12.34), ("<f", 56.78)])
def test_udp_receiver_handles_float_payloads(fmt: str, expected: float) -> None:
    received = []
    received_event = threading.Event()

    def on_receive(value: float) -> None:
        received.append(value)
        received_event.set()

    port = _get_free_port()
    receiver = UdpReceiverService(port, on_receive)
    receiver.start()
    time.sleep(0.05)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(struct.pack(fmt, expected), ("127.0.0.1", port))

        assert received_event.wait(1.0)
        assert received[0] == pytest.approx(expected)
    finally:
        receiver.stop()


@pytest.mark.parametrize("fmt,expected", [("!d", 123456.789), ("<d", 9876.54321)])
def test_udp_receiver_handles_double_payloads(fmt: str, expected: float) -> None:
    received = []
    received_event = threading.Event()

    def on_receive(value: float) -> None:
        received.append(value)
        received_event.set()

    port = _get_free_port()
    receiver = UdpReceiverService(port, on_receive)
    receiver.start()
    time.sleep(0.05)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(struct.pack(fmt, expected), ("127.0.0.1", port))

        assert received_event.wait(1.0)
        assert received[0] == pytest.approx(expected)
    finally:
        receiver.stop()


def test_udp_receiver_logs_unexpected_payload_size(caplog: pytest.LogCaptureFixture) -> None:
    received_event = threading.Event()

    def on_receive(_: float) -> None:
        received_event.set()

    port = _get_free_port()
    receiver = UdpReceiverService(port, on_receive)
    receiver.start()
    time.sleep(0.05)

    caplog.set_level(logging.WARNING)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(b"\x00\x01", ("127.0.0.1", port))

        assert not received_event.wait(0.2)
        assert any(
            "unexpected packet size" in message
            for _, __, message in caplog.record_tuples
        )
    finally:
        receiver.stop()
