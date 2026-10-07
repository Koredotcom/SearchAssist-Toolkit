"""URL filtering: allowed/blocked rules, subdomain scoping, built-in extension denylist.

Reproduces Findly's precedence exactly: if ``blockedOpt`` apply block rules (exclude); elif
``allowedOpt`` apply allow rules (include-only). ``crawlEverything`` bypasses the user rules but the
extension denylist and robots check still apply.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List
from urllib.parse import urldefrag, urlsplit, urlunsplit

# Crawler-hygiene extension denylist (was denyExtensions in Findly). Built-in, not user-configurable.
DENY_EXTENSIONS = {
    # archives
    "zip", "tar", "gz", "tgz", "rar", "7z", "bz2", "xz",
    # binaries / installers
    "exe", "dmg", "pkg", "deb", "rpm", "msi", "bin", "iso", "apk",
    # media
    "mp3", "mp4", "avi", "mov", "wmv", "flv", "mkv", "webm", "ogg", "wav", "m4a", "m4v",
    "jpg", "jpeg", "png", "gif", "bmp", "svg", "ico", "webp", "tiff", "psd",
    # office / docs (PDF deferred; not fetched but reported by content-type when linked without ext)
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "csv", "rtf",
    # fonts / styles / scripts
    "css", "js", "woff", "woff2", "ttf", "eot", "otf",
}


def normalize_url(url: str) -> str:
    """Lowercase host, strip fragment, normalize trailing slash (keep root '/')."""
    url, _ = urldefrag(url)
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
        if not path:
            path = "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def url_hash(url: str) -> str:
    return hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()


def _registrable_host(host: str) -> str:
    host = (host or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _extension(path: str) -> str:
    last = path.rsplit("/", 1)[-1]
    if "." in last:
        return last.rsplit(".", 1)[-1].lower()
    return ""


def _match_condition(url: str, condition: str, needle: str) -> bool:
    condition = (condition or "").strip()
    if condition == "contains":
        return needle in url
    if condition == "doesNotContains":
        return needle not in url
    if condition == "endsWith":
        return url.endswith(needle)
    if condition == "beginsWith":
        return url.startswith(needle)
    if condition in ("is", "equalsTo"):
        return url == needle
    if condition in ("isNot", "notEqualsTo"):
        return url != needle
    return False


def _rules_match(url: str, rules: List[Dict[str, Any]]) -> bool:
    """True if any rule (condition applied to any of its urls) matches."""
    for rule in rules or []:
        condition = rule.get("condition")
        needles = rule.get("url") or []
        if isinstance(needles, str):
            needles = [needles]
        for needle in needles:
            if needle and _match_condition(url, condition, needle):
                return True
    return False


class URLFilter:
    def __init__(self, base_url: str, cfg: Any) -> None:
        self.cfg = cfg
        base = urlsplit(base_url)
        self.base_scheme = base.scheme.lower()
        self.base_host = base.netloc.lower()
        self.base_registrable = _registrable_host(base.netloc)

    def in_scope(self, url: str) -> bool:
        host = urlsplit(url).netloc.lower()
        if not host:
            return False
        if host == self.base_host:
            return True
        reg = _registrable_host(host)
        if self.cfg.allowSubdomains:
            return reg == self.base_registrable or reg.endswith("." + self.base_registrable)
        # Same site with or without www (seed www.guns.com ↔ guns.com in sitemaps).
        return reg == self.base_registrable and host in (
            self.base_registrable,
            "www." + self.base_registrable,
            self.base_host,
        )

    def extension_allowed(self, url: str) -> bool:
        ext = _extension(urlsplit(url).path)
        return ext not in DENY_EXTENSIONS

    def user_rules_allow(self, url: str) -> bool:
        """Findly precedence: blockedOpt wins; elif allowedOpt include-only; else allow."""
        if self.cfg.crawlEverything:
            return True
        if self.cfg.blockedOpt:
            return not _rules_match(url, self.cfg.blockedURLs)
        if self.cfg.allowedOpt:
            return _rules_match(url, self.cfg.allowedURLs)
        return True

    def allowed(self, url: str, *, scope: bool = True, user_rules: bool = True) -> bool:
        """Full gate excluding robots (robots checked separately by the caller).

        ``scope``/``user_rules`` are relaxed for operator-supplied URL lists
        (CSV upload, uploaded sitemaps, retry), which Findly also crawls without
        re-applying the domain filter.
        """
        if not url.lower().startswith(("http://", "https://")):
            return False
        if scope and not self.in_scope(url):
            return False
        if not self.extension_allowed(url):
            return False
        if user_rules and not self.user_rules_allow(url):
            return False
        return True
