"""Crawl job lifecycle: sitemap discovery, optional BFS link expansion, page fetch.

Service-owned layers: HTTP job lifecycle, URL filters, robots, counters, and batched
Findly callback delivery. Browser work lives in ``custom_crawler.browser``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .browser.fetch import PageResult, fetch_page, is_html
from .browser.session import BrowserSession, profile_key_for_url
from .browser.sitemap import discover_urls_via_sitemaps, is_html_page_url
from .delivery.callback import CallbackDelivery
from .delivery.urls import headers_to_dict, merge_callback_headers, resolve_delivery_urls
from .discovery.content_status import ContentStatusError, fetch_urls_by_status
from .discovery.filters import URLFilter, url_hash
from .discovery.robots import RobotsCache
from .discovery.seeds import (
    SOURCE_TYPE_CRAWL_RETRY,
    SOURCE_TYPE_RECRAWL_PAGE,
    SOURCE_TYPE_UPLOAD_SITEMAP,
    SOURCE_TYPE_UPLOAD_URL,
    SeedExpansionError,
    coerce_urls,
    load_csv_values,
    normalize_source_type,
)
from .obs.logging import job_id_var, log, setup_logger
from .obs.metrics import Counters
from .settings import EngineConfig, ServiceConfig

logger = setup_logger("custom_crawler.job")

def url_path_depth(url: str) -> int:
    """Findly UrlFilter._get_url_depth: number of path segments.

    'https://example.com/' -> 0, '/a' -> 1, '/a/b' -> 2. Returns -1 on parse error
    (which Findly treats as passing the depth filter).
    """
    try:
        from urllib.parse import urlparse

        segments = [s for s in urlparse(url).path.split("/") if s]
        return len(segments)
    except Exception:
        return -1


class CrawlJob:
    def __init__(
        self,
        *,
        submit: Dict[str, Any],
        service_cfg: ServiceConfig,
        playwright: Any,
    ) -> None:
        self.job_id: str = submit["jobId"]
        self.external_job_id: str = f"ext-{uuid.uuid4().hex[:16]}"
        self.base_url: str = submit["baseUrl"]
        self.source_type: str = normalize_source_type(submit.get("sourceType"))
        self.stream_id: str = str(submit.get("streamId") or "").strip()
        self.source_id: str = str(
            submit.get("extractionSourceId") or submit.get("sourceId") or ""
        ).strip()
        self.file_url: str = str(submit.get("fileUrl") or "").strip()
        self.file_id: str = str(submit.get("fileId") or "").strip()
        self.submitted_urls: List[str] = coerce_urls(submit.get("urls"))
        self.service_cfg = service_cfg
        self.playwright = playwright
        self.engine = EngineConfig.from_advance_settings(submit.get("advanceSettings"))
        self.max_url_limit = self.engine.maxUrlLimit
        self.profile_key = profile_key_for_url(self.base_url)

        self.counters = Counters()
        self.status = "pending"
        self.error: Optional[str] = None
        self._cancel = asyncio.Event()
        self.created_at = time.time()
        self.finished_at: Optional[float] = None

        self.robots = RobotsCache(respect=self.engine.respectRobotTxtDirectives)
        self.profile_warmed: Optional[bool] = None
        self.cloudflare_blocked = False
        self.url_filter = URLFilter(self.base_url, self.engine)

        callback_url, complete_url = resolve_delivery_urls(
            submit,
            callback_public_host=service_cfg.callback_public_host,
            callback_url_default=service_cfg.callback_url,
            complete_url_default=service_cfg.complete_url,
        )
        self.delivery_headers = merge_callback_headers(
            submit.get("reqHeaders"),
            callback_auth_header=service_cfg.callback_auth_header,
        )
        self.delivery = CallbackDelivery(
            job_id=self.job_id,
            callback_url=callback_url,
            complete_url=complete_url,
            req_headers=self.delivery_headers,
            batch_size=int(submit.get("callbackBatchSize", 10)),
            max_bytes=int(submit.get("callbackMaxBytes", 1024 * 1024)),
            spool_dir=service_cfg.spool_dir,
            retry_max=service_cfg.callback_retry_max,
            counters=self.counters,
            logger=logger,
        )

        # Crawl queue: (url, depth). Grows while BFS expands page links.
        self._urls: List[Tuple[str, int]] = []
        self._seen: Set[str] = set()
        self.discovery_mode = "pending"
        self.discovery_fallback_reason: Optional[str] = None
        self._bfs_active = False

    # ---- lifecycle -------------------------------------------------------
    def cancel(self) -> None:
        self._cancel.set()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def status_doc(self) -> Dict[str, Any]:
        use_profile = (
            self.engine.useProfile
            if self.engine.useProfile is not None
            else self.service_cfg.use_profile
        )
        return {
            "jobId": self.job_id,
            "externalJobId": self.external_job_id,
            "status": self.status,
            "error": self.error,
            "sourceType": self.source_type,
            "profileKey": self.profile_key,
            "profileWarmed": self.profile_warmed,
            "cloudflareBlocked": self.cloudflare_blocked,
            "profileExpired": bool(self.cloudflare_blocked and use_profile),
            "discoveryMode": self.discovery_mode,
            "discoveryFallbackReason": self.discovery_fallback_reason,
            "counters": self.counters.snapshot(),
            "createdAt": self.created_at,
            "finishedAt": self.finished_at,
        }

    @property
    def cf_wait(self) -> float:
        return float(self.service_cfg.challenge_wait_seconds)

    # ---- URL list --------------------------------------------------------
    def _add_url(self, url: str, depth: int) -> bool:
        if len(self._urls) >= self.max_url_limit:
            return False
        h = url_hash(url)
        if h in self._seen:
            return False
        self._seen.add(h)
        self._urls.append((url, depth))
        return True

    async def _enqueue_if_allowed(
        self, url: str, depth: int, *, scope: bool = True, user_rules: bool = True
    ) -> bool:
        if not url or not is_html_page_url(url):
            return False
        if not self.url_filter.allowed(url, scope=scope, user_rules=user_rules):
            self.counters.inc("skipped")
            return False
        if not await self.robots.allowed(url):
            self.counters.inc("skipped")
            return False
        return self._add_url(url, depth)

    async def _seed_bfs(self, *, mode: str, reason: Optional[str]) -> None:
        """Seed the queue from ``baseUrl`` and enable link expansion."""
        seed = self.base_url.rstrip("/") + "/"
        await self._enqueue_if_allowed(seed, 0)
        if not self._urls:
            await self._enqueue_if_allowed(self.base_url, 0)
        self.discovery_mode = mode
        self.discovery_fallback_reason = reason
        self._bfs_active = True

    async def _enqueue_seed_list(self, urls: List[str]) -> int:
        """Enqueue an operator-supplied URL list verbatim (no sitemaps, no BFS)."""
        added = 0
        for url in urls:
            if len(self._urls) >= self.max_url_limit:
                break
            if await self._enqueue_if_allowed(url, 0, scope=False, user_rules=False):
                added += 1
        self.discovery_mode = "seed_list"
        self.discovery_fallback_reason = None
        self._bfs_active = False
        self.counters.set("discovered", len(self._urls))
        return added

    async def _collect_uploaded_page_urls(self) -> None:
        """``uploadUrl``: crawl exactly the CSV pages — Findly applies no domain filter."""
        urls = await load_csv_values(self.file_url, source_type=SOURCE_TYPE_UPLOAD_URL)
        added = await self._enqueue_seed_list(urls)
        log(
            logger,
            logging.INFO,
            "uploaded URL list expanded",
            fileId=self.file_id,
            csvUrls=len(urls),
            queued=added,
            maxUrlLimit=self.max_url_limit,
        )
        if not added:
            raise SeedExpansionError(
                "upload_urls_rejected",
                "None of the uploaded URLs passed the crawl filters.",
            )

    async def _collect_uploaded_sitemap_urls(self, page: Any) -> None:
        """``uploadSitemap``: expand only the uploaded sitemaps (no robots/common probing)."""
        sitemaps = await load_csv_values(
            self.file_url, source_type=SOURCE_TYPE_UPLOAD_SITEMAP
        )
        visited: List[str] = []
        page_urls: List[str] = []
        seen_pages: Set[str] = set()
        for sitemap_url in sitemaps:
            if len(page_urls) >= self.max_url_limit:
                break
            found, pages = await discover_urls_via_sitemaps(
                page,
                sitemap_url,
                max_url_limit=self.max_url_limit - len(page_urls),
                cf_wait=self.cf_wait,
            )
            if not found:
                # Sentinel: the sitemap could not be read, so ``pages`` is just the seed.
                log(
                    logger,
                    logging.WARNING,
                    "uploaded sitemap could not be read",
                    sitemap=sitemap_url,
                )
                continue
            visited.extend(found)
            for url in pages:
                if url in seen_pages:
                    continue
                seen_pages.add(url)
                page_urls.append(url)

        max_depth = self.engine.crawlDepth
        if max_depth >= 0:
            before = len(page_urls)
            page_urls = [u for u in page_urls if url_path_depth(u) <= max_depth]
            if len(page_urls) != before:
                log(
                    logger,
                    logging.INFO,
                    "applied crawlDepth path filter to uploaded sitemap URLs",
                    maxDepth=max_depth,
                    before=before,
                    after=len(page_urls),
                )

        added = 0
        for url in page_urls:
            if len(self._urls) >= self.max_url_limit:
                break
            if await self._enqueue_if_allowed(url, 0, scope=False):
                added += 1
        self.discovery_mode = "sitemap"
        self.discovery_fallback_reason = None
        self._bfs_active = False
        self.counters.set("discovered", len(self._urls))
        log(
            logger,
            logging.INFO,
            "uploaded sitemaps expanded",
            fileId=self.file_id,
            sitemapsUploaded=len(sitemaps),
            sitemapsVisited=len(visited),
            queued=added,
        )
        if not added:
            raise SeedExpansionError(
                "uploaded_sitemaps_empty",
                "The uploaded sitemaps produced no crawlable page URLs.",
            )

    async def _collect_retry_urls(self) -> None:
        """``crawl_retry``: read the source's failed URLs from the Findly public API."""
        cfg = self.service_cfg
        try:
            urls = await fetch_urls_by_status(
                host=cfg.content_status_host or cfg.callback_public_host,
                stream_id=self.stream_id,
                source_id=self.source_id,
                headers=headers_to_dict(self.delivery_headers)
                if not cfg.content_status_auth_header
                else {
                    **headers_to_dict(self.delivery_headers),
                    "auth": cfg.content_status_auth_header,
                },
                status="failed",
                page_limit=cfg.content_status_page_limit,
                max_urls=self.max_url_limit,
                path_template=cfg.content_status_path,
                logger=logger,
            )
        except ContentStatusError as exc:
            raise SeedExpansionError(exc.code, str(exc)) from exc

        added = await self._enqueue_seed_list(urls)
        log(
            logger,
            logging.INFO,
            "retry URL list expanded",
            sourceId=self.source_id,
            failedUrls=len(urls),
            queued=added,
            maxUrlLimit=self.max_url_limit,
        )
        if not added:
            raise SeedExpansionError(
                "no_failed_urls_to_retry",
                "get-content-by-status returned no crawlable failed URLs for this source.",
            )

    async def _collect_recrawl_page_urls(self) -> None:
        """``recrawl_page``: crawl the explicit page URL(s) from the submit payload."""
        urls = self.submitted_urls
        if not urls:
            raise SeedExpansionError(
                "recrawl_page_url_missing",
                "urls is required for recrawl_page.",
            )
        added = await self._enqueue_seed_list(urls)
        log(
            logger,
            logging.INFO,
            "single-page recrawl seeds expanded",
            urls=len(urls),
            queued=added,
        )
        if not added:
            raise SeedExpansionError(
                "recrawl_page_urls_rejected",
                "None of the recrawl page URLs passed the crawl filters.",
            )

    async def _collect_start_urls(self, page: Any, *, seed_home: bool) -> None:
        """Build the initial crawl queue, matching Findly's discovery semantics.

        * ``crawlBeyondSitemaps=true`` skips sitemap discovery entirely and deep-crawls
          from ``baseUrl`` (Findly ``_get_initial_urls`` sets ``fallback_to_deep_crawl``
          without calling ``fetch_urls``). ``crawlDepth`` is the **link-hop depth**.
        * ``crawlBeyondSitemaps=false`` discovers via sitemaps, where ``crawlDepth``
          caps the URL **path-segment depth** (Findly ``_filter_sitemap_urls``). If no
          usable sitemap URLs remain, it falls back to a deep crawl from ``baseUrl``,
          as Findly does for domain sources whose sitemaps are missing or unusable.

        Non-domain source types (CSV uploads, retry) bring their own URL list and
        never fall back to a domain crawl.
        """
        if self.source_type == SOURCE_TYPE_UPLOAD_URL:
            await self._collect_uploaded_page_urls()
            return
        if self.source_type == SOURCE_TYPE_UPLOAD_SITEMAP:
            await self._collect_uploaded_sitemap_urls(page)
            return
        if self.source_type == SOURCE_TYPE_CRAWL_RETRY:
            await self._collect_retry_urls()
            return
        if self.source_type == SOURCE_TYPE_RECRAWL_PAGE:
            await self._collect_recrawl_page_urls()
            return

        if self.engine.crawlBeyondSitemaps:
            await self._seed_bfs(mode="bfs", reason=None)
            log(
                logger,
                logging.INFO,
                "crawlBeyondSitemaps enabled; skipping sitemaps and deep crawling from seed",
                urls=len(self._urls),
                crawlDepth=self.engine.crawlDepth,
                maxUrlLimit=self.max_url_limit,
            )
            self.counters.set("discovered", len(self._urls))
            return

        visited, page_urls = await discover_urls_via_sitemaps(
            page,
            self.base_url,
            max_url_limit=self.max_url_limit,
            cf_wait=self.cf_wait,
        )
        sitemap_found = bool(visited)
        # ``discover_urls_via_sitemaps`` returns the seed when no sitemap exists.
        # Do not mistake that sentinel for a successfully discovered sitemap URL.
        if not sitemap_found:
            page_urls = []
        log(
            logger,
            logging.INFO,
            "sitemap discovery finished",
            urls=len(page_urls),
            sitemaps=len(visited),
        )

        # Findly semantics: in sitemap mode crawlDepth caps URL *path* depth
        # (segment count), not link hops. -1 (parse error) passes, as in Findly.
        max_depth = self.engine.crawlDepth
        before = len(page_urls)
        if max_depth >= 0:
            page_urls = [u for u in page_urls if url_path_depth(u) <= max_depth]
            if len(page_urls) != before:
                log(
                    logger,
                    logging.INFO,
                    "applied crawlDepth path filter to sitemap URLs",
                    maxDepth=max_depth,
                    before=before,
                    after=len(page_urls),
                )

        # Preserve the homepage-first behavior for ephemeral sitemap sessions, but
        # decide fallback based only on accepted sitemap URLs.
        sitemap_urls_added = 0
        for url in page_urls:
            if len(self._urls) >= self.max_url_limit:
                break
            if await self._enqueue_if_allowed(url, 0):
                sitemap_urls_added += 1
        if sitemap_urls_added and seed_home and len(self._urls) < self.max_url_limit:
            home_added = await self._enqueue_if_allowed(self.base_url.rstrip("/") + "/", 0)
            if home_added:
                self._urls.insert(0, self._urls.pop())

        if sitemap_urls_added:
            self.discovery_mode = "sitemap"
            self._bfs_active = False
            log(
                logger,
                logging.INFO,
                "using sitemap discovery results",
                urls=sitemap_urls_added,
                sitemaps=len(visited),
            )
        else:
            if not sitemap_found:
                reason = "sitemap_not_found"
            elif not page_urls:
                reason = "sitemap_empty_or_filtered"
            else:
                reason = "sitemap_urls_rejected"

            await self._seed_bfs(mode="bfs_fallback", reason=reason)
            log(
                logger,
                logging.WARNING,
                "no usable sitemap URLs; activated BFS fallback",
                reason=reason,
                urls=len(self._urls),
                crawlDepth=self.engine.crawlDepth,
                maxUrlLimit=self.max_url_limit,
            )

        self.counters.set("discovered", len(self._urls))
        log(
            logger,
            logging.INFO,
            "start urls collected",
            urls=len(self._urls),
            sitemaps=len(visited),
            mode=self.discovery_mode,
            fallbackReason=self.discovery_fallback_reason,
            profileKey=self.profile_key,
        )

    async def _expand_links(self, links: List[str], depth: int) -> int:
        """Enqueue same-site HTML links one level deeper during BFS fallback."""
        if not self._bfs_active:
            return 0
        next_depth = depth + 1
        if next_depth > self.engine.crawlDepth:
            return 0
        added = 0
        for link in links:
            if len(self._urls) >= self.max_url_limit:
                break
            if await self._enqueue_if_allowed(link, next_depth):
                added += 1
        if added:
            self.counters.set("discovered", len(self._urls))
            log(
                logger,
                logging.INFO,
                "BFS expanded page links",
                added=added,
                nextDepth=next_depth,
                queueSize=len(self._urls),
                maxUrlLimit=self.max_url_limit,
            )
        elif links and next_depth <= self.engine.crawlDepth:
            log(
                logger,
                logging.INFO,
                "BFS found links but queue is full or filtered",
                linksFound=len(links),
                queueSize=len(self._urls),
                maxUrlLimit=self.max_url_limit,
            )
        return added

    # ---- per-URL fetch ----------------------------------------------------
    async def _crawl_one(self, session: BrowserSession, url: str, depth: int) -> None:
        extract = self._bfs_active and depth < self.engine.crawlDepth
        log(
            logger,
            logging.INFO,
            "page crawl started",
            url=url,
            depth=depth,
            profileKey=session.profile_key,
            ephemeral=session.ephemeral,
            extractLinks=extract,
        )

        result: PageResult = await fetch_page(
            session.page,
            url,
            wait_after_load=max(1.0, self.engine.crawlDelay or 1.0),
            cf_wait=self.cf_wait,
            page_timeout_ms=self.service_cfg.page_timeout_ms,
            extract_links=extract,
        )

        self.counters.inc("fetched")
        if result.challenged:
            self.counters.inc("challenged")
            self.cloudflare_blocked = True

        if result.status == "success":
            if result.page_html is None and not is_html(result.content_type):
                self.counters.inc("non_html")
            else:
                self.counters.inc("success")
            if extract and result.links:
                await self._expand_links(result.links, depth)
        else:
            self.counters.inc("failed")

        log(
            logger,
            logging.INFO,
            "page crawl finished",
            url=url,
            finalUrl=result.redirected_url or url,
            status=result.status,
            statusCode=result.status_code,
            challenged=result.challenged,
            blocked=result.blocked,
            title=result.title,
            error=result.error,
            linksFound=len(result.links),
            profileKey=session.profile_key,
        )
        await self.delivery.add_page(result.to_page())

    # ---- run -------------------------------------------------------------
    async def run(self) -> None:
        job_id_var.set(self.job_id)
        self.status = "running"
        final_status = "success"
        session: Optional[BrowserSession] = None
        budget = self.service_cfg.job_budget_seconds
        seed_failed = False
        try:
            await self.delivery.replay_spool()

            use_profile = (
                self.engine.useProfile
                if self.engine.useProfile is not None
                else self.service_cfg.use_profile
            )
            session = BrowserSession(
                self.playwright,
                profile_root=self.service_cfg.profile_root,
                profile_key=self.profile_key,
                channel=self.service_cfg.chrome_channel,
                js_enabled=self.engine.isJavaScriptRendered,
                use_profile=use_profile,
            )
            self.profile_warmed = session.warmed() if use_profile else False
            if use_profile and not self.profile_warmed:
                self.error = "profile_not_warmed"
                final_status = "failed"
                log(
                    logger,
                    logging.ERROR,
                    "useProfile was true but profile is not warmed — refusing ephemeral crawl",
                    profileKey=self.profile_key,
                )
            else:
                await session.start()
                log(
                    logger,
                    logging.INFO,
                    "browser started for discovery+crawl",
                    profileKey=self.profile_key,
                    profileDir=str(session.profile_dir) if session.launched_with_profile else None,
                    profileRequested=use_profile,
                    profileWarmed=self.profile_warmed,
                    ephemeral=session.ephemeral,
                    cookiesInjected=session.cookie_count,
                    cfClearance=session.has_cf_clearance,
                    display=os.environ.get("DISPLAY"),
                    cfWaitSeconds=self.cf_wait,
                    crawlBeyondSitemaps=self.engine.crawlBeyondSitemaps,
                    crawlDepth=self.engine.crawlDepth,
                    sourceType=self.source_type,
                )
                try:
                    await self._collect_start_urls(session.page, seed_home=session.ephemeral)
                except SeedExpansionError as exc:
                    self.error = exc.code
                    seed_failed = True
                    log(
                        logger,
                        logging.ERROR,
                        "seed expansion failed",
                        sourceType=self.source_type,
                        code=exc.code,
                        detail=str(exc),
                        fileUrl=self.file_url,
                        sourceId=self.source_id,
                    )

                i = 0
                while i < len(self._urls):
                    if self.cancelled():
                        break
                    if time.time() - self.created_at > budget:
                        self.error = "job_budget_exceeded"
                        self._cancel.set()
                        break
                    url, depth = self._urls[i]
                    i += 1
                    log(
                        logger,
                        logging.INFO,
                        "starting queued URL",
                        position=i,
                        total=len(self._urls),
                        url=url,
                        depth=depth,
                        profileKey=self.profile_key,
                    )
                    if i > 1 and self.engine.crawlDelay > 0:
                        await asyncio.sleep(self.engine.crawlDelay)
                    try:
                        await self._crawl_one(session, url, depth)
                        if session.launched_with_profile and self.counters.success and (
                            self.counters.success == 1 or self.counters.success % 10 == 0
                        ):
                            await session.refresh_state()
                    except Exception as exc:
                        self.counters.inc("failed")
                        log(logger, logging.ERROR, "url processing error", url=url, err=str(exc))

            await self.delivery.flush(is_last=True)

            if self.cancelled():
                final_status = "timed_out" if self.error == "job_budget_exceeded" else "cancelled"
            elif seed_failed or self.error in ("cloudflare_blocked", "profile_not_warmed"):
                final_status = "failed"
            elif self.counters.fetched and not self.counters.success:
                final_status = "failed"
                self.error = self.error or "all_pages_failed"
        except Exception as exc:
            final_status = "failed"
            self.error = f"{type(exc).__name__}: {exc}"
            log(logger, logging.ERROR, "job crashed", err=str(exc))
            try:
                await self.delivery.flush(is_last=True)
            except Exception:
                pass
        finally:
            if session is not None:
                await session.close()
            self.status = final_status
            self.finished_at = time.time()
            stats = {
                "discovered": self.counters.discovered,
                "fetched": self.counters.fetched,
                "success": self.counters.success,
                "failed": self.counters.failed,
                "skipped": self.counters.skipped,
                "challenged": self.counters.challenged,
                "non_html": self.counters.non_html,
            }
            await self.delivery.send_complete(final_status, stats, self.error)
            log(logger, logging.INFO, "job complete", status=final_status, **stats)
