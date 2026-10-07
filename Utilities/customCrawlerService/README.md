# Custom Crawler Service

The Custom Crawler Service uses Playwright and Google Chrome to crawl JavaScript-heavy and
Cloudflare-protected websites for Search Assist. It can be run locally, on a Linux server, or in
Docker.

This README covers installation, configuration, testing, and the service API. Platform routing and
Search Assist implementation details are intentionally kept in the technical design document.

## Requirements

- Linux with Python **3.11 or newer**. Python 3.13 is used by the current server deployment.
  Python 3.6 is not supported.
- Google Chrome available as `google-chrome` or `google-chrome-stable`.
- A writable profile directory and spool directory.
- Xvfb on headless servers. Install x11vnc, websockify, and noVNC if the interactive warmup UI is
  needed.
- Network access from Findly to this service and from this service to the configured callback host.

The commands below assume this directory:

```text
SearchAssist-Toolkit/Utilities/customCrawlerService
```

## Installation

Create the venv with Python 3.11+; do not use an older system `python3`:

```bash
cd SearchAssist-Toolkit/Utilities/customCrawlerService
python3.13 --version
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If Python 3.13 is installed at a custom path, use that executable instead, for example:

```bash
/data/py3.13.7/bin/python3.13 -m venv .venv
```

Confirm Chrome before starting the service:

```bash
google-chrome --version || google-chrome-stable --version
```

On Debian/Ubuntu, install Playwright system dependencies once:

```bash
python -m playwright install-deps
```

For RHEL, CentOS, or Amazon Linux, use the [server installation](#rhel-centos-or-amazon-linux-server)
instructions below.

## Configuration

Create the environment file and writable data directories:

```bash
cp -n .env.example .env
mkdir -p data/profiles data/spool
```

For a headless server, use:

```env
CRAWLER_PORT=8080
CRAWLER_XVFB_MODE=always
CRAWLER_PROFILE_ROOT=/data/profiles
CRAWLER_SPOOL_DIR=/data/spool
CRAWLER_CALLBACK_PUBLIC_HOST=https://<koreserver-public-host>
CRAWLER_NOVNC_WEB_DIR=/opt/noVNC
```

`CRAWLER_CALLBACK_PUBLIC_HOST` must contain only the host, without `/api` or a callback path. The
service creates the callback URLs automatically. Set `CRAWLER_CALLBACK_AUTH_HEADER` only when the
configured KoreServer callback endpoint requires an authentication header. Never commit real
credentials to `.env`.

## Start the service

```bash
source .venv/bin/activate
python -m custom_crawler.service
```

Verify it from another terminal:

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS -X POST http://127.0.0.1:8080/validate-url \
  -H 'Content-Type: application/json' \
  --data '{"url":"https://example.com"}'
```

The browser console is available at `http://127.0.0.1:8080/ui`. On a remote server, access it
through an SSH tunnel; do not expose VNC ports publicly.

## Crawl model

The service starts a Chrome session, discovers URLs from sitemaps or the configured seed URL, and
fetches pages one at a time. It supports domain crawls, uploaded URL/sitemap lists, retry-failure
crawls, and single-page recrawls.

Cloudflare-challenged URLs are recorded as failed and the crawler continues with the remaining
URLs. A crawl can still finish as failed when all URLs fail, the job is cancelled, the time budget
is exceeded, or a required warmed profile is unavailable.

The default browser is ephemeral. For hosts that require a previously cleared Cloudflare session,
warm and save a profile first, then enable `useProfile` for the crawl.

## Cloudflare / Turnstile hosts

Some hosts serve an interactive challenge on product pages (and sometimes elsewhere). A cold
ephemeral browser may clear the homepage but fail deep URLs. For those hosts:

1. Warm a profile once (human click if needed):
   ```bash
   # Browser UI on the crawler host (SSH tunnel / VPN)
   # open http://127.0.0.1:8080/ui — enter URL, then select Warm Profile

   # Server CLI (no desktop): Xvfb + x11vnc
   python -m tools.warmup_profile --url https://example.com --xvfb always --vnc

   # Desktop
   python -m tools.warmup_profile --url https://example.com --xvfb never --no-vnc \
     --verify-url 'https://example.com/some-deep-page'
   ```
2. Submit crawls with `"useProfile": true` (or set `CRAWLER_USE_PROFILE=true`).

The tool saves only when the page is no longer challenged. It writes `storage_state.json` and
`session_meta.json` under `CRAWLER_PROFILE_ROOT/<host>/`. Cookies expire — re-warm when jobs
start failing with `challenge_not_cleared` / `cloudflareBlocked`.

Diagnose a URL:

```bash
python -m tools.cf_probe --url https://example.com/path --xvfb never
python -m tools.cf_probe --url https://example.com/path --xvfb never --use-profile
```

## RHEL, CentOS, or Amazon Linux server

RHEL, CentOS, or Amazon Linux. Install VNC stack once:

```bash
cd SearchAssist-Toolkit/Utilities/customCrawlerService
source .venv/bin/activate
sudo -E bash tools/install_vnc_deps_yum.sh
```

That installs `xorg-x11-server-Xvfb`, `x11vnc` (EPEL), `websockify` (pip), and noVNC at `/opt/noVNC`.

```bash
export CRAWLER_XVFB_MODE=always
export CRAWLER_VNC_ENABLED=true
export CRAWLER_NOVNC_WEB_DIR=/opt/noVNC
export CRAWLER_PROFILE_ROOT=/data/profiles   # durable disk; use /data/etc if that is your volume
mkdir -p "$CRAWLER_PROFILE_ROOT" /data/spool
python -m custom_crawler.service
```


Open `http://127.0.0.1:8080/ui` after starting the service.

- Keep `CRAWLER_XVFB_MODE=always` on headless servers.
- Do not expose `59xx` VNC ports to the public internet.
- Confirm `playwright==1.60.0`, capture each Cloudflare host in `/ui`, then crawl with `useProfile: true`.

## Submit contract (`POST /crawl`)

```json
{
  "jobId": "<crawlId>",
  "streamId": "<streamId>",
  "baseUrl": "https://example.com",
  "sourceType": "url",
  "fileUrl": "",
  "fileId": "",
  "extractionSourceId": "",
  "callbackBatchSize": 10,
  "callbackMaxBytes": 1048576,
  "advanceSettings": {
    "useProfile": true,
    "crawlBeyondSitemaps": false,
    "allowSubdomains": false,
    "maxUrlLimit": 1500,
    "crawlDepth": 5,
    "respectRobotTxtDirectives": true,
    "isJavaScriptRendered": true,
    "crawlDelay": 1.0,
    "useCookies": true,
    "crawlEverything": false,
    "allowedOpt": false,
    "allowedURLs": [],
    "blockedOpt": false,
    "blockedURLs": []
  },
  "reqHeaders": [],
  "auth": null
}
```

| `sourceType` | Behavior |
|---|---|
| `url` (default) | Domain crawl: sitemap-first, BFS fallback when no usable sitemap URLs |
| `uploadUrl` | HTTP GET `fileUrl` → CSV column `url` → crawl those pages only (`discoveryMode=seed_list`) |
| `uploadSitemap` | HTTP GET `fileUrl` → CSV column `sitemap` → expand sitemaps → crawl pages (`discoveryMode=sitemap`) |
| `crawl_retry` | Crawl URLs that previously failed |
| `recrawl_page` | Crawl the explicit `urls` only (UI single-page recrawl; no sitemap / BFS) |

| Setting | Effect |
|---|---|
| `crawlBeyondSitemaps: true` | Deep crawl straight from `baseUrl`; sitemaps are not fetched |
| `crawlBeyondSitemaps: false` | Sitemap discovery, with BFS fallback when no usable sitemap URLs remain |
| `useProfile: true` | Use a warmed profile for this host. The profile must be captured before the crawl. |

### Retry failures (`sourceType=crawl_retry`)

Use the Search Assist retry action to crawl previously failed URLs. The service receives the
failed URL list and processes it as a new crawl. No sitemap discovery is performed for this mode.

### Single-page recrawl (`sourceType=recrawl_page`)

Use the page-level retry action to crawl one URL. The service receives the URL in `urls` and does
not expand the site or fetch sitemaps.

### Callback delivery

After pages are fetched, the service sends them in batches and sends a completion notification.
Failed deliveries are retried and then written to `CRAWLER_SPOOL_DIR` for later inspection or
replay. Check the service logs for the callback URL and HTTP status when delivery fails.

## Web console

`GET /ui` provides the standalone client console. It can:

- validate a target and report success or failure inline (HTTP status, sitemap count,
  Cloudflare challenge) alongside saved-profile readiness;
- open the interactive **Warm Profile** browser for Cloudflare verification;
- save the profile only, or save it and immediately start a crawl;
- configure max URLs, max depth, delay, JavaScript rendering, robots.txt,
  and subdomains (the console always sends `crawlBeyondSitemaps: false`, so crawls
  are sitemap-first with automatic BFS fallback and there is no toggle for it);
- optionally configure page-batch and completion callback URLs plus an
  `Authorization` header;
- show live discovery mode, counters, final status, errors, and cancel a crawl.

The page works both directly at `/ui` and behind a path-prefixed reverse proxy
such as `/custom-crawler/ui`; the noVNC iframe and WebSocket inherit that prefix.

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `CRAWLER_PORT` | `8080` | HTTP listen port |
| `CRAWLER_PROFILE_ROOT` | `/data/profiles` | Per-host Chrome profiles |
| `CRAWLER_SPOOL_DIR` | `/data/spool` | Undelivered callback buffer |
| `CRAWLER_CHROME_CHANNEL` | `chrome` | Real Google Chrome |
| `CRAWLER_XVFB_MODE` | `auto` | `always` / `auto` / `never` |
| `CRAWLER_PAGE_TIMEOUT_MS` | `60000` | Per-page `goto` timeout |
| `CRAWLER_CHALLENGE_WAIT_SECONDS` | `90` | CF interstitial wait |
| `CRAWLER_HUMAN_CF_WAIT_SECONDS` | `90` | Additional wait during interactive profile warmup |
| `CRAWLER_JOB_BUDGET_SECONDS` | `7200` | Whole-job ceiling |
| `CRAWLER_CONTEXT_RECYCLE_EVERY` | `50` | Pages before recycling the browser context |
| `CRAWLER_RSS_LIMIT_MB` | _(empty)_ | Optional memory threshold for early context recycling |
| `CRAWLER_USE_PROFILE` | `false` | Default for jobs without `useProfile` |
| `CRAWLER_CALLBACK_RETRY_MAX` | `5` | Delivery attempts before spooling |
| `CRAWLER_CALLBACK_PUBLIC_HOST` | _(empty)_ | KoreServer public API base for callbacks + retry status API |
| `CRAWLER_CALLBACK_AUTH_HEADER` | _(empty)_ | Optional token for the callback endpoint when required |
| `CRAWLER_CONTENT_STATUS_HOST` | _(falls back to callback host)_ | Override host for get-content-by-status |
| `CRAWLER_CONTENT_STATUS_AUTH_HEADER` | _(falls back to callback auth)_ | Override JWT for get-content-by-status |
| `CRAWLER_CONTENT_STATUS_LIMIT` | `200` | Page size when listing failed URLs |
| `CRAWLER_VNC_ENABLED` | `true` | Capture APIs / `/ui` VNC |
| `CRAWLER_VNC_HOST` | `localhost` | Address used by the VNC proxy |
| `CRAWLER_NOVNC_WEB_DIR` | `/opt/noVNC` | noVNC static files |

`.env` in this directory overrides shell exports. See `.env.example`.

## Local command reference

```bash
cd SearchAssist-Toolkit/Utilities/customCrawlerService
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install-deps   # Debian/Ubuntu only; first time

mkdir -p data/profiles data/spool
cp -n .env.example .env   # edit paths / CRAWLER_XVFB_MODE as needed

python -m custom_crawler.service
# then http://127.0.0.1:8080/ui
```

```bash
# Mock Findly callbacks (optional)
python -m tools.mock_findly_callbacks

# Warm a CF host (desktop)
python -m tools.warmup_profile --url https://example.com --xvfb never --no-vnc
```

## Testing

Run the unit tests after installing the requirements:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

For a local crawl test without a Findly environment, start the mock callback server in one
terminal:

```bash
python -m tools.mock_findly_callbacks
```

Then run a small crawl in another terminal:

```bash
python -m tools.dry_run_job \
  --url https://example.com \
  --limit 3 \
  --depth 1 \
  --xvfb always
```

The test is successful when the dry run reports fetched pages and the mock server prints callback
and completion messages. Captured request bodies are written to `tools/callback_inbox/`.

Before connecting a deployed service to Search Assist, verify:

```bash
curl -fsS http://<crawler-host>:8080/health
```

The crawler host must be reachable from Findly, and the callback host must be reachable from the
crawler host.

## Troubleshooting

| Symptom | Check |
|---|---|
| `python: command not found` after activation | Recreate the venv with Python 3.11+ and confirm `python --version`. |
| `SyntaxError: future feature annotations is not defined` | The service is running under Python 3.6. Activate the correct venv and start it with `python -m custom_crawler.service`. |
| Chrome executable/channel error | Install Google Chrome and confirm `google-chrome --version`; the default channel is `chrome`. |
| `/health` works locally but Findly cannot connect | Check firewall/security-group rules and confirm the source endpoint URL points to the crawler service. |
| Callbacks fail or pages are written to the spool | Confirm `CRAWLER_CALLBACK_PUBLIC_HOST`, network access to KoreServer, and any required callback authentication header. |
| Callback returns `500` and no downstream request is logged | Check the KoreServer application log and its custom-crawler callback configuration. |
| `/crawl` returns `409 profile_not_warmed` | Capture and save a profile for the target host first, or submit with `useProfile: false`. |
| Several pages show Cloudflare challenges | The pages remain failed, but the crawler continues with the remaining URLs. Re-warm the host profile if challenges persist. |

## API summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Check service availability |
| `GET` | `/ui` | Open the profile warmup and crawl console |
| `POST` | `/crawl` | Start a crawl |
| `GET` | `/crawl/{jobId}` | Get crawl status and counters |
| `POST` | `/crawl/cancel` | Cancel a running crawl |
| `POST` | `/validate-url` | Check whether a URL can be opened |
| `POST` | `/profile/capture/start` | Start interactive profile capture |
| `POST` | `/profile/capture/complete` | Save a cleared profile |
| `POST` | `/profile/capture/cancel` | Cancel profile capture |
| `GET` | `/profile/{host}` | Check profile status |

## Docker

```bash
docker build -t custom-crawler-service .
docker run --rm -p 8080:8080 --shm-size=1g \
  -v $(pwd)/data/profiles:/data/profiles \
  -v $(pwd)/data/spool:/data/spool \
  custom-crawler-service
```

Do **not** share one profile directory across concurrent Chrome processes.
