# nfo — TODO / Roadmap

## ✅ Done (v0.1.19)

- [x] Core: `@log_call`, `@catch` decorators
- [x] Sinks: `SQLiteSink`, `CSVSink`, `MarkdownSink`
- [x] `Logger` — central dispatcher with multiple sinks
- [x] `configure()` — one-liner project setup with sink specs, env overrides
- [x] `configure(force=True)` — re-configuration guard (returns cached logger unless forced)
- [x] `@logged` — class decorator (auto-wrap all public methods)
- [x] `@skip` — exclude methods from `@logged`
- [x] `auto_log()` — module-level patching (one call = all functions logged)
- [x] `auto_log_by_name()` — same as `auto_log()` but accepts module name strings
- [x] `_StdlibBridge` — forward stdlib `logging.getLogger()` to nfo sinks
- [x] `LLMSink` — LLM-powered log analysis via litellm
- [x] `detect_prompt_injection()` — regex prompt injection detection
- [x] `EnvTagger` — auto-tag logs with environment/trace_id/version
- [x] `DynamicRouter` — route logs by env/level/custom rules
- [x] `DiffTracker` — detect output changes between versions
- [x] Async support: `@log_call`, `@catch`, `@logged` transparently handle `async def`
- [x] Duplicate log fix: `propagate=False` prevents double output
- [x] Integration: pactown (`nfo_config.py` + cli.py + runner_api.py)
- [x] Integration: pactown-com (`nfo_config.py` + main.py)
- [x] 87 tests passing
- [x] README with comparison table, integration guide, LLM features
- [x] CHANGELOG.md

## 🔜 Next (v0.2.x)

### New Sinks

- [ ] `PrometheusSink` — export metrics (duration, error rate, call count) to Prometheus; optional dep `prometheus_client`; auto `/metrics` endpoint
- [ ] `WebhookSink` — HTTP POST alerts to Slack/Discord/Teams on ERROR; configurable URL + payload template
- [ ] `OTELSink` — OpenTelemetry spans for distributed tracing; export to Jaeger/Zipkin via OTLP; optional dep `opentelemetry-sdk`
- [ ] `JSONSink` — structured JSON output for ELK/Grafana Loki
- [ ] `ElasticsearchSink` — direct Elasticsearch indexing for production log aggregation

### Web Dashboard

- [ ] Lightweight Flask/FastAPI server for browsing SQLite logs
- [ ] Filter by `trace_id`, `environment`, `level`, `function_name`, date range
- [ ] Endpoint: `GET /query?env=prod&level=ERROR&last=24h`
- [ ] Optional dep: `pip install nfo[dashboard]`

### Replay & Testing

- [ ] `replay_logs()` — replay function calls from SQLite logs for regression testing
- [ ] `replay_from_sqlite("logs.db", max_calls=100)` — bounded replay with assertions

### Core Improvements

- [ ] Log viewer CLI: `nfo query logs.db --level ERROR --last 24h`
- [ ] Log rotation for file-based sinks (CSV, Markdown)
- [ ] Sampling: log only N% of calls for high-throughput functions
- [ ] GitHub Actions integration: auto-comment LLM analysis on failed CI builds

### Composable Pipeline (target)

```python
# Full monitoring stack
sink = PrometheusSink(       # metrics → Grafana
    WebhookSink(             # alerts → Slack
        OTELSink(            # tracing → Jaeger
            EnvTagger(       # tagging
                SQLiteSink("logs.db")
            )
        ),
        url="https://hooks.slack.com/...",
        levels=["ERROR"],
    ),
    port=9090,
)
```

## 💡 Ideas

- `GraphQLSink` — GraphQL query interface over SQLite logs (`{ errors(env: "prod") { func duration } }`)
- `PineconeSink` / `VectorSink` — semantic log search via embeddings
- LangChain/LlamaIndex integration for semantic log search
- Auto-generate unit tests from logged function calls
- Anomaly detection: flag unusual arg patterns or duration spikes
- Cost tracking for LLM sink (tokens used per analysis)
- Plugin system for custom sinks (register via entry_points)
- RPi/embedded mode: minimal memory footprint, circular buffer sink