# nfo — TODO / Roadmap

## 📊 Current Project State (v0.3.0)

**Project Scale Analysis** (from `project.functions.toon`):
- **46 modules** total: 11 core nfo/, 10 tests/, 13 examples/, 2 demo/, tools/
- **448 functions** across all modules with full metadata tracking
- **114 tests** providing comprehensive coverage
- **7 sink types**: SQLite, CSV, Markdown, JSON, Prometheus, Webhook, LLM
- **Multi-language clients**: Go, Rust, Bash with HTTP/gRPC support
- **DevOps integration**: Docker Compose, Kubernetes, monitoring stack

**Function Distribution**:
- Core logging infrastructure: 85 functions (decorators, sinks, models)
- Test suite: 156 test functions across 10 test modules  
- Examples: 65 functions demonstrating all features
- Demo/Load generation: 15 functions for performance testing

## ✅ Done (v0.3.0)

### Binary Metadata Logging (v0.3.0)
- [x] `ThresholdPolicy` — size-based decision on full data vs metadata
- [x] `MetaExtractor` — image/audio/binary/file/numpy/pandas extractors with magic byte detection
- [x] `register_extractor()` — custom extractor registry for user-defined types
- [x] `@meta_log` — dedicated decorator for binary data pipelines (sync + async)
- [x] `BinaryAwareRouter` — sink routing based on payload characteristics
- [x] `@log_call(extract_meta=True)` / `@catch(extract_meta=True)` — opt-in in existing decorators
- [x] `configure(meta_policy=..., auto_extract_meta=True)` — global configuration
- [x] `NFO_META_THRESHOLD` / `NFO_META_EXTRACT` env vars
- [x] 79 new tests (test_meta, test_extractors, test_meta_decorators, test_binary_router)

### Core
- [x] `@log_call`, `@catch` decorators
- [x] `@logged` — class decorator (auto-wrap all public methods)
- [x] `@skip` — exclude methods from `@logged`
- [x] `auto_log()` — module-level patching (one call = all functions logged)
- [x] `auto_log_by_name()` — same but accepts module name strings
- [x] `Logger` — central dispatcher with multiple sinks
- [x] `configure()` — one-liner project setup with sink specs, env overrides
- [x] `configure(force=True)` — re-configuration guard
- [x] Async support: `@log_call`, `@catch`, `@logged` transparently handle `async def`
- [x] Duplicate log fix: `propagate=False` prevents double output
- [x] `_StdlibBridge` — forward stdlib `logging.getLogger()` to nfo sinks

### Sinks
- [x] `SQLiteSink`, `CSVSink`, `MarkdownSink`
- [x] `JSONSink` — structured JSON Lines output for ELK/Grafana Loki
- [x] `PrometheusSink` — export metrics (duration, error rate, call count) to Prometheus
- [x] `WebhookSink` — HTTP POST alerts to Slack/Discord/Teams on ERROR
- [x] `configure()` supports `json:path` and `prometheus:port` sink specs

### Environment & Analysis
- [x] `EnvTagger` — auto-tag logs with environment/trace_id/version
- [x] `DynamicRouter` — route logs by env/level/custom rules
- [x] `DiffTracker` — detect output changes between versions
- [x] `LLMSink` — LLM-powered log analysis via litellm
- [x] `detect_prompt_injection()` — regex prompt injection detection

### DevOps & Multi-language
- [x] Docker Compose demo: FastAPI app + Prometheus + Grafana (pre-built dashboard)
- [x] Grafana dashboard: calls/s, error rate, p95 duration, histogram, top functions
- [x] Load generator: `demo/load_generator.py`
- [x] Root `Dockerfile` + `examples/docker-compose-service.yml` (centralized logging service)
- [x] Kubernetes manifests: Deployment + Service + PVC
- [x] gRPC proto definition (`examples/nfo.proto`)
- [x] HTTP logging service (`examples/http_service.py`) — FastAPI, multi-language endpoint
- [x] Multi-language clients: Bash (`bash_client.sh`), Go (`go_client.go`), Rust (`rust_client.rs`)
- [x] `.env.example` files (root + examples/) with all `NFO_*` variables
- [x] `bump2version` config synced: `pyproject.toml`, `VERSION`, `nfo/__init__.py` bump atomically

### Quality
- [x] 114 tests passing (Python 3.13)
- [x] All Python examples verified and runnable
- [x] README with comparison table (polog, logdecorator, loguru, structlog)
- [x] CHANGELOG.md
- [x] Integration: pactown + pactown-com
- [x] Comprehensive function index (`project.functions.toon`) with 448 functions analyzed
- [x] Project metrics and scale documentation
- [x] Multi-language client verification (Go, Rust, Bash)

## 🔜 Next (v0.3.x)

### Binary Metadata — Phase 2

- [x] `AsyncBufferedSink` — background-thread batched writes with configurable buffer_size, flush_interval, flush_on_error
- [x] `RingBufferSink` — keep last N entries in memory, flush context to delegate on ERROR/CRITICAL; customizable trigger_levels
- [x] `@log_call(sample_rate=0.01)` — sampling for high-throughput functions; errors always logged
- [x] `sample_rate` on `@catch` and `@meta_log` too
- [ ] `@log_call(sample_rate="adaptive")` — automatic rate based on throughput
- [ ] Pipeline context / correlation: `with pipeline_context("name") as ctx:`
- [ ] Prometheus metrics for data sizes: `nfo_data_bytes_total`, `nfo_meta_extractions_total`
- [ ] Dedicated SQLite columns for meta fields (`data_size_bytes`, `data_format`, `data_hash`, `is_meta_log`)
- [ ] Lazy evaluation mode for `@meta_log(lazy=True)` — compute hash/dimensions only when sink needs them
- [ ] CLI extension: `nfo logs --meta --filter "data_format=PNG AND size_bytes > 1000000"`
- [ ] PIL/Pillow image extractor (dimensions, mode, palette)
- [ ] PDF extractor (page count from header)
- [ ] ZIP/archive extractor (file listing)

### New Sinks

- [ ] `OTELSink` — OpenTelemetry spans for distributed tracing (Jaeger/Zipkin via OTLP)
- [ ] `ElasticsearchSink` — direct Elasticsearch indexing for production log aggregation

### Web Dashboard

- [ ] Standalone `nfo-dashboard` CLI: `nfo dashboard --db logs.db`
- [ ] Filter by `trace_id`, `environment`, `level`, `function_name`, date range
- [ ] REST API: `GET /query?env=prod&level=ERROR&last=24h`

### Replay & Testing

- [ ] `replay_logs()` — replay function calls from SQLite logs for regression testing
- [ ] `replay_from_sqlite("logs.db", max_calls=100)` — bounded replay

### Core Improvements

- [ ] Log viewer CLI: `nfo query logs.db --level ERROR --last 24h`
- [ ] Log rotation for file-based sinks (CSV, Markdown, JSON)
- [ ] Sampling: log only N% of calls for high-throughput functions
- [ ] GitHub Actions integration: auto-comment LLM analysis on failed CI builds

### Composable Pipeline (achieved ✅)

```python
# Full monitoring stack (working in v0.2.0)
sink = PrometheusSink(       # metrics → Grafana
    WebhookSink(             # alerts → Slack
        EnvTagger(           # tagging
            SQLiteSink("logs.db")
        ),
        url="https://hooks.slack.com/...",
        levels=["ERROR"],
    ),
    port=9090,
)
```

## 💡 Ideas

- `GraphQLSink` — GraphQL query interface over SQLite logs
- `PineconeSink` / `VectorSink` — semantic log search via embeddings
- LangChain/LlamaIndex integration for semantic log search
- Auto-generate unit tests from logged function calls
- Anomaly detection: flag unusual arg patterns or duration spikes
- Cost tracking for LLM sink (tokens used per analysis)
- Plugin system for custom sinks (register via entry_points)
- RPi/embedded mode: minimal memory footprint, circular buffer sink