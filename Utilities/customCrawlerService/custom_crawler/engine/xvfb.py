"""Hardened Xvfb management using -displayfd.

The parent service starts a single shared Xvfb. Display numbers are chosen from
``FIRST_DISPLAY_NUMBER`` upward so we never collide with the real desktop (:0/:1).
Stale ``/tmp/.X11-unix/XN`` sockets left by a killed prior run are cleaned before
each attempt, and if a number is still taken we walk the range instead of dying.
"""
from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import Optional

from .bins import resolve_bin


# Start well above the desktop / XWayland range (:0/:1).
FIRST_DISPLAY_NUMBER = 20
MAX_DISPLAY_NUMBER = 99


class XvfbDisplay:
    def __init__(self, mode: str = "auto", screen: str = "1280x900x24") -> None:
        self.mode = (mode or "auto").lower()
        self.screen = screen
        self.proc: Optional[subprocess.Popen] = None
        self.display: Optional[str] = None
        # True only when this process spawned Xvfb; False when reusing an existing DISPLAY
        # (in which case headed Chrome renders on the real desktop and is visible).
        self.owned = False
        self._read_fd: Optional[int] = None
        self._prev_display = os.environ.get("DISPLAY")
        self._monitor: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def available() -> bool:
        return resolve_bin("Xvfb") is not None

    @staticmethod
    def _clear_stale(display_num: int) -> None:
        """Remove lock/socket for ``:N`` only when no live process owns them."""
        lock = f"/tmp/.X{display_num}-lock"
        sock = f"/tmp/.X11-unix/X{display_num}"
        # If an Xvfb (or other X server) is already bound to this number, leave it alone.
        try:
            out = subprocess.check_output(["ps", "-eo", "args"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            out = ""
        needle = f"Xvfb :{display_num}"
        if any(needle in line for line in out.splitlines()):
            return
        for path in (lock, sock):
            try:
                if os.path.exists(path) or os.path.islink(path):
                    os.unlink(path)
            except OSError:
                pass

    def _spawn_one(self, display_num: int) -> Optional[str]:
        """Try to start Xvfb on ``:display_num``. Return ``':N'`` or None."""
        xvfb = resolve_bin("Xvfb")
        if not xvfb:
            return None
        self._clear_stale(display_num)
        read_fd, write_fd = os.pipe()
        try:
            self.proc = subprocess.Popen(
                [
                    xvfb,
                    f":{display_num}",
                    "-displayfd",
                    str(write_fd),
                    "-screen",
                    "0",
                    self.screen,
                    "-ac",
                    "-nolisten",
                    "tcp",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                pass_fds=(write_fd,),
                close_fds=True,
            )
        finally:
            os.close(write_fd)
        self._read_fd = read_fd

        deadline = time.time() + 5.0
        buf = b""
        os.set_blocking(read_fd, False)
        while time.time() < deadline:
            if self.proc.poll() is not None:
                break
            try:
                chunk = os.read(read_fd, 64)
            except BlockingIOError:
                chunk = b""
            if chunk:
                buf += chunk
                if b"\n" in buf:
                    break
            else:
                time.sleep(0.05)
        try:
            os.close(read_fd)
        except OSError:
            pass
        self._read_fd = None

        num = buf.decode("ascii", "ignore").strip()
        if not num.isdigit() or self.proc.poll() is not None:
            # Drain stderr for diagnostics, then tear down.
            err = b""
            try:
                if self.proc.stderr:
                    err = self.proc.stderr.read() or b""
            except Exception:
                pass
            if self.proc and self.proc.poll() is None:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=2)
                except Exception:
                    try:
                        self.proc.kill()
                    except Exception:
                        pass
            self.proc = None
            if err:
                # Keep quiet unless every candidate fails (caller raises).
                pass
            return None
        display = f":{num}"
        self.display = display
        return display

    def _spawn(self) -> Optional[str]:
        # Walk :20..:99 so a stale socket on :20 (from a killed prior run) cannot
        # take the whole service down.
        for n in range(FIRST_DISPLAY_NUMBER, MAX_DISPLAY_NUMBER + 1):
            display = self._spawn_one(n)
            if display is not None:
                return display
        return None

    def start(self) -> Optional[str]:
        # "never" / "auto"-with-a-display reuse the real desktop: Chrome stays headed and
        # therefore VISIBLE. Only mode="always" guarantees an off-screen virtual display.
        if self.mode == "never":
            self.display = self._prev_display
            return self.display
        if self.mode == "auto" and self._prev_display:
            self.display = self._prev_display
            return self.display
        if not self.available():
            if self.mode == "always":
                raise RuntimeError("Xvfb requested (always) but not installed")
            self.display = self._prev_display
            return self.display

        display = self._spawn()
        if display is None:
            if self.mode == "always":
                raise RuntimeError(
                    "Failed to start Xvfb on any display "
                    f":{FIRST_DISPLAY_NUMBER}-:{MAX_DISPLAY_NUMBER} "
                    "(check stale /tmp/.X11-unix/XN sockets)"
                )
            self.display = self._prev_display
            return self.display

        os.environ["DISPLAY"] = display
        # Chrome / GTK prefer Wayland when WAYLAND_DISPLAY or GDK_BACKEND=wayland is set, or
        # when a wayland socket exists under XDG_RUNTIME_DIR — that bypasses Xvfb and paints
        # a real window on the desktop. Force the X11 path for every child of this process.
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ["GDK_BACKEND"] = "x11"
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        self.owned = True
        self._start_monitor()
        return display

    def _start_monitor(self) -> None:
        def _watch() -> None:
            while not self._stop.is_set():
                time.sleep(2.0)
                if self.proc is not None and self.proc.poll() is not None and not self._stop.is_set():
                    self._spawn()
                    if self.display:
                        os.environ["DISPLAY"] = self.display

        self._monitor = threading.Thread(target=_watch, name="xvfb-monitor", daemon=True)
        self._monitor.start()

    def stop(self) -> None:
        self._stop.set()
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None
        if self._prev_display is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = self._prev_display
