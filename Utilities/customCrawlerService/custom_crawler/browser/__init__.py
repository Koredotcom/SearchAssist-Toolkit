"""Headed Chrome crawl engine: session, challenge wait, page fetch, sitemap, links.

Used by the FastAPI service for discovery and page fetching. Launch flags stay minimal
(``--disable-blink-features=AutomationControlled``, ``--disable-dev-shm-usage``). Cloudflare
sites that need an interactive challenge must warm a per-host profile first
(``GET /ui`` or ``tools.warmup_profile``), then crawl with ``useProfile: true``.
"""
