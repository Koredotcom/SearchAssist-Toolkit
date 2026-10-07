"""Attach x11vnc (and optional noVNC) to the Xvfb display for interactive warmup.

Used only by ``tools.warmup_profile`` — the crawl path never needs a viewer.
"""
from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from typing import List, Optional

from ..engine.bins import resolve_bin
from ..obs.logging import log, setup_logger

logger = setup_logger("custom_crawler.engine.vnc")


def _guess_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "SERVER_IP"


def _display_num(display: str) -> Optional[int]:
    d = (display or "").strip()
    if d.startswith(":"):
        try:
            return int(d[1:].split(".")[0])
        except ValueError:
            return None
    return None


class ViewAttach:
    """Start x11vnc against an existing DISPLAY (Xvfb already running)."""

    def __init__(self) -> None:
        self.procs: List[subprocess.Popen] = []
        self.vnc_port: Optional[int] = None
        self.ws_port: Optional[int] = None

    def start(self, display: str, *, listen: str = "0.0.0.0", novnc_dir: str = "/opt/noVNC") -> None:
        x11vnc = resolve_bin("x11vnc")
        if x11vnc is None:
            log(logger, logging.WARNING, "x11vnc not installed", fix="sudo bash tools/install_vnc_deps_yum.sh")
            return
        num = _display_num(display)
        if num is None:
            log(logger, logging.WARNING, "cannot attach VNC", display=display)
            return
        self.vnc_port = 5900 + num
        cmd = [
            x11vnc,
            "-display", display,
            "-rfbport", str(self.vnc_port),
            "-forever",
            "-shared",
            "-nopw",
            "-noxdamage",
            "-listen", listen,
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        if proc.poll() is not None:
            log(logger, logging.ERROR, "x11vnc exited immediately")
            return
        self.procs.append(proc)
        ip = _guess_ip()
        print("========== OPEN THIS TO CLICK CLOUDFLARE ==========", flush=True)
        print(f"  VNC Viewer -> {ip}:{self.vnc_port}", flush=True)
        print("  (VPN / same network. Do not expose 59xx to the public internet.)", flush=True)
        print("===================================================", flush=True)

        websockify = resolve_bin("websockify")
        if websockify and os.path.isdir(novnc_dir):
            self.ws_port = 6080
            ws = subprocess.Popen(
                [websockify, "--web", novnc_dir, str(self.ws_port), f"127.0.0.1:{self.vnc_port}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.4)
            if ws.poll() is None:
                self.procs.append(ws)
                print(
                    f"  or browser: http://{ip}:{self.ws_port}/vnc.html?autoconnect=true&resize=scale",
                    flush=True,
                )

    def stop(self) -> None:
        for proc in reversed(self.procs):
            try:
                proc.terminate()
                proc.wait(timeout=4)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.procs.clear()
