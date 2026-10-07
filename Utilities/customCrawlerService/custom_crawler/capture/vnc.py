"""Dedicated Xvfb + x11vnc + websockify for interactive profile capture.

Capture must not reuse the crawl service DISPLAY. x11vnc listens on localhost only;
the FastAPI app reverse-proxies noVNC under /vnc-proxy/<token>/<wsPort>/.
"""
from __future__ import annotations

import logging
import os
import secrets
import socket
import subprocess
import tempfile
import time
from typing import List, Optional

from ..engine.bins import YUM_INSTALL_HINT, resolve_bin
from ..obs.logging import log, setup_logger

logger = setup_logger("custom_crawler.capture.vnc")

_STARTUP_WAIT = 0.6

# Stay above the crawl Xvfb range (:20–:99) in engine.xvfb.
DISPLAY_RANGE_START = 100
DISPLAY_RANGE_END = 119
# 5900+display would land on 6000+, which is the X11 TCP range (6000+display),
# so x11vnc loses the bind race against any local X server.
VNC_PORT_START = 5901
VNC_PORT_END = 5999
WS_PORT_START = 6080
WS_PORT_END = 6180


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _find_free_port(start: int, end: int) -> Optional[int]:
    for port in range(start, end + 1):
        if _is_port_free(port):
            return port
    return None


def _find_free_display(start: int, end: int) -> Optional[int]:
    for num in range(start, end + 1):
        lock_file = f"/tmp/.X{num}-lock"
        socket_file = f"/tmp/.X11-unix/X{num}"
        if not os.path.exists(lock_file) and not os.path.exists(socket_file):
            return num
    return None


class CaptureVncStack:
    """Lifecycle for one capture: Xvfb + localhost x11vnc + websockify/noVNC."""

    def __init__(
        self,
        *,
        novnc_web_dir: str = "/opt/noVNC",
        screen: str = "1280x900x24",
    ) -> None:
        self.novnc_web_dir = novnc_web_dir
        self.screen = screen
        self.display_num: Optional[int] = None
        self.vnc_port: Optional[int] = None
        self.ws_port: Optional[int] = None
        self.session_token = ""
        self.vnc_password = ""
        self.vnc_url = ""
        self._xvfb_proc: Optional[subprocess.Popen] = None
        self._x11vnc_proc: Optional[subprocess.Popen] = None
        self._websockify_proc: Optional[subprocess.Popen] = None
        self._passwd_file: Optional[str] = None
        self._xvfb_bin = resolve_bin("Xvfb")
        self._x11vnc_bin = resolve_bin("x11vnc")
        self._websockify_bin = resolve_bin("websockify")

    @property
    def display(self) -> Optional[str]:
        return f":{self.display_num}" if self.display_num is not None else None

    def check_prerequisites(self) -> List[str]:
        missing: List[str] = []
        if not self._xvfb_bin:
            missing.append("Xvfb")
        if not self._x11vnc_bin:
            missing.append("x11vnc")
        if not self._websockify_bin:
            missing.append("websockify")
        if self.novnc_web_dir and not os.path.isdir(self.novnc_web_dir):
            missing.append(f"noVNC web dir ({self.novnc_web_dir})")
        return missing

    def start(self) -> str:
        missing = self.check_prerequisites()
        if missing:
            raise RuntimeError(
                "VNC prerequisites missing: " + ", ".join(missing) + ". " + YUM_INSTALL_HINT
            )

        self.display_num = _find_free_display(DISPLAY_RANGE_START, DISPLAY_RANGE_END)
        if self.display_num is None:
            raise RuntimeError(
                f"No free X display in range :{DISPLAY_RANGE_START}-:{DISPLAY_RANGE_END}"
            )
        self.vnc_port = _find_free_port(VNC_PORT_START, VNC_PORT_END)
        if self.vnc_port is None:
            raise RuntimeError(f"No free VNC port in range {VNC_PORT_START}-{VNC_PORT_END}")
        self.ws_port = _find_free_port(WS_PORT_START, WS_PORT_END)
        if self.ws_port is None:
            raise RuntimeError(f"No free WebSocket port in range {WS_PORT_START}-{WS_PORT_END}")
        self.session_token = secrets.token_urlsafe(32)
        self.vnc_password = secrets.token_urlsafe(12)

        # Do not set process-wide DISPLAY — crawl jobs use the service Xvfb.
        self._start_xvfb()
        self._start_x11vnc()
        self._start_websockify()
        self.vnc_url = self._build_url()
        log(
            logger,
            logging.INFO,
            "capture VNC ready",
            display=self.display,
            vncPort=self.vnc_port,
            wsPort=self.ws_port,
        )
        return self.vnc_url

    def chrome_env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY",)}
        env["DISPLAY"] = self.display or ""
        env["XDG_SESSION_TYPE"] = "x11"
        env["GDK_BACKEND"] = "x11"
        env["QT_QPA_PLATFORM"] = "xcb"
        return env

    def stop(self) -> None:
        for name, proc in (
            ("websockify", self._websockify_proc),
            ("x11vnc", self._x11vnc_proc),
            ("Xvfb", self._xvfb_proc),
        ):
            if proc is None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
            log(logger, logging.INFO, "stopped capture process", name=name)
        self._xvfb_proc = self._x11vnc_proc = self._websockify_proc = None
        if self._passwd_file:
            try:
                os.remove(self._passwd_file)
            except OSError:
                pass
            self._passwd_file = None

    def _build_url(self) -> str:
        from urllib.parse import quote

        token = self.session_token
        pw = self.vnc_password
        port = self.ws_port
        base = f"/vnc-proxy/{token}/{port}/vnc.html"
        # Absolute path is required: a relative path is resolved under
        # /vnc-proxy/<token>/<port>/ and becomes a doubled URL → WS 403.
        path = f"/vnc-proxy/{token}/{port}/websockify"
        return (
            f"{base}?autoconnect=true&resize=scale"
            f"&path={quote(path, safe='/')}&password={quote(pw, safe='')}"
        )

    def _cleanup_stale_display(self) -> None:
        import signal

        num = self.display_num
        if num is None:
            return
        lock_file = f"/tmp/.X{num}-lock"
        if os.path.exists(lock_file):
            try:
                with open(lock_file) as f:
                    stale_pid = int(f.read().strip())
                os.kill(stale_pid, signal.SIGTERM)
                time.sleep(0.3)
            except (ProcessLookupError, ValueError, OSError):
                pass
            try:
                os.remove(lock_file)
            except OSError:
                pass
        try:
            os.remove(f"/tmp/.X11-unix/X{num}")
        except OSError:
            pass

    def _start_xvfb(self) -> None:
        self._cleanup_stale_display()
        cmd = [self._xvfb_bin, f":{self.display_num}", "-screen", "0", self.screen, "-ac", "-nolisten", "tcp"]
        self._xvfb_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(_STARTUP_WAIT)
        if self._xvfb_proc.poll() is not None:
            raise RuntimeError(f"Xvfb exited immediately (display :{self.display_num})")

    def _start_x11vnc(self) -> None:
        fd, self._passwd_file = tempfile.mkstemp(prefix="vnc_pw_", suffix=".txt")
        try:
            os.write(fd, (self.vnc_password or "").encode("utf-8"))
        finally:
            os.close(fd)
        os.chmod(self._passwd_file, 0o600)
        cmd = [
            self._x11vnc_bin,
            "-display",
            f":{self.display_num}",
            "-rfbport",
            str(self.vnc_port),
            "-passwdfile",
            self._passwd_file,
            "-localhost",
            "-noxdamage",
            "-forever",
            "-shared",
        ]
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "GDK_BACKEND")}
        env["XDG_SESSION_TYPE"] = "x11"
        err_r, err_w = os.pipe()
        self._x11vnc_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=err_w, env=env
        )
        os.close(err_w)
        time.sleep(_STARTUP_WAIT)
        if self._x11vnc_proc.poll() is not None:
            err = os.read(err_r, 65536).decode("utf-8", errors="replace")
            os.close(err_r)
            try:
                os.remove(self._passwd_file)
            except OSError:
                pass
            self._passwd_file = None
            # x11vnc prints a long banner before failing, so the cause is in the tail.
            raise RuntimeError(f"x11vnc exited immediately (port {self.vnc_port}): {err[-600:]}")
        os.close(err_r)

    def _start_websockify(self) -> None:
        cmd = [self._websockify_bin]
        if os.path.isdir(self.novnc_web_dir):
            cmd += ["--web", self.novnc_web_dir]
        cmd += [f"127.0.0.1:{self.ws_port}", f"127.0.0.1:{self.vnc_port}"]
        self._websockify_proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(_STARTUP_WAIT)
        if self._websockify_proc.poll() is not None:
            raise RuntimeError(f"websockify exited immediately (ws port {self.ws_port})")
