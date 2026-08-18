---
name: Bug Report
about: Create a report to help us improve the business flows telemetry stack
title: '[BUG] '
labels: bug
assignees: ''
---

**Describe the Bug**
A clear and concise description of what the bug is.

**Component / Module**
Which part of the telemetry stack is affected?
- [ ] Pipeline Extractor (`extract.py` / Parquet / DuckDB)
- [ ] dbt Models (`staging`, `intermediate`, `marts`)
- [ ] Metrics Pusher (`push_metrics.py` / Prometheus OpenMetrics)
- [ ] Pipeline Orchestrator (`pipeline.py`)
- [ ] Backend Integrations (Laravel / Django / FastAPI)
- [ ] Mobile Integrations (Flutter SDK)
- [ ] CI/CD Workflows & GitHub Actions
- [ ] Documentation

**To Reproduce**
Steps to reproduce the behavior:
1. Configure `.env` with `...`
2. Run command `...`
3. See error output:
```bash
# Paste error output here
```

**Expected Behavior**
A clear and concise description of what you expected to happen.

**Environment & Setup**
 - OS: [e.g. Ubuntu 22.04, Windows 11, macOS Sonoma]
 - Python Version: [e.g. 3.11, 3.12]
 - DuckDB Version: [e.g. 1.1.0]
 - dbt-core & dbt-duckdb Version: [e.g. 1.9.0]
 - Source Database & Driver: [e.g. MySQL 8.0 with PyMySQL / PostgreSQL 16 with psycopg2]

**Additional Context**
Add any other context, stack traces, or relevant database schema details about the problem here.
