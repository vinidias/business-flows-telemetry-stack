## Description
Briefly describe the purpose of this PR and what problem it addresses.

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🧪 Tests / CI update
- [ ] 🔧 Refactoring / Performance optimization

## Component Affected
- [ ] Pipeline Extractor & DuckDB (`pipeline/extract.py`)
- [ ] Metrics Pusher (`pipeline/push_metrics.py`)
- [ ] Pipeline Orchestrator (`pipeline/pipeline.py`)
- [ ] dbt Models (`pipeline/analytics/models/`)
- [ ] Backend Integrations (`backend/`)
- [ ] Mobile Integrations (`mobile/`)
- [ ] CI/CD & Workflows (`.github/`)

## How Has This Been Tested?
Please describe the tests that you ran to verify your changes:
- [ ] Unit tests passed (`pytest`)
- [ ] Local pipeline test run (`python pipeline/pipeline.py` or synthetic mock dataset)
- [ ] dbt compilation & model tests (`dbt run --profiles-dir . && dbt test --profiles-dir .`)

## Checklist
- [ ] My code follows the style and structure guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented complex or non-obvious code blocks
- [ ] I have updated the documentation where relevant
- [ ] I have added unit tests verifying new functionality or bug fixes
- [ ] All new and existing tests passed locally
