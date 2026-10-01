"""Test-only child-process network tripwire. Never shipped in the wheel."""

import os
import socket
from pathlib import Path

LOG = Path(os.environ["NETWORK_GUARD_LOG"])
LOG.write_text("guard-loaded\n")
_original_connect = socket.socket.connect
_original_connect_ex = socket.socket.connect_ex


def _record(address):
    with LOG.open("a") as stream:
        stream.write(f"blocked: {address!r}\n")
    raise RuntimeError("Network is blocked in the offline integration test")


def connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _record(address)
    return _original_connect(self, address)


def connect_ex(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        _record(address)
    return _original_connect_ex(self, address)


def getaddrinfo(*args, **kwargs):
    _record(args)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
