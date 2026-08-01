# Search AI — 360° Troubleshooting Guide (TSG)

**Version:** 1.0  
**Last updated:** 2026-08-01  
**Audience:** SRE, Platform Engineering, Search AI On-Call  
**Observability source:** Groundcover (kore.ai tenant) + SearchAssist Toolkit integration docs

---

## Table of Contents

1. [Purpose & Scope](#1-purpose--scope)
2. [Architecture Overview](#2-architecture-overview)
3. [Service Catalog](#3-service-catalog)
4. [Queue & Messaging Reference](#4-queue--messaging-reference)
5. [Data Stores & Dependencies](#5-data-stores--dependencies)
6. [Observability — Groundcover Playbook](#6-observability--groundcover-playbook)
7. [Incident Triage Decision Tree](#7-incident-triage-decision-tree)
8. [Module-by-Module TSG](#8-module-by-module-tsg)
9. [Scenario Playbooks](#9-scenario-playbooks)
10. [Client-Side / Integration TSG](#10-client-side--integration-tsg)
11. [Realtime Processing TSG](#11-realtime-processing-tsg)
12. [Performance & Slowness TSG](#12-performance--slowness-tsg)
13. [Escalation & Immediate Next Steps](#13-escalation--immediate-next-steps)
14. [Appendix: gcQL & PromQL Cookbook](#14-appendix-gcql--promql-cookbook)

---

## 1. Purpose & Scope

This guide provides **step-by-step troubleshooting** for the full Search AI data pipeline across Kore.ai / Groundcover environments:

| Pipeline stage | What it covers |
|----------------|----------------|
| **Crawling** | Web crawl, deep crawl, batch crawl, SSO crawl, connector fetch |
| **Extraction** | Chunk extraction, layout extraction, markdown/Tika, AI Vision, agentic extraction |
| **Indexing** | Chunk indexing, onboarding indexing, embedding generation, OpenSearch writes |
| **Realtime** | Incremental message extraction, webhooks, message connectors |
| **Platform health** | Service pods, queues, schedulers, encryption, ML embeddings |

**Groundcover backends covered:** `us-east-aws`, `centralindia`, `eu-central-1`, `ap-northeast-1`, `ap-southeast`, `gc-aws-sg`, `me-central`, `uaenorth`

**Namespaces (examples):** `xo11-blue`, `xo11-green`, `abl-platform-prod`, `abl-platform-dev`, `abl-platform-indprod`, `abl-platform-fb-prod-abl`

---

## 2. Architecture Overview

Search AI runs as **two major platform stacks** observed in Groundcover:

### Stack A — XO11 / Findly (SearchAssist SaaS)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INGESTION & ORCHESTRATION                            │
│  searchai-app-server-runtime  │  searchai-service-admin  │  searchai-job-   │
│  searchai-app-server-runtime- │                          │  scheduler       │
│  dialog-gpt                   │                          │                  │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │ RabbitMQ (Findly queues)
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  CRAWL                    EXTRACTION                    INDEXING              │
│  ─────                    ──────────                    ────────              │
│  crawler-tasks              chunk-extraction-service      chunk-indexing-service│
│  searchai-crawling-         searchai-chunk-extraction-  onboarding-indexing- │
│    consumers                consumers                    tasks                 │
│  search-batch-crawlconsumers searchai-layout-chunk-     dailog-gpt-chuck-    │
│  search-deep-crawlconsumers   extraction-consumers        indexing-tasks       │
│                             searchai-markdown-extraction-                    │
│                               consumer                                       │
│                             searchai-onboarding-chunk-                       │
│                               extraction-consumers                           │
│                             searchai-aivision-chunk-extract-                 │
│                               consumers                                      │
│                             agentic-extraction-service                       │
│                             searchai-tika-service                            │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  ML / ENCRYPTION / SEARCH BACKEND                                            │
│  searchai-ml-embeddings │ searchai-findly-encryption │ OpenSearch / ES       │
│  searchai-etl-service-dialog-gpt │ MongoDB (searchassist)                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Stack B — ABL Platform (BullMQ-based Search AI)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  abl-platform-*-search-ai          (API / orchestrator — Node.js)             │
│  abl-platform-*-search-ai-worker   (BullMQ job processors)                  │
│  abl-platform-*-search-ai-runtime  (query/runtime layer)                    │
│  abl-platform-*-crawler-go-worker  (Go crawl workers)                         │
│  abl-platform-*-crawler-mcp-server (MCP crawl orchestration)                │
│  abl-platform-*-entity-extraction-service                                     │
│  abl-platform-*-opensearch / opensearch-cluster-master                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### End-to-end document lifecycle

```
Source → Crawl/Connector → Raw doc store → Extraction → Chunks + Vectors → Index → Search API
                │                │              │              │              │
           crawler-tasks    MongoDB/GridFS   RabbitMQ      embeddings    OpenSearch
           crawl consumers  xo_save_crawled  queues        ml-embeddings   bulk index
```

---

## 3. Service Catalog

### 3.1 Core API & Orchestration

| Workload | Role | Log paths (examples) | When to check |
|----------|------|----------------------|---------------|
| `searchai-app-server-runtime` | Main SearchAssist API runtime; ingest, search, config | `/data/logs/findly/` | API errors, ingest failures, auth issues |
| `searchai-app-server-runtime-dialog-gpt` | Dialog GPT variant of app server | Same | GPT-specific ingest/search issues |
| `searchai-service-admin` | Admin service; queue stats, batch crawl orchestration | `BatchCrawlConsumers-*.log` | Queue backlog visibility, ECONNRESET to downstream |
| `searchai-job-scheduler` | Scheduled jobs, cleanup, recurring crawl/extract/index | Scheduler logs | Stuck jobs, DB cleanup errors (code 508) |
| `searchai-findly-encryption` | Document/chunk encryption at rest | Encryption service logs | Decrypt failures, indexing blocked by encryption |
| `search-app-runtime` / `search-app-design` | Search app UI runtime/design | App logs | UI-facing search issues |
| `searchai-etl-service-dialog-gpt` | ETL for dialog GPT pipelines | ETL logs | ETL transform failures |
| `searchai-etl-job-msg-connector` | Message connector ETL jobs | ETL logs | Connector sync failures |

### 3.2 Crawling Services

| Workload | Role | Key resources |
|----------|------|---------------|
| `crawler-tasks` | Crawl job orchestration (ArgoCD: `crawler-tasks-prod-blue`) | `FindlyCrawlBatches`, `web_crawl_batch_queue` |
| `searchai-crawling-consumers` | Primary crawl message consumers | `web_crawl_batch_queue`, `CrawlBatchesQueue` |
| `search-batch-crawlconsumers` | Batch crawl processing | `batchStats "CrawlBatchesQueue"` |
| `search-deep-crawlconsumers` | Deep/multi-level crawl | Deep crawl queues |
| `findly-BatchCrawlConsumers` | Legacy Findly batch crawl (log role) | `BatchCrawlConsumers-*.log` |
| `findly-DeepCrawlConsumers` | Legacy deep crawl | Deep crawl logs |
| `findly-XoSaveCrawlDocs` | Saves crawled documents post-crawl | `xo_save_crawled_documents` |
| `abl-platform-*-crawler-go-worker` | Go-based crawler workers (ABL) | Crawl job queues |
| `abl-platform-*-crawler-mcp-server` | MCP server for crawl orchestration | MCP crawl API |

### 3.3 Extraction Services

| Workload | Role | Extraction type |
|----------|------|-----------------|
| `chunk-extraction-service` | Core chunk extraction API | Standard documents |
| `chunk-extraction-tasks` | Async chunk extraction tasks | Task-based |
| `searchai-chunk-extraction-consumers` | RabbitMQ consumer for chunk extraction | `Extraction Queue`, `ExtractionDefaultQueue` |
| `searchai-layout-chunk-extraction-consumers` | Layout-aware extraction (PDFs, complex docs) | Layout extraction |
| `searchai-markdown-extraction-consumer` | Markdown-specific extraction | Markdown docs |
| `searchai-markdown-chunk-extraction-consumers` | Markdown chunk consumers | Markdown chunks |
| `searchai-onboarding-chunk-extraction-consumers` | Onboarding/new index extraction | `ExtractionOnboardQueue` |
| `searchai-aivision-chunk-extract-consumers` | AI Vision (image/OCR) extraction | Vision docs |
| `searchai-message-connector-extraction-consumers` | Full sync message connector extraction | `MsgConnectorFullSyncQueue` |
| `searchai-message-connector-webhook-extraction-consumers` | Webhook-driven extraction | `MsgConnectorWebhookQueue` |
| `searchai-incremental-message-extraction` | Incremental connector updates | `MsgConnectorIncrementalQueue` |
| `search-incremental-msg-extraction` | Incremental msg extraction (alt deployment) | Incremental queues |
| `onboarding-extraction-tasks` | Onboarding extraction task runner | Onboarding pipeline |
| `layout-aware-extraction-tasks` | Layout extraction tasks | Layout pipeline |
| `agentic-extraction-service` | LLM/agent-based extraction | Custom/agentic docs |
| `searchai-tika-service` | Apache Tika document parsing | Office/PDF binary parsing |
| `events-extractor` | Event stream extraction | Event sources |
| `abl-platform-*-entity-extraction-service` | ABL entity extraction | ABL pipeline |

### 3.4 Indexing Services

| Workload | Role | Key queues |
|----------|------|------------|
| `chunk-indexing-service` | Core indexing service | `Indexing Queue`, `IndexingDefaultQueue` |
| `chunk-indexing-tasks` | Async indexing tasks | Indexing task queues |
| `onboarding-indexing-tasks` | Onboarding index builds | `IndexingHeavyQueue` |
| `dailog-gpt-chuck-indexing-tasks` | Dialog GPT chunk indexing | GPT indexing queues |
| `searchai-ml-embeddings` | Embedding vector generation | Embedding calls |
| `abl-platform-*-search-ai-worker` | ABL BullMQ indexing workers | `search-embedding`, etc. |

### 3.5 ABL Platform Search AI (per environment)

| Environment prefix | Workloads |
|--------------------|-----------|
| `abl-platform-dev-*` | search-ai, search-ai-worker, search-ai-runtime, opensearch, bullmq-retention-audit |
| `abl-platform-sit-*` | search-ai, search-ai-runtime, crawler-go-worker, crawler-mcp-server |
| `abl-platform-staging-*` | search-ai, search-ai-runtime, crawler-mcp-server |
| `abl-platform-qa-*` | search-ai, search-ai-runtime, search-ai-worker |
| `abl-platform-indprod-*` | search-ai, search-ai-runtime, opensearch-cluster-master |
| `abl-platform-prod-*` | search-ai, crawler-go-worker, crawler-mcp-server |
| `abl-platform-fb-prod-abl-*` | search-ai, crawler-go-worker, crawler-mcp-server |
| `abl-platform-awsprodus-*` | search-ai, crawler components |

---

## 4. Queue & Messaging Reference

### 4.1 Findly / XO11 RabbitMQ Queues

Observed in `searchai-job-scheduler` and `searchai-service-admin` logs:

| Queue name | Stage | Consumer workload(s) |
|------------|-------|----------------------|
| `CrawlBatchesQueue` | Crawl | `search-batch-crawlconsumers`, `searchai-crawling-consumers` |
| `web_crawl_batch_queue` | Crawl | `searchai-crawling-consumers` |
| `Extraction Queue` | Extraction | `searchai-chunk-extraction-consumers` |
| `ExtractionDefaultQueue` | Extraction | `searchai-chunk-extraction-consumers` |
| `ExtractionOnboardQueue` | Extraction (onboarding) | `searchai-onboarding-chunk-extraction-consumers` |
| `ExtractionCustomApiQueue` | Extraction (custom API) | Custom extraction SDK callback path |
| `DocWorkbenchQueue` | Extraction/workbench | Doc workbench consumers |
| `DocWorkbenchHeavyQueue` | Extraction (heavy) | Heavy doc processing |
| `Doc Workbench Queue` | Extraction | Workbench pipeline |
| `Indexing Queue` | Indexing | `chunk-indexing-service` |
| `IndexingDefaultQueue` | Indexing | `chunk-indexing-service` |
| `IndexingHeavyQueue` | Indexing (heavy/onboarding) | `onboarding-indexing-tasks` |
| `IndexingMsgConnectorQueue` | Indexing (connectors) | Connector indexing |
| `MsgConnectorFullSyncQueue` | Connector sync | `searchai-message-connector-extraction-consumers` |
| `MsgConnectorIncrementalQueue` | Connector incremental | `searchai-incremental-message-extraction` |
| `MsgConnectorWebhookQueue` | Connector webhooks | `searchai-message-connector-webhook-extraction-consumers` |
| `WebhookEventsQueue` | Webhook events | Webhook consumers |
| `AutoSuggestQueue` | Autosuggest indexing | Autosuggest pipeline |

**MongoDB collections (crawl orchestration):** `searchassist.FindlyCrawlBatches`

### 4.2 ABL Platform BullMQ Queues

Observed via `searchai_queue_*` metrics on `abl-platform-prod-search-ai`:

| Queue name | Stage |
|------------|-------|
| `search-page-processing` | Crawl → page processing |
| `search-docling-extraction` | Docling-based extraction |
| `search-enrichment` | Content enrichment |
| `search-embedding` | Vector embedding generation |
| `search-canonical-map` | Canonical URL mapping |

### 4.3 Key metrics for queue health

| Metric | Meaning | Alert threshold (suggested) |
|--------|---------|----------------------------|
| `searchai_queue_waiting` | Jobs waiting in BullMQ queue | > 100 for > 15 min |
| `searchai_queue_oldest_waiting_age_milliseconds` | Age of oldest waiting job | > 300000 (5 min) |
| `searchai_queue_active` | Currently processing jobs | 0 while waiting > 0 = stuck workers |
| `searchai_worker_active_jobs` | Active worker jobs | Compare across replicas |
| `searchai_worker_job_duration_milliseconds` | Job processing time | p95 spike vs baseline |
| `rabbitmq_queue_messages` | RabbitMQ depth | Env-specific baseline |
| `rabbitmq_queue_consumer_utilisation` | Consumer capacity used | < 0.1 with high depth = under-consumed |
| `rabbitmq_global_messages_delivered_total` | Delivery rate | Drop = consumer outage |

---

## 5. Data Stores & Dependencies

| Store | Host examples (from logs) | Used for |
|-------|---------------------------|----------|
| **MongoDB** | `pab-bots-searchassist-mongos1.kore-prod-aws.com`, `mongos2` | Crawl batches, doc metadata, job state |
| **OpenSearch / Elasticsearch** | `opensearch-cluster-master`, `ebay-esw-searchassist-es` zone | Vector + keyword index |
| **RabbitMQ** | `rabbitmqa-server`, `rabbitmqb-server`, `rabbitmq-server` | Async pipeline queues (Findly) |
| **Redis / BullMQ** | ABL platform internal | ABL job queues |
| **Kafka** | `otel-kafka-kafka-brokers` | OTEL/telemetry (not primary pipeline) |

**External dependencies:**
- LLM APIs (OpenAI, Azure OpenAI, Anthropic) — `searchai_llm_call_*` metrics
- Embedding models — `searchai-ml-embeddings`, `searchai_embedding_*` metrics
- Custom extraction SDK (customer-hosted, port 6606) — callback URL reachability

---

## 6. Observability — Groundcover Playbook

### 6.1 First 5 minutes checklist

| Step | Action | Groundcover query |
|------|--------|-------------------|
| 1 | Identify affected workload | Entities: `workload:*searchai* \| stats by (workload) count()` |
| 2 | Check pod health | Events: `reason:Failed workload:*searchai*` |
| 3 | Check error log rate | Logs: `workload:<service> level:error \| stats by (body) count()` |
| 4 | Check queue depth | Metrics: `searchai_queue_waiting`, `rabbitmq_queue_messages` |
| 5 | Check processing latency | Metrics: `searchai_worker_job_duration_milliseconds`, `searchai_embedding_duration_milliseconds` |
| 6 | Trace a failing doc | Logs: filter by `streamId`, `docId`, or `x-trace-id` |

**Backend selection:** Always pass `backend_id` (e.g. `us-east-aws`, `centralindia`) when querying Groundcover.

### 6.2 Workloads with highest error volume (24h snapshot — us-east-aws)

| Workload | Error pattern |
|----------|---------------|
| `searchai-service-admin` | `ECONNRESET`, Axios HTTP client errors to downstream services |
| `searchai-job-scheduler` | `DBError code 508` during cleanup |
| `searchai-app-server-runtime` | `RecordNotFound`, downstream errors |
| `searchai-chunk-extraction-consumers` | `Invalid IPv6 URL` during link processing |

### 6.3 Known scheduling issues

These workloads have recurring `FailedScheduling` events (node affinity / taints):
- `search-batch-crawlconsumers`
- `search-deep-crawlconsumers`
- `searchai-aivision-chunk-extract-consumers`

**Fix pattern:** Verify node pool labels, taints/tolerations, and resource requests in deployment manifests.

### 6.4 Log file locations (Findly pods)

| Log path | Component |
|----------|-----------|
| `/data/logs/findly/BatchCrawlConsumers-*.log` | Batch crawl consumers |
| `/data/logs/findly/extract_consumer.log` | Extraction consumers |
| `/data/logs/nodeservices/findlyXoSaveCrawlDocs*` | Save crawled docs |
| `/data/logs/findly/` (general) | Findly services |

### 6.5 Distributed tracing (RabbitMQ)

RabbitMQ consumers are historically under-instrumented. Use `customTraceId` propagation (see `Blog/Published/Newrelic-Instrumentation.md`):
- Pass trace ID when publishing to queue
- Wrap consumer processing in background transaction
- NRQL: `SELECT message.queueName, duration FROM Transaction WHERE customTraceId = '<id>'`

---

## 7. Incident Triage Decision Tree

```
User reports Search AI issue
         │
         ▼
┌─ Is search/query broken? ──YES──► Check searchai-app-server-runtime, OpenSearch health
│        NO
│        ▼
├─ Is new content missing? ──YES──► Trace doc through pipeline (crawl→extract→index)
│        NO
│        ▼
├─ Is processing slow? ──YES──► Check queue depth + worker job duration metrics
│        NO
│        ▼
├─ Is a service down? ──YES──► Check pod status, restarts, FailedScheduling events
│        NO
│        ▼
└─ Integration/custom SDK issue? ──► See Section 10 (client-side TSG)
```

### Symptom → First service to inspect

| Symptom | Start here | Then check |
|---------|------------|------------|
| Web crawl not starting | `crawler-tasks`, `searchai-job-scheduler` | `CrawlBatchesQueue` depth |
| Crawl running but no docs | `searchai-crawling-consumers`, `findly-XoSaveCrawlDocs` | MongoDB `FindlyCrawlBatches` |
| Docs crawled but not extracted | `searchai-chunk-extraction-consumers` | `Extraction Queue` depth |
| Extracted but not indexed | `chunk-indexing-service` | `Indexing Queue`, OpenSearch bulk errors |
| Onboarding stuck | `searchai-onboarding-chunk-extraction-consumers`, `onboarding-indexing-tasks` | `ExtractionOnboardQueue`, `IndexingHeavyQueue` |
| Connector sync failing | `searchai-message-connector-extraction-consumers` | `MsgConnectorFullSyncQueue` |
| Incremental updates missing | `searchai-incremental-message-extraction` | `MsgConnectorIncrementalQueue` |
| PDF/Office parsing fails | `searchai-tika-service` | Tika OOM, timeout |
| Image/OCR extraction fails | `searchai-aivision-chunk-extract-consumers` | Vision API limits, scheduling |
| Embeddings slow/failing | `searchai-ml-embeddings` | `searchai_embedding_duration_milliseconds` |
| Encryption errors | `searchai-findly-encryption` | Key rotation, decrypt logs |
| ABL pipeline stuck | `abl-platform-*-search-ai-worker` | BullMQ queue metrics |

---

## 8. Module-by-Module TSG

---

### 8.1 Crawling (`crawler-tasks`, `searchai-crawling-consumers`, batch/deep consumers)

#### Symptoms
- Crawl job shows "in progress" indefinitely
- Zero pages crawled
- `web_crawl_batch_queue` depth growing
- `FailedScheduling` on crawl consumer pods

#### Debugging steps
1. **Groundcover — pod status**
   ```
   workload:crawler-tasks OR workload:searchai-crawling-consumers | fields workload, namespace, cluster, status
   ```
2. **Groundcover — crawl errors**
   ```
   workload:*crawl* level:error | stats by (body) count() | sort by (count desc) | limit 20
   ```
3. **Check queue depth** — RabbitMQ `CrawlBatchesQueue`, `web_crawl_batch_queue`
4. **Check scheduler** — `searchai-job-scheduler` logs for `batchStats "CrawlBatchesQueue"`
5. **MongoDB** — Verify `FindlyCrawlBatches` documents progressing past `ready-to-queue`
6. **ArgoCD** — Check sync status for `crawler-tasks-prod-blue`, `searchai-crawling-consumers-prod-blue`

#### Common root causes & fixes

| Root cause | Evidence | Fix |
|------------|----------|-----|
| Consumer pods not scheduled | `FailedScheduling`, node affinity errors | Fix tolerations/node selectors; scale node pool |
| RabbitMQ consumers down | Queue depth ↑, `rabbitmq_queue_consumers` = 0 | Restart consumers; check RabbitMQ cluster health |
| SSO/session expired (external crawler) | 401/403 in crawl logs | Re-authenticate SSO crawler utility |
| Target site blocking bot | Timeout, 403 in crawl logs | Adjust crawl delay, user-agent, IP allowlist |
| MongoDB unreachable | DBError in scheduler | Check mongos connectivity (`pab-bots-searchassist-mongos*`) |
| Crawl batch stuck in `ready-to-queue` | Scheduler logs show status filter | Restart `searchai-job-scheduler`; check DB lock |

#### Immediate next steps
1. Confirm crawl consumer pod count matches expected replicas
2. Check oldest message age in `CrawlBatchesQueue`
3. If single-tenant issue, identify `streamId` / bot ID in admin logs
4. Escalate to platform if RabbitMQ cluster unhealthy

---

### 8.2 Extraction (`chunk-extraction-service`, extraction consumers)

#### Symptoms
- Documents visible in admin UI but status "extracting"
- `Extraction Queue` / `ExtractionDefaultQueue` backlog
- Empty chunks after extraction
- Custom extraction callback timeout

#### Debugging steps
1. **Identify extraction path** (standard vs layout vs markdown vs vision vs onboarding)
2. **Groundcover logs**
   ```
   workload:searchai-chunk-extraction-consumers level:error | limit 20
   workload:searchai-layout-chunk-extraction-consumers level:error | limit 20
   workload:searchai-markdown-extraction-consumer level:error | limit 20
   ```
3. **Check extraction service health**
   ```
   workload:chunk-extraction-service | fields workload, namespace, cluster
   ```
4. **Tika service** (binary docs): `searchai-tika-service` CPU/memory, response times
5. **Custom extraction**: Verify customer SDK reachable on port 6606, `x-callback-url` valid
6. **Agentic extraction**: `agentic-extraction-service` LLM call metrics

#### Common root causes & fixes

| Root cause | Evidence | Fix |
|------------|----------|-----|
| Extraction consumer scaled to 0 | No consumers on queue | Scale up deployment |
| Tika OOM on large PDFs | Tika pod restarts, OOMKilled events | Increase memory limits; split large docs |
| Invalid URL in crawl content | `Invalid IPv6 URL` in chunk-extraction logs | Fix source URL normalization |
| Custom SDK callback failure | 202 returned but no callback | Check customer firewall, API key, port 6606 |
| LLM rate limit (agentic) | `searchai_llm_call_*` errors spike | Backoff, increase quota, scale consumers |
| Layout extraction timeout | layout-consumer logs, long job duration | Increase timeout; use `DocWorkbenchHeavyQueue` |

#### Immediate next steps
1. Map document to correct extraction queue
2. Check `/data/logs/findly/extract_consumer.log` on extraction pod
3. Re-queue document from admin if stuck (if supported)
4. For custom extraction, test callback URL with curl from platform network

---

### 8.3 Indexing (`chunk-indexing-service`, indexing tasks, embeddings)

#### Symptoms
- Chunks exist but not searchable
- `Indexing Queue` / `IndexingHeavyQueue` backlog
- Search returns stale results
- OpenSearch bulk rejections

#### Debugging steps
1. **Queue depth**
   ```
   Logs: body:*Indexing* workload:searchai-job-scheduler | stats by (body) count()
   ```
2. **Indexing service health**
   ```
   workload:chunk-indexing-service OR workload:onboarding-indexing-tasks
   ```
3. **Embedding latency**
   ```
   PromQL: rate(searchai_embedding_duration_milliseconds_sum[5m]) / rate(searchai_embedding_duration_milliseconds_count[5m])
   ```
4. **OpenSearch health**
   ```
   workload:opensearch-cluster-master | fields workload, namespace, cluster
   Metrics: opensearch_bulk_items_succeeded_total, search_pipeline_error_total
   ```
5. **Encryption layer** — `searchai-findly-encryption` errors before index write

#### Common root causes & fixes

| Root cause | Evidence | Fix |
|------------|----------|-----|
| Indexing consumer backlog | `Indexing Queue` depth high | Scale `chunk-indexing-service` / indexing tasks |
| Embedding service slow | `searchai_embedding_duration` p95 spike | Scale `searchai-ml-embeddings`; check GPU/CPU |
| OpenSearch cluster red | OpenSearch health API, shard unassigned | Fix shard allocation, disk space |
| Mapping conflict | OpenSearch bulk error in logs | Reindex with correct mapping |
| Encryption key mismatch | `searchai-findly-encryption` errors | Verify key config, rotation state |
| Heavy onboarding queue | `IndexingHeavyQueue` only backed up | Scale `onboarding-indexing-tasks` |

#### Immediate next steps
1. Verify OpenSearch cluster status (green/yellow/red)
2. Check if issue is global or single `searchIndexId` / bot
3. Compare embedding throughput vs indexing enqueue rate
4. Check disk usage on OpenSearch nodes

---

### 8.4 Job Scheduler (`searchai-job-scheduler`)

#### Symptoms
- Scheduled crawls not triggering
- Cleanup jobs failing
- Queue stats not updating

#### Debugging steps
1. ```
   workload:searchai-job-scheduler level:error | stats by (body) count()
   ```
2. Look for `jobDetails "<QueueName>"` log lines — confirms queue monitoring active
3. Check `Error in cleanup: CustomKoreError [DBError]: {}` with `code: 508`

#### Fixes
| Issue | Fix |
|-------|-----|
| DBError 508 on cleanup | Check MongoDB connectivity; verify cleanup job permissions |
| Scheduler pod crash loop | Check memory, DB connection pool exhaustion |
| Jobs not enqueued | Verify scheduler cron config; check `ready-to-queue` filter logic |

---

### 8.5 Service Admin (`searchai-service-admin`)

#### Symptoms
- Batch crawl orchestration failures
- HTTP errors to downstream (ECONNRESET)
- Configuration API failures

#### Debugging steps
1. ```
   workload:searchai-service-admin level:error | limit 20
   ```
2. Filter for `isAxiosError`, `ECONNRESET`, `cause: Error: read ECONNRESET`
3. Check downstream target of failed HTTP calls (app-server-runtime, MongoDB)

#### Fixes
- **ECONNRESET** — Downstream service restarted or connection pool exhausted; check target pod health
- **Configuration API** — `/searchassistapi/internal/configuration` failures; verify app-server-runtime

---

### 8.6 App Server Runtime (`searchai-app-server-runtime`)

#### Symptoms
- Ingest API 5xx
- Search API errors
- Auth/token failures

#### Key API endpoints (from integration toolkit)
| Operation | Endpoint |
|-----------|----------|
| Ingest (UnifiedXO) | `POST /api/public/bot/{streamId}/ingest-data` |
| Ingest (legacy) | `POST /searchassistapi/external/stream/{streamId}/ingest?...&index=true` |
| Advanced Search | `POST /api/public/bot/{bot_id}/search/v2/advanced-search` |
| Chunk list | `POST /api/public/bot/{botId}/chunk/list` |
| Internal config | `GET /searchassistapi/internal/configuration` |

#### Debugging
1. Check ingress/nginx (`searchassist-nginx-80`) if external reachability issue
2. Filter logs by `kore_route`, `request_uri`, `streamId`
3. Verify JWT/token expiry for ingest calls

---

### 8.7 ML Embeddings (`searchai-ml-embeddings`)

#### Metrics
- `searchai_embedding_duration_milliseconds_*`
- `searchai_embedding_vectors_total`
- `searchai_llm_call_duration_milliseconds_*`

#### Symptoms
- Indexing blocked waiting for vectors
- High embedding latency

#### Fixes
- Scale embedding service replicas
- Check model loading / GPU availability
- Verify embedding API rate limits

---

### 8.8 ABL Platform Search AI

#### Components
- `abl-platform-*-search-ai` — API + BullMQ producer
- `abl-platform-*-search-ai-worker` — Queue consumers
- `abl-platform-*-search-ai-runtime` — Search runtime

#### BullMQ queue TSG

| Check | PromQL / action |
|-------|-----------------|
| Waiting jobs | `searchai_queue_waiting{queue="search-embedding"}` |
| Stale jobs | `searchai_queue_oldest_waiting_age_milliseconds > 300000` |
| Worker saturation | `searchai_worker_active_jobs` per pod |
| Job failures | `searchai_worker_job_total` vs success counter |

#### Pipeline order (ABL)
```
search-page-processing → search-docling-extraction → search-enrichment → search-embedding → search-canonical-map → OpenSearch
```

**If `search-page-processing` backed up:** Check crawler-go-worker and crawler-mcp-server  
**If `search-embedding` backed up:** Scale search-ai-worker; check embedding service

---

## 9. Scenario Playbooks

### 9.1 "Crawl is slow"

| Step | Action |
|------|--------|
| 1 | Measure `CrawlBatchesQueue` / `web_crawl_batch_queue` depth and consumer count |
| 2 | Check `search-batch-crawlconsumers` and `search-deep-crawlconsumers` pod CPU/memory |
| 3 | Review crawl config: `maxPages`, `delay`, `batchSize` (client or platform config) |
| 4 | Check target site rate limiting (429/503 in crawl logs) |
| 5 | Verify MongoDB write latency for `FindlyCrawlBatches` |
| 6 | For external SSO crawler: reduce `batchSize`, increase `delay` (default 20000ms) |

### 9.2 "Extraction is slow"

| Step | Action |
|------|--------|
| 1 | Identify queue: `Extraction Queue` vs `DocWorkbenchHeavyQueue` vs `ExtractionOnboardQueue` |
| 2 | Compare enqueue rate vs `searchai_worker_job_duration` / consumer throughput |
| 3 | Check if docs are routed to heavy queue (large PDFs, layout docs) |
| 4 | Inspect `searchai-tika-service` if binary parsing involved |
| 5 | Check LLM/vision API latency for agentic/vision extraction |
| 6 | Scale appropriate extraction consumer deployment |

### 9.3 "Indexing is slow"

| Step | Action |
|------|--------|
| 1 | Check `Indexing Queue` and `IndexingHeavyQueue` depth |
| 2 | Measure `searchai_embedding_duration` p95 |
| 3 | Check OpenSearch bulk throughput: `opensearch_bulk_items_succeeded_total` rate |
| 4 | Verify `searchai-findly-encryption` not adding excessive latency |
| 5 | Check OpenSearch JVM heap, disk watermarks |
| 6 | Scale `chunk-indexing-service` and/or `searchai-ml-embeddings` |

### 9.4 "Queue health degraded"

| Step | Action |
|------|--------|
| 1 | **RabbitMQ (Findly):** `rabbitmq_queue_messages`, `rabbitmq_queue_consumers`, `rabbitmq_queue_consumer_utilisation` |
| 2 | **BullMQ (ABL):** `searchai_queue_waiting`, `searchai_queue_active`, `searchai_queue_pending` |
| 3 | Check RabbitMQ cluster: `rabbitmq_unreachable_cluster_peers_count`, pod restarts |
| 4 | Look for poison messages: single message type causing consumer crash loop |
| 5 | Check `rabbitmq_global_messages_dead_lettered_delivery_limit_total` |
| 6 | Drain or move messages to DLQ if needed (with platform team approval) |

### 9.5 "Service unhealthy / pods crashing"

| Step | Action |
|------|--------|
| 1 | `query_events`: `reason:Failed OR reason:Unhealthy workload:*searchai*` |
| 2 | Check OOMKilled, CrashLoopBackOff, FailedScheduling |
| 3 | Review last 50 lines of pod logs before crash |
| 4 | Check dependent services (MongoDB, RabbitMQ, OpenSearch) |
| 5 | Compare resource requests/limits vs actual usage |
| 6 | Rollback recent deployment if correlated with ArgoCD sync |

### 9.6 "Realtime / incremental sync not working"

| Step | Action |
|------|--------|
| 1 | Check `searchai-incremental-message-extraction` / `search-incremental-msg-extraction` pods |
| 2 | Monitor `MsgConnectorIncrementalQueue` depth |
| 3 | Verify webhook consumers: `searchai-message-connector-webhook-extraction-consumers` |
| 4 | Check `WebhookEventsQueue` for webhook delivery failures |
| 5 | Validate connector credentials and webhook endpoint reachability |
| 6 | Compare last successful sync timestamp in connector logs |

### 9.7 "Data visible in admin but not in search"

| Step | Action |
|------|--------|
| 1 | Confirm chunks exist: Chunk List API `/api/public/bot/{botId}/chunk/list` |
| 2 | Check indexing status in admin UI / MongoDB doc status |
| 3 | Verify `searchIndexId` matches active index |
| 4 | Check RACL / access control filters on search |
| 5 | Query OpenSearch directly for document ID |
| 6 | Check if encryption/decryption failed silently |

---

## 10. Client-Side / Integration TSG

> Source: SearchAssist Toolkit (`/workspace`) — client utilities that connect to hosted Search AI.

### 10.1 SSO Crawling Utility

| Issue | Debug | Fix |
|-------|-------|-----|
| Chrome won't start | `which google-chrome`, verify `chromePath` | Install Chrome; fix path in `crawler.json` |
| Auth failure | 401 on ingest API | Refresh `authToken`, verify `streamId` |
| Memory exhaustion | OOM during large crawl | Reduce `batchSize` (default 50) |
| Network timeout | Axios timeout errors | Increase `ingest.timeout` (default 10000ms) |
| SSO session lost | Pages redirect to login | Re-run manual SSO login; check `chrome_profile` |
| Wrong chunk model | Documents not searchable | Set `isUnifiedXO: true` for XO11, `false` for XO10 |

**Ingest endpoints:**
- XO11: `POST /api/public/bot/{streamId}/ingest-data`
- XO10: `POST /searchassistapi/external/stream/{streamId}/ingest?contentSource=manual&extractionType=data&index=true`

### 10.2 Custom Extraction SDK (port 6606)

| Issue | Debug | Fix |
|-------|-------|-----|
| Port unavailable | `EADDRINUSE :6606` | Kill conflicting process or change `SERVER.PORT` |
| Missing headers | 400 from SDK | Ensure `x-trace-id` and `x-callback-url` present |
| Callback never received | 202 returned but no platform update | Verify callback URL reachable from platform; check API key |
| Extraction logic error | Stack trace in SDK logs | Fix custom `CustomExtractionLogic`; enable debug mode |

**Flow:** Platform POSTs doc → SDK returns 202 → async extraction → POST chunks to `x-callback-url`

### 10.3 Custom Connector Service (port 3232)

| Issue | Debug | Fix |
|-------|-------|-----|
| Platform can't poll content | Connection refused | Ensure service running; check `Authorization` in `.env` |
| Pagination stuck | Same offset returned | Verify `GET /getContent?limit&offset` implementation |

### 10.4 Custom SDK Connector (ingest.js)

| Issue | Debug | Fix |
|-------|-------|-----|
| Batch ingest failures | Axios error logs | Verify `SEARCHAI_HOST_NAME`, `SEARCHAI_JWT_TOKEN`, `STREAM_ID` |
| Slow ingest | High batch failure retry | Tune `INGESTION_BATCH_SIZE` (default 10) |

### 10.5 Custom Embeddings Service (port 5000)

| Issue | Debug | Fix |
|-------|-------|-----|
| Returns `[0]` vector | Model path missing | Ensure `/var/www/multilingual-e5-base` exists |
| Model load failure | Flask startup errors | Check model files and permissions |

---

## 11. Realtime Processing TSG

### Message connector pipeline

```
Connector source → MsgConnectorFullSyncQueue → searchai-message-connector-extraction-consumers
                → MsgConnectorIncrementalQueue → searchai-incremental-message-extraction
                → MsgConnectorWebhookQueue → searchai-message-connector-webhook-extraction-consumers
                                                      ↓
                                            IndexingMsgConnectorQueue → chunk-indexing-service
```

### Debugging realtime issues

1. **Identify sync type:** Full vs incremental vs webhook
2. **Check corresponding queue depth** (see Section 4.1)
3. **Verify ETL job:** `searchai-etl-job-msg-connector` pod health
4. **Check webhook delivery:** `WebhookEventsQueue`, customer endpoint HTTP status
5. **Compare timestamps:** Last sync time in connector config vs latest indexed doc
6. **Auth/token expiry:** Connector credentials rotated without platform update

### Realtime health indicators

| Indicator | Healthy | Unhealthy |
|-----------|---------|-----------|
| `MsgConnectorIncrementalQueue` depth | Near 0 between syncs | Continuously growing |
| Incremental consumer pods | Running, processing | CrashLoop / FailedScheduling |
| Webhook latency | < 30s end-to-end | Timeouts, 5xx to customer endpoint |
| Index freshness | New docs searchable < SLA | Hours/days stale |

---

## 12. Performance & Slowness TSG

### 12.1 Baseline metrics to establish

| Metric | Component |
|--------|-----------|
| `searchai_worker_job_duration_milliseconds` p50/p95 | All BullMQ workers |
| `searchai_embedding_duration_milliseconds` p95 | Embedding generation |
| `searchai_llm_call_duration_milliseconds` p95 | LLM-based extraction |
| `search_query_duration_ms_milliseconds` p95 | Search runtime |
| `rabbitmq_queue_messages` per queue | Findly pipeline |
| Crawl pages/minute | Crawl consumers (from logs) |
| OpenSearch bulk latency | Indexing service |

### 12.2 Bottleneck identification matrix

| If this is slow... | Likely bottleneck | Scale target |
|--------------------|-------------------|--------------|
| Crawl enqueue | `crawler-tasks`, scheduler | scheduler, MongoDB |
| Crawl processing | `searchai-crawling-consumers` | crawl consumers |
| Extraction | extraction consumers | specific consumer type |
| Embedding | `searchai-ml-embeddings` | embedding service |
| Index write | `chunk-indexing-service` | indexing service + OpenSearch |
| Search query | `searchai-app-server-runtime`, OpenSearch | runtime + OS data nodes |

### 12.3 Resource exhaustion signals

| Signal | Groundcover check |
|--------|-------------------|
| CPU throttling | Pod CPU metrics vs limits |
| OOM kills | Events: `reason:OOMKilled` |
| Disk full (OpenSearch) | OpenSearch node disk metrics |
| Connection pool exhausted | `ECONNRESET` in service-admin logs |
| Event loop lag | `searchai_event_loop_delay_max_milliseconds` |

---

## 13. Escalation & Immediate Next Steps

### Severity guide

| Severity | Criteria | Response |
|----------|----------|----------|
| **SEV-1** | Search API down for all tenants; OpenSearch red; RabbitMQ cluster down | Page on-call platform + DBA |
| **SEV-2** | Pipeline stalled > 2h for production tenant; queue depth growing unbounded | Engage Search AI team within 30 min |
| **SEV-3** | Single tenant crawl/extract slow; non-prod environment | Next business day; document in ticket |
| **SEV-4** | Client-side utility issue; single document failure | Support team + integration docs |

### Information to collect before escalation

- [ ] Affected `streamId` / `botId` / `searchIndexId`
- [ ] Environment (namespace, cluster, backend_id)
- [ ] Pipeline stage where stuck (crawl / extract / index / search)
- [ ] Queue name and current depth
- [ ] Sample `docId` / `x-trace-id`
- [ ] Groundcover log snippets (error body, timestamp)
- [ ] Timeline: when started, last successful processing
- [ ] Recent deployments (ArgoCD sync events)

### Escalation contacts (fill in per org)

| Team | Scope |
|------|-------|
| Search AI Platform | Pipeline services, queue consumers, schedulers |
| Infra / SRE | Kubernetes, RabbitMQ, OpenSearch clusters |
| DBA | MongoDB `searchassist` database |
| ML Platform | `searchai-ml-embeddings`, embedding models |
| Customer Integration | Custom SDK, SSO crawler, connectors |

---

## 14. Appendix: gcQL & PromQL Cookbook

### Groundcover gcQL — copy/paste queries

**List all Search AI workloads:**
```
workload:*searchai* OR workload:*crawl* OR workload:*index* OR workload:*extract* | stats by (workload) count() | sort by (count desc) | limit 100
```

**Error rate by workload (24h):**
```
workload:*searchai* level:error | stats by (workload) count() | sort by (count desc) | limit 30
```

**Failed pod events:**
```
reason:Failed workload:*searchai* OR workload:*crawl* | fields workload, reason, message | limit 50
```

**Queue monitoring logs:**
```
body:*jobDetails* workload:searchai-job-scheduler | stats by (body) count() | sort by (count desc) | limit 20
```

**Crawl resource activity:**
```
resource:web_crawl_batch_queue | stats count()
```

**Extraction errors:**
```
workload:searchai-chunk-extraction-consumers level:error | fields timestamp, body | limit 20
```

**Service admin connection errors:**
```
workload:searchai-service-admin level:error body:*ECONNRESET* | limit 20
```

**Scheduler DB errors:**
```
workload:searchai-job-scheduler level:error body:*DBError* | limit 20
```

### PromQL — copy/paste queries

**BullMQ queue waiting (ABL):**
```promql
sum by (queue) (searchai_queue_waiting)
```

**Oldest waiting job age:**
```promql
max by (queue) (searchai_queue_oldest_waiting_age_milliseconds)
```

**Embedding latency (avg 5m):**
```promql
rate(searchai_embedding_duration_milliseconds_sum[5m]) / rate(searchai_embedding_duration_milliseconds_count[5m])
```

**Worker job throughput:**
```promql
rate(searchai_worker_job_total[5m])
```

**RabbitMQ queue depth:**
```promql
rabbitmq_queue_messages
```

**RabbitMQ consumer utilization:**
```promql
rabbitmq_queue_consumer_utilisation
```

**OpenSearch bulk success rate:**
```promql
rate(opensearch_bulk_items_succeeded_total[5m])
```

---

## Document maintenance

| Action | Frequency |
|--------|-----------|
| Refresh service catalog from Groundcover entities | Monthly |
| Update queue names from scheduler logs | After platform releases |
| Review error patterns from Groundcover logs | Quarterly |
| Validate gcQL queries against current field names | After Groundcover upgrades |

---

*This document was generated from Groundcover observability data (kore.ai tenant) and SearchAssist Toolkit integration documentation. Update service names and queue lists as deployments evolve.*
