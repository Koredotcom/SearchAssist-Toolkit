"""Seed expansion for non-domain source types (CSV uploads, retry lists).

Findly source types ride on the ``/crawl`` payload as ``sourceType``:

* ``url`` — domain crawl (sitemap-first, BFS fallback); handled by ``CrawlJob``
* ``uploadUrl`` — CSV of page URLs (first column header ``url``)
* ``uploadSitemap`` — CSV of sitemap URLs (first column header ``sitemap``)
* ``crawl_retry`` — failed URLs pulled from the Findly public API
* ``recrawl_page`` — the explicit page URL(s) sent as ``urls``

CSV rules mirror Findly ``UrlFetcher._extract_data_from_csv``: only the first
column is read, its header must match the source type, values are stripped and
de-duplicated. Rejections raise ``SeedExpansionError`` so the job fails with a
stable code instead of silently deep-crawling the domain.
"""
from __future__ import annotations

import csv
import io
from typing import List, Optional, Sequence

import httpx

SOURCE_TYPE_URL = "url"
SOURCE_TYPE_UPLOAD_URL = "uploadUrl"
SOURCE_TYPE_UPLOAD_SITEMAP = "uploadSitemap"
SOURCE_TYPE_CRAWL_RETRY = "crawl_retry"
SOURCE_TYPE_RECRAWL_PAGE = "recrawl_page"

CSV_COLUMN_BY_SOURCE_TYPE = {
    SOURCE_TYPE_UPLOAD_URL: "url",
    SOURCE_TYPE_UPLOAD_SITEMAP: "sitemap",
}

_KNOWN_SOURCE_TYPES = {
    SOURCE_TYPE_URL,
    SOURCE_TYPE_UPLOAD_URL,
    SOURCE_TYPE_UPLOAD_SITEMAP,
    SOURCE_TYPE_CRAWL_RETRY,
    SOURCE_TYPE_RECRAWL_PAGE,
}


class SeedExpansionError(RuntimeError):
    """Seed list could not be built. ``code`` is reported as the job error."""

    def __init__(self, code: str, message: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code


def normalize_source_type(raw: Optional[str]) -> str:
    """Map a submitted ``sourceType`` onto a known mode (unknown → domain crawl)."""
    value = (raw or "").strip()
    if not value:
        return SOURCE_TYPE_URL
    for known in _KNOWN_SOURCE_TYPES:
        if value.lower() == known.lower():
            return known
    return SOURCE_TYPE_URL


def coerce_urls(urls: Optional[Sequence[str]] = None) -> List[str]:
    """Strip and de-duplicate an explicit ``urls`` list, order preserved."""
    out: List[str] = []
    seen = set()
    for raw in urls or []:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def parse_csv_column(text: str, expected_column: str) -> List[str]:
    """Return de-duplicated first-column values, order preserved."""
    rows = [
        row
        for row in csv.reader(io.StringIO(text))
        if row and any((cell or "").strip() for cell in row)
    ]
    if not rows:
        raise SeedExpansionError(
            "upload_file_empty", "The uploaded file has no rows."
        )

    header = (rows[0][0] or "").strip().lstrip("\ufeff").lower()
    if header != expected_column.lower():
        raise SeedExpansionError(
            "upload_file_invalid_column",
            f"The uploaded CSV has incorrect column names. Expected '{expected_column}', got '{header}'.",
        )

    out: List[str] = []
    seen = set()
    for row in rows[1:]:
        value = (row[0] or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    if not out:
        raise SeedExpansionError(
            "upload_file_empty", "The uploaded file contained no usable values."
        )
    return out


async def fetch_csv_text(file_url: str, *, timeout: float = 30.0) -> str:
    """Download the uploaded CSV over HTTP. Signed KoreServer file URLs work as-is."""
    if not (file_url or "").strip():
        raise SeedExpansionError(
            "upload_file_url_missing", "fileUrl is required for upload source types."
        )
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(file_url)
    except Exception as exc:
        raise SeedExpansionError(
            "upload_file_download_failed",
            f"The uploaded file could not be downloaded: {type(exc).__name__}: {exc}",
        ) from exc
    if resp.status_code >= 300:
        raise SeedExpansionError(
            "upload_file_download_failed",
            f"The uploaded file could not be downloaded (HTTP {resp.status_code}).",
        )
    return resp.text


async def load_csv_values(
    file_url: str, *, source_type: str, timeout: float = 30.0
) -> List[str]:
    column = CSV_COLUMN_BY_SOURCE_TYPE.get(source_type)
    if not column:
        raise SeedExpansionError(
            "upload_source_type_unsupported",
            f"sourceType '{source_type}' does not read a CSV file.",
        )
    text = await fetch_csv_text(file_url, timeout=timeout)
    return parse_csv_column(text, column)
