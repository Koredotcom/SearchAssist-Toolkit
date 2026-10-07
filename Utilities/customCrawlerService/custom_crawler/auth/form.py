"""Site form auth — DEFERRED past v1.

Placeholder for the later auth phase. When enabled it will reproduce the flow in
``crawl_ai/auth/CrawlAIFormAuthentication.py`` (navigate to auth_check_url, optional multi-step
flow, fill form_fields, generalized submit probe, validation via test_type/test_value).
"""
from __future__ import annotations

from typing import Any, Dict


async def run_form_login(page: Any, auth: Dict[str, Any]) -> bool:  # pragma: no cover - deferred
    raise NotImplementedError("Form auth is deferred past v1")
