"""
Unit tests for pipeline/push_metrics.py.
Tests Prometheus / OpenMetrics payload formatting, DuckDB metric extraction, and HTTP pusher.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

try:
    from push_metrics import (
        format_prometheus_payload,
        collect_metrics_from_duckdb,
        push_to_grafana,
    )
except ImportError:
    from pipeline.push_metrics import (
        format_prometheus_payload,
        collect_metrics_from_duckdb,
        push_to_grafana,
    )


class TestFormatPrometheusPayload:
    """Tests for OpenMetrics / Prometheus exposition text generation."""

    def test_empty_metrics_list(self):
        """Empty metrics list should return an empty payload string."""
        payload = format_prometheus_payload([])
        assert payload.strip() == ""

    def test_single_metric_without_labels(self):
        """Test formatting a single metric without label dictionary."""
        metrics = [("business_users_dau", {}, 42.0)]
        payload = format_prometheus_payload(metrics)

        lines = [line for line in payload.split("\n") if line]
        assert "# HELP business_users_dau Business flow telemetry metric" in lines
        assert "# TYPE business_users_dau gauge" in lines

        data_line = [l for l in lines if l.startswith("business_users_dau ")][0]
        parts = data_line.split()
        assert parts[0] == "business_users_dau"
        assert float(parts[1]) == 42.0
        assert parts[2].isdigit()  # timestamp in ms

    def test_single_metric_with_labels(self):
        """Test formatting metric with multiple labels (alphabetically sorted)."""
        metrics = [
            (
                "business_revenue_daily_amount",
                {"currency": "BRL", "payment_method": "pix", "source": "business_pipeline"},
                1250.75,
            )
        ]
        payload = format_prometheus_payload(metrics)

        assert '# HELP business_revenue_daily_amount Business flow telemetry metric' in payload
        assert '# TYPE business_revenue_daily_amount gauge' in payload
        assert 'business_revenue_daily_amount{currency="BRL",payment_method="pix",source="business_pipeline"} 1250.75' in payload

    def test_header_deduplication_for_same_metric(self):
        """HELP and TYPE headers should be printed once per metric name."""
        metrics = [
            ("business_platform_active_users", {"platform": "ios"}, 100.0),
            ("business_platform_active_users", {"platform": "android"}, 150.0),
            ("business_platform_active_users", {"platform": "web"}, 80.0),
        ]
        payload = format_prometheus_payload(metrics)

        help_count = payload.count("# HELP business_platform_active_users")
        type_count = payload.count("# TYPE business_platform_active_users")
        assert help_count == 1
        assert type_count == 1
        assert 'platform="ios"' in payload
        assert 'platform="android"' in payload
        assert 'platform="web"' in payload

    def test_multiple_distinct_metrics(self):
        """Test formatting a full realistic batch of business telemetry metrics."""
        metrics = [
            ("business_users_dau", {"source": "business_pipeline"}, 500.0),
            ("business_revenue_daily_amount", {"currency": "BRL"}, 9900.0),
            ("business_funnel_step_conversion_ratio", {"step_name": "checkout"}, 0.45),
        ]
        payload = format_prometheus_payload(metrics)

        assert "# HELP business_users_dau" in payload
        assert "# HELP business_revenue_daily_amount" in payload
        assert "# HELP business_funnel_step_conversion_ratio" in payload
        assert "business_users_dau{source=\"business_pipeline\"} 500.0" in payload
        assert payload.endswith("\n")


class TestCollectMetricsFromDuckDB:
    """Tests for querying dbt marts in DuckDB."""

    def test_nonexistent_duckdb_returns_empty(self, tmp_path):
        """Missing DuckDB database should return empty metric list."""
        missing_db = tmp_path / "non_existent.duckdb"
        metrics = collect_metrics_from_duckdb(missing_db)
        assert metrics == []

    def test_collects_from_all_marts(self, tmp_path):
        """Verify metric collection from mart tables."""
        duckdb_path = tmp_path / "analytics.duckdb"
        con = duckdb.connect(str(duckdb_path))

        try:
            # 1. mart_user_growth
            con.execute("""
                CREATE TABLE mart_user_growth (
                    metric_date DATE,
                    dau_count BIGINT,
                    wau_count BIGINT,
                    mau_count BIGINT,
                    new_registrations_count BIGINT,
                    cumulative_total_users BIGINT
                );
            """)
            con.execute("INSERT INTO mart_user_growth VALUES ('2026-08-18', 45, 120, 300, 10, 500);")

            # 2. mart_revenue
            con.execute("""
                CREATE TABLE mart_revenue (
                    metric_date DATE,
                    currency VARCHAR,
                    payment_method VARCHAR,
                    daily_gross_revenue DOUBLE,
                    daily_successful_transactions BIGINT,
                    daily_average_order_value DOUBLE,
                    cumulative_total_revenue DOUBLE
                );
            """)
            con.execute("INSERT INTO mart_revenue VALUES ('2026-08-18', 'BRL', 'pix', 1500.0, 15, 100.0, 15000.0);")

            # 3. mart_event_funnel
            con.execute("""
                CREATE TABLE mart_event_funnel (
                    funnel_step_order INT,
                    step_name VARCHAR,
                    event_name VARCHAR,
                    total_events BIGINT,
                    unique_users_count BIGINT,
                    step_conversion_rate DOUBLE,
                    overall_conversion_rate DOUBLE
                );
            """)
            con.execute("INSERT INTO mart_event_funnel VALUES (1, 'Signup', 'signup_completed', 50, 40, 1.0, 1.0);")

            # 4. mart_platform_split
            con.execute("""
                CREATE TABLE mart_platform_split (
                    metric_date DATE,
                    platform VARCHAR,
                    active_users_count BIGINT,
                    events_count BIGINT,
                    revenue_amount DOUBLE
                );
            """)
            con.execute("INSERT INTO mart_platform_split VALUES ('2026-08-18', 'ios', 30, 200, 800.0);")
        finally:
            con.close()

        metrics = collect_metrics_from_duckdb(duckdb_path)
        metric_names = [m[0] for m in metrics]

        assert "business_users_dau" in metric_names
        assert "business_users_mau" in metric_names
        assert "business_revenue_daily_amount" in metric_names
        assert "business_funnel_step_events_total" in metric_names
        assert "business_platform_active_users" in metric_names

        # Verify values
        dau_metric = [m for m in metrics if m[0] == "business_users_dau"][0]
        assert dau_metric[2] == 45.0


class TestPushToGrafana:
    """Tests for Grafana Cloud HTTP pusher."""

    def test_dry_run_mode_without_credentials(self, monkeypatch):
        """Should skip push and return True in dry-run mode."""
        monkeypatch.delenv("GRAFANA_PROMETHEUS_URL", raising=False)
        monkeypatch.delenv("GRAFANA_API_KEY", raising=False)

        payload = "# HELP test metric\ntest 1.0 123456\n"
        success = push_to_grafana(payload)
        assert success is True

    @patch("requests.post")
    def test_successful_http_push(self, mock_post, monkeypatch):
        """Should return True when Grafana responds with 200 OK."""
        monkeypatch.setenv("GRAFANA_PROMETHEUS_URL", "https://prometheus-prod.grafana.net/api/v1/push")
        monkeypatch.setenv("GRAFANA_INSTANCE_ID", "12345")
        monkeypatch.setenv("GRAFANA_API_KEY", "glc_valid_api_key_mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        payload = "# HELP test metric\ntest 1.0 123456\n"
        success = push_to_grafana(payload)

        assert success is True
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_failed_http_push(self, mock_post, monkeypatch):
        """Should return False when Grafana responds with HTTP 401 Unauthorized."""
        monkeypatch.setenv("GRAFANA_PROMETHEUS_URL", "https://prometheus-prod.grafana.net/api/v1/push")
        monkeypatch.setenv("GRAFANA_INSTANCE_ID", "12345")
        monkeypatch.setenv("GRAFANA_API_KEY", "glc_invalid_key")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_post.return_value = mock_resp

        payload = "# HELP test metric\ntest 1.0 123456\n"
        success = push_to_grafana(payload)

        assert success is False
