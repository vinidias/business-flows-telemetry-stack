# Contributing to business-flows-telemetry-stack

Thank you for your interest in contributing! This project aims to make telemetry accessible to every startup, regardless of budget or infrastructure.

## Ways to Contribute

- **New backend integrations** — Rails, Spring Boot, Go/Gin, NestJS
- **Mobile SDKs** — React Native, native iOS (Swift), native Android (Kotlin)
- **dbt models** — Cohort retention, churn signals, LTV estimation
- **Grafana dashboards** — New templates for different business models (SaaS, marketplace, e-commerce)
- **Documentation** — Tutorials, case studies, translations

## Guidelines

1. Keep dependencies minimal — no extra servers required
2. All secrets via environment variables (`.env.example` always updated)
3. Comment your dbt SQL — this is a learning resource
4. Test your integration before submitting a PR

## Development Setup

```bash
git clone https://github.com/your-org/business-flows-telemetry-stack
cd business-flows-telemetry-stack/pipeline
cp .env.example .env
pip install -r requirements.txt
python pipeline.py
```

## License

By contributing, you agree your code will be published under the MIT License.
