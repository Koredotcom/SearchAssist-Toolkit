"""Site basic auth — DEFERRED past v1.

Placeholder for the later auth phase. In v1 only unauthenticated sources use the custom crawler
path; authenticated sources keep the existing crawl4ai / Scrapy routing.

When enabled, credentials are taken from ``authDetails.formFields`` following
``utils._get_basic_auth_credentials`` rules (password field → password; textbox / username-like key
→ username; only ``isEnabled`` fields) and applied as Playwright context ``http_credentials``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

USERNAME_KEYS = {"username", "email", "user", "username or email"}


def extract_basic_credentials(form_fields: List[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    username = None
    password = None
    for field in form_fields or []:
        if not field.get("isEnabled"):
            continue
        ftype = (field.get("type") or "").lower()
        key = (field.get("key") or "").lower()
        value = field.get("value")
        if ftype == "password":
            password = value
        elif ftype == "textbox" or key in USERNAME_KEYS:
            username = value
    if username and password:
        return {"username": username, "password": password}
    return None
