# Custom Crawler Service — headed google-chrome-stable + Xvfb + Playwright
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: Xvfb, fonts, and the libraries headed Chrome needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg ca-certificates \
        xvfb x11vnc \
        fonts-liberation fonts-noto-color-emoji fonts-unifont \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 \
        libatspi2.0-0 libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

# Pinned google-chrome-stable (real Chrome, not bundled Chromium).
ARG CHROME_VERSION=126.0.6478.126-1
RUN wget -q -O /tmp/chrome.deb \
        "https://dl.google.com/linux/chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_${CHROME_VERSION}_amd64.deb" \
    && (apt-get update && apt-get install -y --no-install-recommends /tmp/chrome.deb || \
        (dpkg -i /tmp/chrome.deb; apt-get install -y -f --no-install-recommends)) \
    && rm -f /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/*

# noVNC static client for GET /ui iframe (x11vnc stays on localhost).
ARG NOVNC_VERSION=1.5.0
RUN wget -qO- "https://github.com/novnc/noVNC/archive/refs/tags/v${NOVNC_VERSION}.tar.gz" \
        | tar xz -C /opt \
    && mv /opt/noVNC-${NOVNC_VERSION} /opt/noVNC

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY custom_crawler ./custom_crawler
COPY tools ./tools
COPY ui ./ui

# Profile + spool volumes. Chrome crashes on the default 64 MB /dev/shm,
# so run with --disable-dev-shm-usage and mount adequate /dev/shm.
RUN mkdir -p /data/profiles /data/spool
VOLUME ["/data/profiles", "/data/spool"]

ENV CRAWLER_PORT=8080 \
    CRAWLER_PROFILE_ROOT=/data/profiles \
    CRAWLER_SPOOL_DIR=/data/spool \
    CRAWLER_CHROME_CHANNEL=chrome \
    CRAWLER_XVFB_MODE=always \
    CRAWLER_VNC_ENABLED=true \
    CRAWLER_NOVNC_WEB_DIR=/opt/noVNC

EXPOSE 8080

CMD ["python", "-m", "custom_crawler.service"]
