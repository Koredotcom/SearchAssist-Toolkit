#!/usr/bin/env bash
# Install Xvfb, x11vnc, websockify, and noVNC on yum/dnf servers (RHEL, CentOS, Amazon Linux).
# Run as a user that can sudo. Activate the Findly venv first so websockify lands on PATH.
#
#   source /data/sa_py3.13.7/Findly/bin/activate   # or your venv
#   sudo -E bash tools/install_vnc_deps_yum.sh
set -euo pipefail

NOVNC_VERSION="${NOVNC_VERSION:-1.5.0}"
NOVNC_DIR="${CRAWLER_NOVNC_WEB_DIR:-/opt/noVNC}"

if command -v dnf >/dev/null 2>&1; then
  PKG=dnf
elif command -v yum >/dev/null 2>&1; then
  PKG=yum
else
  echo "Neither yum nor dnf found. This script is for RHEL/CentOS/Amazon Linux." >&2
  exit 1
fi

# x11vnc lives in EPEL on most yum distros.
if ! rpm -q epel-release >/dev/null 2>&1; then
  $PKG install -y epel-release || true
fi

$PKG install -y \
  xorg-x11-server-Xvfb \
  x11vnc \
  wget \
  tar \
  gzip \
  python3-pip || true

# Some Amazon Linux builds name the Xvfb package without the xorg- prefix.
if ! command -v Xvfb >/dev/null 2>&1 && ! test -x /usr/bin/Xvfb; then
  $PKG install -y Xvfb || $PKG install -y xorg-x11-server-Xvfb
fi

if ! command -v x11vnc >/dev/null 2>&1 && ! test -x /usr/bin/x11vnc; then
  echo "x11vnc is not in the default repos. Enable EPEL and retry: sudo $PKG install -y epel-release x11vnc" >&2
  exit 1
fi

PY="${PYTHON:-python3}"
if command -v python >/dev/null 2>&1; then
  PY=python
fi
"$PY" -m pip install -U websockify

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
wget -qO "$tmpdir/novnc.tgz" \
  "https://github.com/novnc/noVNC/archive/refs/tags/v${NOVNC_VERSION}.tar.gz"
mkdir -p "$(dirname "$NOVNC_DIR")"
rm -rf "$NOVNC_DIR"
tar xzf "$tmpdir/novnc.tgz" -C "$tmpdir"
mv "$tmpdir/noVNC-${NOVNC_VERSION}" "$NOVNC_DIR"

echo "Installed:"
echo "  Xvfb       = $(command -v Xvfb || echo /usr/bin/Xvfb)"
echo "  x11vnc     = $(command -v x11vnc || echo /usr/bin/x11vnc)"
echo "  websockify = $(command -v websockify || true)"
echo "  noVNC      = $NOVNC_DIR"
echo
echo "Then:"
echo "  export CRAWLER_XVFB_MODE=always"
echo "  export CRAWLER_NOVNC_WEB_DIR=$NOVNC_DIR"
echo "  export CRAWLER_PROFILE_ROOT=/data/profiles   # or /data/etc"
echo "  python -m custom_crawler.service"
echo "  # tunnel: ssh -L 8080:127.0.0.1:8080 <server>  then http://127.0.0.1:8080/ui"
