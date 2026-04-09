<!-- code2docs:start --># nfo

![version](https://img.shields.io/badge/version-0.1.0-blue) ![python](https://img.shields.io/badge/python-%3E%3D3.9-blue) ![coverage](https://img.shields.io/badge/coverage-unknown-lightgrey) ![functions](https://img.shields.io/badge/functions-367-green)
> **367** functions | **45** classes | **61** files | CC̄ = 3.3

> Auto-generated project documentation from source code analysis.

**Author:** Tom Sapletta  
**License:** Apache-2.0[(LICENSE)](./LICENSE)  
**Repository:** [https://github.com/wronai/lg](https://github.com/wronai/lg)

## Installation

### From PyPI

```bash
pip install nfo
```

### From Source

```bash
git clone https://github.com/wronai/lg
cd nfo
pip install -e .
```

### Optional Extras

```bash
pip install nfo[llm]    # LLM integration (litellm)
pip install nfo[prometheus]    # prometheus features
pip install nfo[cli]    # cli features
pip install nfo[rich]    # rich features
pip install nfo[dashboard]    # dashboard features
pip install nfo[dev]    # development tools
pip install nfo[grpc]    # grpc features
pip install nfo[all]    # all optional features
```

## Quick Start

### CLI Usage

```bash
# Generate full documentation for your project
nfo ./my-project

# Only regenerate README
nfo ./my-project --readme-only

# Preview what would be generated (no file writes)
nfo ./my-project --dry-run

# Check documentation health
nfo check ./my-project

# Sync — regenerate only changed modules
nfo sync ./my-project
```

### Python API

```python
from nfo import generate_readme, generate_docs, Code2DocsConfig

# Quick: generate README
generate_readme("./my-project")

# Full: generate all documentation
config = Code2DocsConfig(project_name="mylib", verbose=True)
docs = generate_docs("./my-project", config=config)
```

## Generated Output

When you run `nfo`, the following files are produced:

```
<project>/
├── README.md                 # Main project README (auto-generated sections)
├── docs/
│   ├── api.md               # Consolidated API reference
│   ├── modules.md           # Module documentation with metrics
│   ├── architecture.md      # Architecture overview with diagrams
│   ├── dependency-graph.md  # Module dependency graphs
│   ├── coverage.md          # Docstring coverage report
│   ├── getting-started.md   # Getting started guide
│   ├── configuration.md    # Configuration reference
│   └── api-changelog.md    # API change tracking
├── examples/
│   ├── quickstart.py       # Basic usage examples
│   └── advanced_usage.py   # Advanced usage examples
├── CONTRIBUTING.md         # Contribution guidelines
└── mkdocs.yml             # MkDocs site configuration
```

## Configuration

Create `nfo.yaml` in your project root (or run `nfo init`):

```yaml
project:
  name: my-project
  source: ./
  output: ./docs/

readme:
  sections:
    - overview
    - install
    - quickstart
    - api
    - structure
  badges:
    - version
    - python
    - coverage
  sync_markers: true

docs:
  api_reference: true
  module_docs: true
  architecture: true
  changelog: true

examples:
  auto_generate: true
  from_entry_points: true

sync:
  strategy: markers    # markers | full | git-diff
  watch: false
  ignore:
    - "tests/"
    - "__pycache__"
```

## Sync Markers

nfo can update only specific sections of an existing README using HTML comment markers:

```markdown
<!-- nfo:start -->
# Project Title
... auto-generated content ...
<!-- nfo:end -->
```

Content outside the markers is preserved when regenerating. Enable this with `sync_markers: true` in your configuration.

## Architecture

```
nfo/
├── project        ├── main    ├── load_generator        ├── main        ├── main        ├── main        ├── main        ├── main        ├── main        ├── main        ├── main        ├── server        ├── client        ├── nfo_pb2_grpc        ├── nfo_pb2        ├── main        ├── main        ├── main        ├── demo_basic        ├── demo_configure        ├── demo_formats        ├── main    ├── sync_pactown_com_dependency    ├── app    ├── llm    ├── auto        ├── main    ├── analytics    ├── extractors    ├── webhook    ├── buffered_sink    ├── redact├── nfo/    ├── ring_buffer_sink    ├── metrics    ├── setup    ├── configure    ├── fastapi_middleware    ├── meta    ├── binary_router    ├── log_flow    ├── context    ├── pipeline_sink    ├── terminal    ├── env    ├── models    ├── meta_decorators    ├── prometheus    ├── logged    ├── json_sink    ├── logger    ├── sinks        ├── _decision        ├── _core    ├── decorators/        ├── _extract        ├── _log_call        ├── _catch    ├── click        ├── main    ├── __main__```

## API Overview

### Classes

- **`LogEntry`** — —
- **`NfoClient`** — —
- **`LogEntry`** — —
- **`LogResponse`** — —
- **`NfoClient`** — —
- **`NfoLoggerServicer`** — Implementation of NfoLogger gRPC service.
- **`NfoLoggerStub`** — --- Service ---
- **`NfoLoggerServicer`** — --- Service ---
- **`NfoLogger`** — --- Service ---
- **`PaymentService`** — —
- **`UserService`** — —
- **`LLMSink`** — Sink that sends ERROR-level log entries to an LLM for root-cause analysis.
- **`InventoryService`** — —
- **`LogStats`** — Statistics for a single function/metric.
- **`LogAnalytics`** — Analytics engine for nfo SQLite logs.
- **`WebhookSink`** — Sink that POSTs log entries to an HTTP webhook endpoint.
- **`AsyncBufferedSink`** — Buffer log entries and write them batch-wise in a background thread.
- **`RingBufferSink`** — In-memory ring buffer that flushes context to *delegate* on error.
- **`MetricValue`** — Single metric value with timestamp.
- **`Counter`** — Monotonically increasing counter metric.
- **`Gauge`** — Gauge metric for values that can go up or down.
- **`Histogram`** — Histogram metric for latency/distribution tracking.
- **`MetricsCollector`** — Central metrics collector for registering and collecting all metrics.
- **`FastAPIMiddleware`** — ASGI middleware that emits one nfo LogEntry per HTTP request.
- **`ThresholdPolicy`** — Policy deciding when to log full data vs extracted metadata.
- **`BinaryAwareRouter`** — Route log entries to different sinks based on payload characteristics.
- **`LogFlowParser`** — Parse logs, group by trace_id, and build compressed flow graphs.
- **`PipelineSink`** — Sink that groups log entries by ``pipeline_run_id`` and renders pipeline ticks.
- **`TerminalSink`** — Sink that displays log entries in the terminal with configurable format.
- **`EnvTagger`** — Sink wrapper that auto-tags every log entry with:
- **`DynamicRouter`** — Routes log entries to different sinks based on rules.
- **`DiffTracker`** — Tracks input/output changes between function calls across versions.
- **`LogEntry`** — A single log entry produced by a decorated function call.
- **`PrometheusSink`** — Sink that exports nfo log entries as Prometheus metrics.
- **`JSONSink`** — Append log entries as JSON Lines (one JSON object per line).
- **`Logger`** — Central logger instance.
- **`Sink`** — Base class for all sinks.
- **`SQLiteSink`** — Persist log entries to a SQLite database.
- **`CSVSink`** — Append log entries to a CSV file.
- **`MarkdownSink`** — Append log entries to a Markdown file as structured sections.
- **`NfoGroup`** — Click Group that automatically logs every command invocation via nfo.
- **`NfoCommand`** — Click Command that logs its own invocation via nfo.
- **`LogEntry`** — —
- **`LogBatchRequest`** — —

### Functions

- `create_user(name, email)` — Create a new user.
- `delete_user(user_id)` — Delete user by ID.
- `calculate_total(prices)` — Sum a list of prices.
- `health_check()` — Excluded from auto_log — called frequently, not interesting.
- `weighted_choice(endpoints)` — —
- `main()` — —
- `setup_logger()` — —
- `run_bash(script_path)` — Run a Bash script and capture its output through nfo logging.
- `main()` — —
- `NewNfoClient()` — —
- `Log()` — —
- `LogCall()` — —
- `getEnv()` — —
- `main()` — —
- `setup_logger()` — —
- `fetch_user(user_id)` — —
- `parse_config(raw)` — Parse config string. Returns empty dict on failure.
- `add(a, b)` — Add two numbers.
- `greet(name)` — —
- `risky_divide(a, b)` — Divides a by b. Returns None on error instead of raising.
- `setup_logger()` — —
- `compute(x, y)` — —
- `dangerous(data)` — —
- `nfo_log()` — —
- `nfo_run()` — —
- `nfo_query()` — —
- `setup_logger()` — —
- `multiply(a, b)` — —
- `process_items(items)` — Process items and return count.
- `serve(port, max_workers)` — Start the gRPC server.
- `run_demo(target)` — Run all four gRPC RPCs against nfo server.
- `add_NfoLoggerServicer_to_server(servicer, server)` — —
- `setup_logger()` — —
- `fibonacci(n)` — —
- `batch_process(items)` — —
- `parse_int(value)` — —
- `demo_env_tagger()` — EnvTagger wraps a sink to auto-tag every log entry.
- `demo_dynamic_router()` — DynamicRouter sends logs to different sinks based on rules.
- `demo_diff_tracker()` — DiffTracker detects when function output changes.
- `process_order(order_id, amount)` — —
- `parse_config(raw)` — —
- `cli()` — Demo CLI with automatic nfo logging.
- `greet(name)` — Greet someone.
- `process(count)` — Run a processing loop.
- `deploy(path, force)` — Deploy to a target path.
- `fail()` — Command that fails (demonstrates error logging).
- `cli()` — Demo CLI using nfo.configure() with terminal sink.
- `deploy(target, force)` — Deploy to target.
- `migrate(db_path)` — Run database migration.
- `make_entry(function_name, args, kwargs, return_value)` — —
- `demo()` — —
- `setup_logger()` — —
- `fetch_data(url)` — Simulate an async HTTP fetch.
- `process_batch(items)` — Process items concurrently.
- `risky_fetch(url)` — Fetch that may fail — returns {} on error instead of raising.
- `main()` — —
- `compute_fibonacci(n)` — Compute fibonacci number (intentionally slow for large n).
- `process_order(order_id, amount)` — Simulate order processing.
- `risky_division(a, b)` — Division that may fail.
- `slow_operation(duration)` — Simulate a slow operation.
- `health()` — —
- `demo_success()` — Run several successful decorated function calls.
- `demo_error()` — Trigger error-level log entries.
- `demo_slow()` — Trigger a slow operation to demonstrate duration histograms.
- `demo_batch()` — Run a batch of mixed calls (success + errors) for load simulation.
- `metrics()` — Expose Prometheus metrics (alternative to prom_sink auto-server).
- `browse_logs(level, limit)` — Browse latest logs from SQLite.
- `detect_prompt_injection(text)` — Scan text for common prompt injection patterns.
- `scan_entry_for_injection(entry)` — Scan a LogEntry's args/kwargs for prompt injection attempts.
- `auto_log()` — Automatically wrap all functions in one or more modules with logging.
- `auto_log_by_name()` — Like auto_log() but accepts module name strings instead of module objects.
- `create_order(order_id, amount)` — —
- `parse_payload(raw)` — —
- `create_analytics(db_path)` — Factory function to create LogAnalytics instance.
- `detect_format(data)` — Detect file format from magic bytes.
- `extract_image_meta(data)` — Extract metadata from an image without external dependencies.
- `extract_binary_meta(data)` — General metadata for arbitrary binary data.
- `extract_file_meta(file_obj)` — Metadata from a file-like object (without reading its contents).
- `extract_numpy_meta(arr)` — Metadata from a numpy ndarray (duck-typed).
- `extract_dataframe_meta(df)` — Metadata from a pandas DataFrame (duck-typed).
- `extract_wav_meta(data)` — Extract metadata from WAV file header.
- `register_extractor(type_check, extractor)` — Register a custom metadata extractor.
- `unregister_all_extractors()` — Remove all custom extractors (useful in tests).
- `extract_meta(value)` — Auto-detect value type and extract metadata.
- `is_sensitive_key(key)` — Check if a key/parameter name likely holds a secret value.
- `redact_value(value, visible_chars)` — Replace a sensitive value with a redacted placeholder.
- `redact_kwargs(kwargs)` — Return a copy of kwargs with sensitive values redacted.
- `redact_args(args, param_names)` — Redact positional args if their parameter names are sensitive.
- `redact_string(text)` — Scan a string for common secret patterns and redact inline values.
- `get_logger(name)` — Return a stdlib logger bridged to nfo sinks via configure().
- `debug(message)` — Log a DEBUG-level event directly to nfo sinks.
- `info(message)` — Log an INFO-level event directly to nfo sinks.
- `warning(message)` — Log a WARNING-level event directly to nfo sinks.
- `error(message)` — Log an ERROR-level event directly to nfo sinks.
- `event(name)` — Log a named business event at INFO level with structured kwargs.
- `get_global_meta_policy()` — Return the globally configured :class:`~nfo.meta.ThresholdPolicy` (if any).
- `get_global_auto_extract_meta()` — Return ``True`` if ``auto_extract_meta`` was enabled via :func:`configure`.
- `configure()` — Configure nfo logging for the entire project.
- `get_config()` — Return current configuration state.
- `sizeof(obj)` — Best-effort size of *obj* in bytes.
- `build_log_flow_graph(entries_or_grouped)` — Convenience wrapper for building a flow graph without manual parser setup.
- `compress_logs_for_llm(entries_or_graph)` — Convenience wrapper for LLM-ready compression output.
- `get_current_context()` — Get merged context from all active context managers.
- `log_context()` — Temporarily add metadata context to all log entries.
- `temp_level(level)` — Temporarily change the log level for the current logger.
- `temp_sink(sink_spec)` — Temporarily add a sink for the duration of the context.
- `silence()` — Temporarily silence all logging within this context.
- `temp_config()` — Temporarily reconfigure nfo with new settings.
- `span(name)` — Create a tracing span for a block of code.
- `with_context()` — Decorator to add context to a function.
- `generate_trace_id()` — Generate a new trace ID.
- `safe_repr(value, max_length)` — Best-effort repr with defensive truncation.
- `meta_log(func)` — Decorator that logs metadata instead of raw binary data.
- `skip(func)` — Mark a public method to be excluded from @logged auto-wrapping.
- `logged(cls)` — Class decorator that auto-wraps all public methods with @log_call.
- `decision_log(func)` — Decorator that logs decision outcomes with structured reasons.
- `set_default_logger(logger)` — Replace the module-level default logger used by decorators.
- `log_call(func)` — Decorator that automatically logs function calls.
- `catch(func)` — Decorator that logs calls **and** suppresses exceptions.
- `nfo_options(func)` — Decorator that adds common nfo CLI options to a Click command/group.
- `log_call(entry)` — Log a single call from any language.
- `log_batch(batch)` — Log multiple entries at once.
- `get_logs(language, level, limit)` — Query stored logs from SQLite.
- `health()` — —
- `cmd_run(args)` — Run a command and log it through nfo.
- `cmd_logs(args)` — Query nfo logs from SQLite database.
- `cmd_version(args)` — Print nfo version.
- `cmd_serve(args)` — Start nfo HTTP logging service.
- `main()` — —


## Project Structure

📄 `demo.app` (13 functions, 1 classes)
📄 `demo.load_generator` (2 functions)
📄 `examples.async-usage.main` (5 functions)
📄 `examples.auto-log.main` (5 functions)
📄 `examples.bash-client.main` (3 functions)
📄 `examples.bash-wrapper.main` (3 functions)
📄 `examples.basic-usage.main` (3 functions)
📄 `examples.click-integration.demo_basic` (5 functions)
📄 `examples.click-integration.demo_configure` (3 functions)
📄 `examples.click-integration.demo_formats` (2 functions)
📄 `examples.configure.main` (4 functions, 1 classes)
📄 `examples.csv-sink.main` (3 functions)
📄 `examples.env-config.main` (4 functions, 1 classes)
📄 `examples.env-tagger.main` (3 functions)
📄 `examples.go-client.main` (5 functions, 2 classes)
📄 `examples.grpc-service.client` (1 functions)
📄 `examples.grpc-service.nfo_pb2`
📄 `examples.grpc-service.nfo_pb2_grpc` (10 functions, 3 classes)
📄 `examples.grpc-service.server` (6 functions, 1 classes)
📄 `examples.http-service.main` (5 functions, 2 classes)
📄 `examples.markdown-sink.main` (3 functions)
📄 `examples.multi-sink.main` (4 functions)
📄 `examples.rust-client.main` (1 functions, 3 classes)
📄 `examples.sqlite-sink.main` (3 functions)
📦 `nfo` (9 functions)
📄 `nfo.__main__` (14 functions)
📄 `nfo.analytics` (9 functions, 2 classes)
📄 `nfo.auto` (3 functions)
📄 `nfo.binary_router` (4 functions, 1 classes)
📄 `nfo.buffered_sink` (6 functions, 1 classes)
📄 `nfo.click` (5 functions, 2 classes)
📄 `nfo.configure` (12 functions, 1 classes)
📄 `nfo.context` (8 functions)
📦 `nfo.decorators`
📄 `nfo.decorators._catch` (3 functions)
📄 `nfo.decorators._core` (5 functions)
📄 `nfo.decorators._decision` (2 functions)
📄 `nfo.decorators._extract` (6 functions)
📄 `nfo.decorators._log_call` (3 functions)
📄 `nfo.env` (14 functions, 3 classes)
📄 `nfo.extractors` (15 functions)
📄 `nfo.fastapi_middleware` (3 functions, 1 classes)
📄 `nfo.json_sink` (3 functions, 1 classes)
📄 `nfo.llm` (8 functions, 1 classes)
📄 `nfo.log_flow` (33 functions, 1 classes)
📄 `nfo.logged` (5 functions)
📄 `nfo.logger` (7 functions, 1 classes)
📄 `nfo.meta` (3 functions, 1 classes)
📄 `nfo.meta_decorators` (5 functions)
📄 `nfo.metrics` (23 functions, 5 classes)
📄 `nfo.models` (8 functions, 1 classes)
📄 `nfo.pipeline_sink` (16 functions, 1 classes)
📄 `nfo.prometheus` (5 functions, 1 classes)
📄 `nfo.redact` (5 functions)
📄 `nfo.ring_buffer_sink` (3 functions, 1 classes)
📄 `nfo.setup`
📄 `nfo.sinks` (15 functions, 4 classes)
📄 `nfo.terminal` (12 functions, 1 classes)
📄 `nfo.webhook` (5 functions, 1 classes)
📄 `project`
📄 `tools.sync_pactown_com_dependency`

## Requirements

- Python >= >=3.9


## Contributing

**Contributors:**
- Tom Softreck <tom@sapletta.com>
- Tom Sapletta <tom@sapletta.com>
- Tom Sapletta <tom-sapletta-com@users.noreply.github.com>

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/wronai/lg
cd nfo

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest
```

## Documentation

- 📖 [Full Documentation](https://github.com/wronai/lg/tree/main/docs) — API reference, module docs, architecture
- 🚀 [Getting Started](https://github.com/wronai/lg/blob/main/docs/getting-started.md) — Quick start guide
- 📚 [API Reference](https://github.com/wronai/lg/blob/main/docs/api.md) — Complete API documentation
- 🔧 [Configuration](https://github.com/wronai/lg/blob/main/docs/configuration.md) — Configuration options
- 💡 [Examples](./examples) — Usage examples and code samples

### Generated Files

| Output | Description | Link |
|--------|-------------|------|
| `README.md` | Project overview (this file) | — |
| `docs/api.md` | Consolidated API reference | [View](./docs/api.md) |
| `docs/modules.md` | Module reference with metrics | [View](./docs/modules.md) |
| `docs/architecture.md` | Architecture with diagrams | [View](./docs/architecture.md) |
| `docs/dependency-graph.md` | Dependency graphs | [View](./docs/dependency-graph.md) |
| `docs/coverage.md` | Docstring coverage report | [View](./docs/coverage.md) |
| `docs/getting-started.md` | Getting started guide | [View](./docs/getting-started.md) |
| `docs/configuration.md` | Configuration reference | [View](./docs/configuration.md) |
| `docs/api-changelog.md` | API change tracking | [View](./docs/api-changelog.md) |
| `CONTRIBUTING.md` | Contribution guidelines | [View](./CONTRIBUTING.md) |
| `examples/` | Usage examples | [Browse](./examples) |
| `mkdocs.yml` | MkDocs configuration | — |

<!-- code2docs:end -->