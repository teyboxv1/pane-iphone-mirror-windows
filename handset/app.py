"""Desktop launcher: runs the server and opens Pane in its own app window.

Closing the window quits Pane. Launching a second copy just opens another
window onto the running one.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from handset.airplay import start_airplay_receiver, stop_airplay_receiver
from handset.server import HOST, PORT, Handler, SingleServer
from handset.window import start_caption_stripper

PORT = int(os.environ.get("PANE_PORT", PORT))
URL = f"http://{HOST}:{PORT}/"
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Pane"

BROWSERS = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
)


def _setup_logging() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(DATA_DIR / "pane.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    # A windowed exe has no console, so print() and tracebacks would be lost.
    if sys.stdout is None or sys.stderr is None:
        log = open(DATA_DIR / "pane.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def _already_running() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((HOST, PORT)) == 0


def _open_window() -> subprocess.Popen | None:
    for browser in BROWSERS:
        if browser.is_file():
            # A dedicated profile makes this its own process, so we can tell
            # when the user closes the window.
            proc = subprocess.Popen(
                [
                    str(browser),
                    f"--app={URL}",
                    f"--user-data-dir={DATA_DIR / 'window'}",
                    "--window-size=1280,860",
                    "--no-first-run",
                    "--no-default-browser-check",
                ]
            )
            start_caption_stripper()
            return proc
    webbrowser.open(URL)
    return None


def main() -> None:
    _setup_logging()
    if _already_running():
        _open_window()
        return

    server = SingleServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, name="pane-server", daemon=True).start()
    logging.info("Pane listening on %s", URL)

    start_airplay_receiver()

    window = _open_window()
    if window is None:
        # No Chrome or Edge: the page is in the default browser; keep serving.
        while True:
            time.sleep(3600)
    window.wait()
    stop_airplay_receiver()
    server.shutdown()
    os._exit(0)


if __name__ == "__main__":
    main()
