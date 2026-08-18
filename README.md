# business-flows-telemetry-stack

> **Zero-infrastructure telemetry ecosystem for startups.**  
> Track your product, understand your users, and visualize business flows — for **$0/month**.

[![Daily Pipeline](https://github.com/your-org/business-flows-telemetry-stack/actions/workflows/daily-pipeline.yml/badge.svg)](https://github.com/your-org/business-flows-telemetry-stack/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![dbt](https://img.shields.io/badge/dbt-duckdb-orange)](https://docs.getdbt.com)
[![Grafana](https://img.shields.io/badge/Grafana-Cloud%20Free-yellow)](https://grafana.com/grafana/cloud)

---

## The Problem

Most telemetry solutions assume you have:
- A dedicated data server
- A DevOps team
- $500+/month to spend on cloud data services

**Startups don't have any of that.**

---

## The Solution

A lightweight, battle-tested telemetry stack built around what you *already have*:

```
Your existing backend  →  analytics_events table  →  Lightweight API endpoint
        ↓
Your developer's laptop  →  DuckDB + dbt  →  Business metrics
        ↓
GitHub Actions (free)  →  Runs daily, no server needed
        ↓
Grafana Cloud (free tier)  →  Beautiful dashboards
```

**Real cost: $0/month.**

---

## What You Get

### 📊 Business Flow Dashboards (Grafana Cloud)
- **User Growth** — DAU, WAU, MAU by platform (iOS/Android/Web)
- **Event Funnel** — Any custom flow: signup → first action → conversion
- **Revenue** — Gross revenue, ticket average, payment methods
- **Platform Split** — Where your users actually come from

### 🔧 Backend Integrations
- **Laravel** (PHP) — Drop-in Model + Controller + Migration
- **Django** (Python) — Django ORM model + DRF view
- **FastAPI** (Python) — Async endpoint, Pydantic models

### 📱 Mobile SDK
- **Flutter** — Plug-and-play `AnalyticsService` with auto platform detection, local queue and retry

### ⚙️ Data Pipeline
- **Extract** — Pulls data from MySQL or PostgreSQL to local Parquet files
- **Transform** — dbt models: staging → intermediate → marts
- **Load** — Pushes aggregated metrics to Grafana Cloud via Prometheus remote write
- **Orchestrate** — GitHub Actions runs it daily for free

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR EXISTING STACK                           │
│                                                                   │
│  Mobile App (Flutter)          Web / Backend                     │
│  └─ AnalyticsService.dart      └─ POST /api/analytics/event     │
│       │                              │                            │
│       ▼                              ▼                            │
│  Firebase Analytics          analytics_events (MySQL/Postgres)   │
│       │                              │                            │
└───────┼──────────────────────────────┼───────────────────────────┘
        │                              │
        ▼                              ▼
  BigQuery Export               Python extract.py
  (Firebase → GCP)              (reads DB → Parquet)
        │                              │
        └──────────────┬───────────────┘
                        ▼
               DuckDB + dbt (local / GitHub Actions)
               ├── stg_users
               ├── stg_events
               ├── int_user_journey
               └── marts/
                   ├── mart_user_growth
                   ├── mart_event_funnel
                   ├── mart_revenue
                   └── mart_platform_split
                        │
                        ▼
              push_metrics.py
              (Prometheus Remote Write)
                        │
                        ▼
            ┌───────────────────┐
            │   GRAFANA CLOUD   │  ← Free Tier (10k metrics/month)
            │   Free Tier       │
            │  ┌─────────────┐  │
            │  │  Dashboards │  │
            │  └─────────────┘  │
            └───────────────────┘
```

---

## Cost Breakdown

| Component | Service | Monthly Cost |
|-----------|---------|-------------|
| Event storage | Existing database | $0 |
| Data processing | Developer's machine / GitHub Actions | $0 |
| Mobile analytics | Firebase Analytics | $0 |
| BigQuery export | Google Cloud Free Tier | $0 |
| Dashboards | Grafana Cloud Free Tier | $0 |
| Pipeline orchestration | GitHub Actions (2,000 min/month free) | $0 |
| **Total** | | **$0/month** |

> Scales to production with Firebase at ~$0 for up to 10M events/month.

---

## Quick Start

### 1. Add analytics_events to your backend

Pick your framework:
- [Laravel →](backend/laravel/)
- [Django →](backend/django/)
- [FastAPI →](backend/fastapi/)

### 2. Instrument your mobile app

```dart
// pubspec.yaml
dependencies:
  http: ^1.2.0

// main.dart
final analytics = AnalyticsService(
  baseUrl: 'https://your-api.com',
  userId: currentUser.id,
);

analytics.trackScreen('HomeScreen');
analytics.trackEvent('booking_created', properties: {'service_id': 42});
analytics.trackConversion('first_purchase', value: 150.0);
```

Full Flutter SDK: [mobile/flutter/](mobile/flutter/)

### 3. Set up the pipeline

```bash
git clone https://github.com/your-org/business-flows-telemetry-stack
cd business-flows-telemetry-stack/pipeline

cp .env.example .env
# Edit .env with your database credentials

pip install -r requirements.txt
python pipeline.py
```

### 4. Connect Grafana Cloud

1. Create free account at [grafana.com/grafana/cloud](https://grafana.com/grafana/cloud)
2. Get your Prometheus push URL and API key
3. Add to `.env` and run `python push_metrics.py`
4. Import dashboards from `grafana/dashboards/`

### 5. Automate with GitHub Actions

```bash
# Add secrets to your GitHub repository:
# DB_HOST, DB_NAME, DB_USER, DB_PASS
# GRAFANA_PROMETHEUS_URL, GRAFANA_INSTANCE_ID, GRAFANA_API_KEY
```

The pipeline runs daily at 06:00 BRT automatically. ✅

---

## Real-World Usage

This stack was developed and battle-tested at **[Propaga](https://propagatec.com.br)** — an AgTech startup connecting rural producers with specialized consultants in Brazil.

- **Stack**: Laravel 11 + Flutter (iOS + Android) + MySQL on shared hosting
- **Users**: Producers, consultants, technicians across Brazil
- **Challenge**: No DevOps, no dedicated server, budget-constrained

After implementing `business-flows-telemetry-stack`, the team gained:
- Real-time visibility into user registration flows
- Conversion funnel from signup → first booking → payment
- Platform split (iOS vs Android vs Web registrations)
- Zero additional infrastructure cost

---

## Project Structure

```
business-flows-telemetry-stack/
├── backend/
│   ├── laravel/           # PHP/Laravel integration
│   ├── django/            # Python/Django integration
│   └── fastapi/           # Python/FastAPI integration
├── mobile/
│   └── flutter/           # Flutter analytics SDK
├── pipeline/
│   ├── extract.py         # Database → Parquet
│   ├── push_metrics.py    # DuckDB → Grafana Cloud
│   ├── pipeline.py        # Orchestrator
│   ├── requirements.txt
│   └── analytics/         # dbt project
│       └── models/
│           ├── staging/
│           ├── intermediate/
│           └── marts/
├── grafana/
│   └── dashboards/        # Importable Grafana JSON dashboards
├── docs/
│   ├── architecture.md
│   ├── cost-breakdown.md
│   └── getting-started.md
└── .github/
    └── workflows/
        └── daily-pipeline.yml
```

---

## Contributing

This project is open to contributions for:
- New backend framework integrations (Rails, Spring Boot, Go/Gin)
- Additional dbt models (cohort analysis, churn prediction features)
- Grafana dashboard templates
- React Native / native iOS / native Android SDKs

See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

---

## License

MIT — use freely in commercial and open source projects.

---

*Built with ❤️ by the Propaga team. If this helped your startup, give it a ⭐*
