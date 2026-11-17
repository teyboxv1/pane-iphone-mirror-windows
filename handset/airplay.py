"""Embedded AirPlay audio receiver (Shairport4w) for Windows."""

from __future__ import annotations

import atexit
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PROCESS: subprocess.Popen | None = None
_ATEXIT_REGISTERED = False
RAOP_PORT = 5000

_SHAIRPORT_NAME = "shairport.exe"


def _find_shairport_bin() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "handset" / "bin" / _SHAIRPORT_NAME)
    here = Path(__file__).resolve().parent
    candidates.extend(
        [
            here / "bin" / _SHAIRPORT_NAME,
            Path(sys.executable).resolve().parent / "handset" / "bin" / _SHAIRPORT_NAME,
            Path.cwd() / "handset" / "bin" / _SHAIRPORT_NAME,
        ]
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def airplay_available() -> bool:
    return _find_shairport_bin() is not None


def configure_registry() -> None:
    """Best-effort Shairport4w registry as 'Pane Audio'."""
    try:
        import winreg

        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Shairport4w")
        winreg.SetValueEx(key, "ApName", 0, winreg.REG_SZ, "Pane Audio")
        winreg.SetValueEx(key, "StartMinimized", 0, winreg.REG_SZ, "yes")
        winreg.SetValueEx(key, "Tray", 0, winreg.REG_SZ, "yes")
        winreg.SetValueEx(key, "TrayTrackInfo", 0, winreg.REG_SZ, "no")
        winreg.SetValueEx(key, "InfoPanel", 0, winreg.REG_SZ, "no")
        winreg.CloseKey(key)
        logger.info("Configured Shairport4w registry as Pane Audio")
    except Exception as error:
        logger.warning("Could not set Shairport4w registry: %s", error)


def start_airplay_receiver() -> bool:
    global _PROCESS, _ATEXIT_REGISTERED
    if _PROCESS is not None and _PROCESS.poll() is None:
        return True

    exe = _find_shairport_bin()
    if exe is None:
        logger.warning("AirPlay receiver binary not found (expected handset/bin/%s)", _SHAIRPORT_NAME)
        return False

    configure_registry()

    try:
        _PROCESS = subprocess.Popen(
            [str(exe)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("AirPlay audio receiver started (PID %s) as Pane Audio", _PROCESS.pid)
        if not _ATEXIT_REGISTERED:
            atexit.register(stop_airplay_receiver)
            _ATEXIT_REGISTERED = True
        return True
    except Exception as error:
        logger.error("Failed to start AirPlay receiver: %s", error)
        _PROCESS = None
        return False


def is_airplay_connected() -> bool:
    global _PROCESS
    if _PROCESS is None or _PROCESS.poll() is not None:
        return False
    try:
        import psutil

        proc = psutil.Process(_PROCESS.pid)
        for conn in proc.net_connections(kind="tcp"):
            status = conn.status
            if status in (psutil.CONN_ESTABLISHED, "ESTABLISHED") and getattr(conn.laddr, "port", None) == RAOP_PORT:
                return True
    except Exception:
        pass
    return False


def stop_airplay_receiver() -> None:
    global _PROCESS
    if _PROCESS is None or _PROCESS.poll() is not None:
        _PROCESS = None
        return
    try:
        _PROCESS.terminate()
        _PROCESS.wait(timeout=2)
        logger.info("AirPlay audio receiver stopped")
    except Exception:
        try:
            _PROCESS.kill()
        except Exception:
            pass
    _PROCESS = None


def airplay_status() -> dict:
    available = airplay_available()
    running = _PROCESS is not None and _PROCESS.poll() is None
    return {
        "available": available,
        "running": running,
        "connected": is_airplay_connected() if running else False,
    }