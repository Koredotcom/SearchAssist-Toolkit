"""Locate yum-installed VNC/X binaries on RHEL/CentOS/Amazon Linux.

``shutil.which`` misses packages when the service PATH is minimal (systemd, nohup).
"""
from __future__ import annotations

import os
import shutil
from typing import Optional

# Absolute paths yum/dnf use on AL2, AL2023, RHEL, CentOS.
_EXTRA_DIRS = ("/usr/bin", "/usr/local/bin", "/bin")

_NAMES = {
    "Xvfb": ("Xvfb",),
    "x11vnc": ("x11vnc",),
    "websockify": ("websockify",),
}

YUM_INSTALL_HINT = (
    "On the crawl server run: "
    "sudo bash tools/install_vnc_deps_yum.sh"
)


def resolve_bin(name: str) -> Optional[str]:
    """Return an executable path for Xvfb / x11vnc / websockify, or None."""
    for candidate in _NAMES.get(name, (name,)):
        found = shutil.which(candidate)
        if found:
            return found
        for directory in _EXTRA_DIRS:
            path = os.path.join(directory, candidate)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
    return None
