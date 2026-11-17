"""Local device window. Binds to loopback only."""

from __future__ import annotations

import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from handset.device import read_handset, snapshot
from handset.mux import MuxError
from handset.airplay import airplay_status
from handset.screen import restart_screen, screen_status, start_screen
from handset.wifi import pair_for_wifi, wifi_discovery_snapshot, wifi_paired_udids
from handset.window import ALLOWED_ACTIONS, window_action

ROOT = Path(__file__).resolve().parent / "web"
HOST = "127.0.0.1"
PORT = 8765
MIRROR_PREFIX = "/mirror"
STREAM_HOST = "127.0.0.1"
STREAM_PORT = 8766
_HOP_BY_HOP = frozenset(
    {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "upgrade"}
)
_CLIENT_GONE = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except _CLIENT_GONE:
            pass
        except Exception:
            try:
                if not self.wfile.closed:
                    self._json({"error": "Internal server error."}, status=500)
            except Exception:
                pass

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == MIRROR_PREFIX or path.startswith(f"{MIRROR_PREFIX}/"):
            self._proxy_mirror("GET")
            return
        if path == "/api/status":
            payload = snapshot()
            payload["screen"] = screen_status()
            payload["wifi"] = {"paired": wifi_paired_udids()}
            self._json(payload)
            return
        if path == "/api/screen":
            self._json(screen_status())
            return
        if path == "/api/airplay/status":
            self._json(airplay_status())
            return
        if path == "/api/wifi/discover":
            import asyncio

            self._json(asyncio.run(wifi_discovery_snapshot()))
            return
        if path.startswith("/api/devices/"):
            udid = unquote(path.removeprefix("/api/devices/")).strip("/")
            if not udid or "/" in udid:
                self._json({"error": "Missing device id."}, status=400)
                return
            self._device(udid)
            return
        self._file(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == MIRROR_PREFIX or path.startswith(f"{MIRROR_PREFIX}/"):
            self._proxy_mirror("POST")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        udid = payload.get("udid") if isinstance(payload.get("udid"), str) else None
        if path == "/api/screen/restart":
            self._json(restart_screen(udid))
            return
        if path == "/api/wifi/pair":
            if not udid:
                self._json({"ok": False, "error": "Plug in the iPhone first."}, status=400)
                return
            self._json(pair_for_wifi(udid))
            return
        if path.startswith("/api/window/"):
            action = path.removeprefix("/api/window/").strip("/")
            if not action or action not in ALLOWED_ACTIONS:
                self._json({"ok": False, "error": "Unknown window action."}, status=400)
                return
            width = int(payload.get("width") or 0)
            height = int(payload.get("height") or 0)
            self._json({"ok": window_action(action, width, height)})
            return
        if path != "/api/screen":
            self._json({"error": "Unknown action."}, status=404)
            return
        transport = payload.get("transport")
        if transport not in {"auto", "usb", "wifi"}:
            transport = "auto"
        self._json(start_screen(udid, transport))

    def log_message(self, fmt: str, *args) -> None:
        return

    def _device(self, udid: str) -> None:
        try:
            self._json(read_handset(udid))
        except MuxError as error:
            self._json({"udid": udid, "paired": False, "error": str(error)}, status=409)

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _mirror_upstream_path(self) -> str:
        path = unquote(urlparse(self.path).path)
        upstream = path.removeprefix(MIRROR_PREFIX) or "/"
        if not upstream.startswith("/"):
            upstream = f"/{upstream}"
        query = urlparse(self.path).query
        return upstream + (f"?{query}" if query else "")

    def _write_client(self, data: bytes) -> bool:
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except _CLIENT_GONE:
            return False
        return True

    def _proxy_mirror_stream(self, method: str, target: str) -> None:
        """Relay the live body de-chunked; close the client connection after the stream."""
        conn = http.client.HTTPConnection(STREAM_HOST, STREAM_PORT, timeout=600)
        started = False
        self.close_connection = True
        try:
            conn.request(method, target, headers={"Connection": "close"})
            response = conn.getresponse()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() in _HOP_BY_HOP or key.lower() in {"transfer-encoding", "content-length"}:
                    continue
                self.send_header(key, value)
            self.end_headers()
            started = True
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                if not self._write_client(chunk):
                    return
        except (OSError, http.client.HTTPException) as error:
            if not started:
                self._json({"error": f"Screen stream is not running ({error})."}, status=503)
        finally:
            conn.close()

    def _proxy_mirror(self, method: str) -> None:
        target = self._mirror_upstream_path()
        upstream_path = target.split("?", 1)[0]
        is_live_stream = method == "GET" and upstream_path.endswith(".bin")
        if is_live_stream:
            self._proxy_mirror_stream(method, target)
            return

        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length and method in {"POST", "PUT"} else None

        headers: dict[str, str] = {}
        for name in ("Content-Type", "Accept"):
            value = self.headers.get(name)
            if value:
                headers[name] = value

        conn = http.client.HTTPConnection(STREAM_HOST, STREAM_PORT, timeout=120)
        started = False
        try:
            conn.request(method, target, body=body, headers=headers)
            response = conn.getresponse()
            payload = response.read()
            self.send_response(response.status)
            started = True
            for key, value in response.getheaders():
                if key.lower() in _HOP_BY_HOP:
                    continue
                self.send_header(key, value)
            self.end_headers()
            if payload:
                self._write_client(payload)
        except OSError as error:
            if not started:
                self._json({"error": f"Screen stream is not running ({error})."}, status=503)
        finally:
            conn.close()

    def _file(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        root = ROOT.resolve()
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            self._json({"error": "Not found."}, status=404)
            return
        if not target.is_file():
            self._json({"error": "Not found."}, status=404)
            return
        kind = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


class SingleServer(ThreadingHTTPServer):
    # On Windows, address reuse lets a second copy bind the same port and steal requests.
    allow_reuse_address = False


def main() -> None:
    server = SingleServer((HOST, PORT), Handler)
    print(f"Handset listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
