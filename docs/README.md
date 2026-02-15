# nfo Documentation

This directory contains comprehensive documentation for the nfo project, generated from the function index analysis.

## Documentation Files

### [Project Analysis](project-analysis.md)
Comprehensive analysis of the nfo project based on function index data:
- Project scale metrics (46 modules, 448 functions)
- Architecture insights and design patterns
- Module distribution and functionality breakdown
- Scalability analysis and recommendations

### [Function Reference](function-reference.md)
Complete API reference for all nfo functions:
- Core decorators (`@log_call`, `@catch`, `@logged`)
- Auto-logging functions (`auto_log`, `auto_log_by_name`)
- Configuration utilities (`configure`)
- All sink types and their parameters
- CLI interface commands
- Data models and utilities

### [Examples Guide](../examples/)
Working examples demonstrating all nfo features:
- Basic usage patterns
- Multi-sink configurations
- Environment-based setup
- Multi-language integration
- DevOps deployment patterns

## Quick Links

- **Installation**: See main [README](../README.md)
- **Quick Start**: `pip install nfo` and add `@log_call` to any function
- **Configuration**: Use `configure()` or environment variables
- **Examples**: Browse the [examples/](../examples/) directory
- **Testing**: Run `pytest tests/` for full test suite

## Project Overview

nfo is a zero-dependency Python logging library that automatically captures:
- Function arguments and types
- Return values and exceptions
- Execution duration
- Environment context
- LLM-powered analysis (optional)

### Key Features

- **Zero boilerplate**: One decorator or one function call
- **Multiple sinks**: SQLite, CSV, Markdown, JSON, Prometheus, Webhooks
- **Auto-logging**: Instrument entire modules with `auto_log()`
- **Multi-language**: Python core with Go, Rust, Bash clients
- **DevOps ready**: Docker Compose, Kubernetes, monitoring stack
- **LLM integration**: AI-powered root cause analysis
- **Production features**: Environment tagging, trace correlation, diff tracking

### Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Decorators    │───▶│     Logger       │───▶│     Sinks       │
│ @log_call       │    │ Central dispatch │    │ SQLite, CSV,    │
│ @catch          │    │ Multiple sinks   │    │ Markdown, JSON  │
│ @logged         │    │ Stdlib bridge    │    │ Prometheus,     │
│ auto_log()      │    │ Thread-safe      │    │ Webhook, LLM    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Getting Started

1. **Install**: `pip install nfo`
2. **Basic use**: Add `@log_call` to any function
3. **Configure**: Use `configure(sinks=["sqlite:logs.db"])`
4. **Advanced**: Chain sinks for full monitoring stack

### Function Index

This documentation is generated from the project's function index (`project.functions.toon`), which analyzes:
- **46 modules** across core, tests, examples, and demo
- **448 functions** with comprehensive metadata
- **114 tests** providing full coverage
- **7 sink types** for different output formats
- **Multi-language support** with HTTP/gRPC clients

For the most up-to-date information, see the main project [README](../README.md) and [CHANGELOG](../CHANGELOG.md).
