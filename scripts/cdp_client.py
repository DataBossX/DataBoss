"""Minimal Chrome DevTools Protocol client (standard library only).

Playwright cannot be installed in this environment, but the Chromium binary is
present and speaks CDP over a WebSocket. This implements just enough of RFC 6455
-- client handshake, masked text frames, unfragmented reads -- to call
``Runtime.evaluate`` in a real page.

Scope is deliberately small: single-frame text messages, no compression, no
continuation frames. That is all CDP needs for evaluate-and-read-back.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from typing import Optional

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


class WebSocket:
    def __init__(self, url: str, timeout: float = 30.0):
        if not url.startswith("ws://"):
            raise ValueError(f"only ws:// is supported, got {url}")
        rest = url[len("ws://"):]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.path = "/" + path
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        self.sock.settimeout(timeout)
        self._buffer = b""
        self._handshake(hostport)

    def _handshake(self, hostport: str) -> None:
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {hostport}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        while b"\r\n\r\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("connection closed during handshake")
            self._buffer += chunk
        header, _, remainder = self._buffer.partition(b"\r\n\r\n")
        if b"101" not in header.split(b"\r\n")[0]:
            raise ConnectionError(f"handshake failed: {header[:200]!r}")
        self._buffer = remainder

    def _recv_exact(self, count: int) -> bytes:
        while len(self._buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("connection closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def send(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])              # FIN + text opcode
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)        # client frames are always masked
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask = secrets.token_bytes(4)
        header += mask
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    def recv(self) -> str:
        while True:
            first, second = self._recv_exact(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._recv_exact(8))[0]
            if second & 0x80:                    # server frames are never masked
                mask = self._recv_exact(4)
                payload = bytes(b ^ mask[i % 4]
                                for i, b in enumerate(self._recv_exact(length)))
            else:
                payload = self._recv_exact(length)

            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise ConnectionError("server closed the websocket")
            if opcode == 0x9:                    # ping -> pong
                self.sock.sendall(b"\x8a\x80" + secrets.token_bytes(4))

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class HeadlessPage:
    """Launch Chromium with CDP enabled and evaluate JavaScript in a real page."""

    def __init__(self, *, width: int = 390, height: int = 844, port: int = 0,
                 reduced_motion: bool = False, extra_flags=()):
        self.profile = tempfile.mkdtemp(prefix="cdp-")
        self.port = port or self._free_port()
        flags = [
            "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
            "--hide-scrollbars", "--force-color-profile=srgb",
            f"--user-data-dir={self.profile}",
            f"--window-size={width},{height}",
            f"--remote-debugging-port={self.port}",
            "about:blank",
        ]
        if reduced_motion:
            flags.insert(-1, "--force-prefers-reduced-motion")
        flags[-1:-1] = list(extra_flags)
        self.proc = subprocess.Popen([CHROME, *flags],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.ws: Optional[WebSocket] = None
        self._id = 0
        self._connect()

    @staticmethod
    def _free_port() -> int:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]

    def _connect(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                raw = urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/list", timeout=3).read()
                targets = json.loads(raw)
                page = next(t for t in targets if t.get("type") == "page")
                self.ws = WebSocket(page["webSocketDebuggerUrl"])
                return
            except Exception as exc:
                last = exc
                time.sleep(0.3)
        raise RuntimeError(f"could not attach to Chromium: {last}")

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 40.0) -> dict:
        self._id += 1
        message_id = self._id
        self.ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = json.loads(self.ws.recv())
            if message.get("id") == message_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message.get("result", {})
        raise TimeoutError(f"{method} timed out")

    def goto(self, url: str, *, settle_seconds: float = 3.0) -> None:
        self.call("Page.enable")
        self.call("Page.navigate", {"url": url})
        time.sleep(settle_seconds)               # let the app fetch and render

    def wait_for(self, expression: str, *, timeout: float = 25.0,
                 interval: float = 0.35) -> bool:
        """Poll a JS predicate until it is true.

        Fixed sleeps make screenshot suites flaky under load; this waits for the
        app to actually be ready instead of guessing how long that takes.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if self.evaluate(f"!!({expression})"):
                    return True
            except RuntimeError:
                pass                             # page mid-navigation
            time.sleep(interval)
        return False

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True,
        })
        if result.get("exceptionDetails"):
            raise RuntimeError(result["exceptionDetails"].get("text", "evaluation failed"))
        return result["result"].get("value")

    def screenshot(self, path: str) -> int:
        data = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        raw = base64.b64decode(data["data"])
        with open(path, "wb") as handle:
            handle.write(raw)
        return len(raw)

    def close(self) -> None:
        if self.ws:
            self.ws.close()
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        import shutil

        shutil.rmtree(self.profile, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
