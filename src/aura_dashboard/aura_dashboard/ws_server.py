"""ws_server — a minimal, dependency-free WebSocket server (RFC 6455).

Why this exists
---------------
Ubuntu 22.04 ships python3-websockets 9.1, whose legacy protocol still
passes ``loop=`` keyword arguments into asyncio primitives. Python 3.10
removed that keyword, so depending on how the library was installed the
server dies with ``TypeError: ... unexpected keyword argument 'loop'``
the moment it starts (or the moment a client connects) — silently, in a
background thread. The browser then sits on "connecting…" forever.

Rather than pin a library version on every machine that runs the demo,
this module implements the small subset of RFC 6455 that AURA needs
(text frames, ping/pong, close) directly on top of the standard library.
It is threaded, has zero external dependencies, and works identically on
Python 3.8+ — which is exactly what a demo you show a professor needs.

Scope: server-side only, text frames only (AURA speaks JSON), no
extensions, no TLS (localhost demo traffic).
"""

from __future__ import annotations

import base64
import hashlib
import socket
import struct
import threading
from typing import Callable, List, Optional

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes we care about.
_OP_CONT = 0x0
_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA


class _Client:
    """One connected browser: socket + a write lock.

    The write lock matters: broadcasts arrive from the ROS executor
    thread while pongs are written from this client's reader thread.
    Interleaving two frame writes corrupts the stream, so every send on
    a given socket goes through its lock.
    """

    def __init__(self, sock: socket.socket, addr) -> None:
        self.sock = sock
        self.addr = addr
        self.wlock = threading.Lock()
        self.open = True

    # -- frame encoding ----------------------------------------------------

    def send_text(self, text: str) -> bool:
        """Send one text frame. Returns False if the socket is dead."""
        return self._send_frame(_OP_TEXT, text.encode("utf-8"))

    def send_pong(self, payload: bytes) -> bool:
        return self._send_frame(_OP_PONG, payload)

    def send_close(self, code: int = 1000) -> None:
        try:
            self._send_frame(_OP_CLOSE, struct.pack("!H", code))
        except Exception:
            pass

    def _send_frame(self, opcode: int, payload: bytes) -> bool:
        # Server-to-client frames are never masked (RFC 6455 §5.1).
        header = bytearray([0x80 | opcode])          # FIN + opcode
        n = len(payload)
        if n < 126:
            header.append(n)
        elif n < 65536:
            header.append(126)
            header += struct.pack("!H", n)
        else:
            header.append(127)
            header += struct.pack("!Q", n)
        try:
            with self.wlock:
                self.sock.sendall(bytes(header) + payload)
            return True
        except Exception:
            self.open = False
            return False

    def close(self) -> None:
        self.open = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass


class WebSocketServer:
    """Threaded WebSocket server for the AURA operator console.

    Callbacks (all optional, all invoked from the client's reader
    thread):
      on_message(text)          — a text frame arrived from any client
      on_connect(client_send)   — a browser finished the handshake;
                                  ``client_send(text)`` sends only to it
                                  (used to push a state snapshot)
      on_count_change(n)        — number of connected consoles changed
    """

    def __init__(self, host: str, port: int,
                 on_message: Optional[Callable[[str], None]] = None,
                 on_connect: Optional[Callable[[Callable[[str], bool]], None]] = None,
                 on_count_change: Optional[Callable[[int], None]] = None,
                 log: Optional[Callable[[str], None]] = None) -> None:
        self.host = host
        self.port = port
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_count_change = on_count_change
        self.log = log or (lambda s: None)
        self._clients: List[_Client] = []
        self._lock = threading.Lock()
        self._listener: Optional[socket.socket] = None
        self._running = False

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Bind, listen, and accept in a daemon thread. Raises on bind
        failure so a port conflict is loud, not silent."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        self._listener = srv
        self._running = True
        threading.Thread(target=self._accept_loop, daemon=True,
                         name="aura-ws-accept").start()
        self.log(f"WebSocket server listening on ws://{self.host}:{self.port}")

    def stop(self) -> None:
        self._running = False
        with self._lock:
            clients = list(self._clients)
        for c in clients:
            c.send_close()
            c.close()
        if self._listener is not None:
            try:
                self._listener.close()
            except Exception:
                pass

    def count(self) -> int:
        with self._lock:
            return len(self._clients)

    # -- broadcasting (called from the ROS executor thread) -------------------

    def broadcast(self, text: str) -> None:
        """Send ``text`` to every connected console; prune dead sockets."""
        with self._lock:
            clients = list(self._clients)
        dead = [c for c in clients if not c.send_text(text)]
        if dead:
            with self._lock:
                for c in dead:
                    if c in self._clients:
                        self._clients.remove(c)
                n = len(self._clients)
            for c in dead:
                c.close()
            self._notify_count(n)

    # -- internals -------------------------------------------------------------

    def _notify_count(self, n: int) -> None:
        if self.on_count_change:
            try:
                self.on_count_change(n)
            except Exception:
                pass

    def _accept_loop(self) -> None:
        while self._running:
            try:
                sock, addr = self._listener.accept()
            except OSError:
                return  # listener closed
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=self._client_thread, args=(sock, addr),
                             daemon=True, name="aura-ws-client").start()

    def _client_thread(self, sock: socket.socket, addr) -> None:
        try:
            if not self._handshake(sock):
                sock.close()
                return
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            return

        client = _Client(sock, addr)
        with self._lock:
            self._clients.append(client)
            n = len(self._clients)
        self.log(f"console connected ({n})")
        self._notify_count(n)

        if self.on_connect:
            try:
                self.on_connect(client.send_text)
            except Exception:
                pass

        try:
            self._read_loop(client)
        finally:
            with self._lock:
                if client in self._clients:
                    self._clients.remove(client)
                n = len(self._clients)
            client.close()
            self.log(f"console disconnected ({n})")
            self._notify_count(n)

    # -- handshake ---------------------------------------------------------------

    def _handshake(self, sock: socket.socket) -> bool:
        """Read the HTTP upgrade request and reply 101. Returns success."""
        sock.settimeout(5.0)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                return False
            data += chunk
            if len(data) > 16384:
                return False
        sock.settimeout(None)

        headers = {}
        for line in data.split(b"\r\n")[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower()] = v.strip()

        key = headers.get(b"sec-websocket-key")
        if key is None or b"websocket" not in headers.get(b"upgrade", b"").lower():
            sock.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return False

        accept = base64.b64encode(
            hashlib.sha1(key + _WS_GUID.encode()).digest())
        sock.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
        return True

    # -- frame reading ---------------------------------------------------------

    def _recv_exact(self, sock: socket.socket, n: int) -> Optional[bytes]:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _read_loop(self, client: _Client) -> None:
        sock = client.sock
        fragments: List[bytes] = []
        frag_opcode = _OP_TEXT

        while client.open:
            head = self._recv_exact(sock, 2)
            if head is None:
                return
            fin = bool(head[0] & 0x80)
            opcode = head[0] & 0x0F
            masked = bool(head[1] & 0x80)
            length = head[1] & 0x7F

            if length == 126:
                ext = self._recv_exact(sock, 2)
                if ext is None:
                    return
                length = struct.unpack("!H", ext)[0]
            elif length == 127:
                ext = self._recv_exact(sock, 8)
                if ext is None:
                    return
                length = struct.unpack("!Q", ext)[0]

            if length > 1 << 20:      # 1 MiB — nothing the console sends
                client.send_close(1009)
                return

            mask = b""
            if masked:
                mask = self._recv_exact(sock, 4)
                if mask is None:
                    return

            payload = self._recv_exact(sock, length) if length else b""
            if payload is None:
                return
            if masked and payload:
                payload = bytes(b ^ mask[i % 4]
                                for i, b in enumerate(payload))

            if opcode == _OP_PING:
                client.send_pong(payload)
                continue
            if opcode == _OP_PONG:
                continue
            if opcode == _OP_CLOSE:
                client.send_close()
                return
            if opcode in (_OP_TEXT, _OP_BINARY):
                fragments = [payload]
                frag_opcode = opcode
            elif opcode == _OP_CONT:
                fragments.append(payload)
            else:
                continue  # unknown opcode — skip

            if fin and frag_opcode == _OP_TEXT and self.on_message:
                try:
                    self.on_message(b"".join(fragments).decode("utf-8"))
                except Exception:
                    pass
                fragments = []
