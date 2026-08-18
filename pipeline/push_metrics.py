"""
==============================================================================
Business Flows Telemetry Stack - Grafana Cloud Metrics Pusher
==============================================================================
Reads aggregated business metrics from DuckDB marts and pushes them to
Grafana Cloud Prometheus / Mimir via HTTP OpenMetrics push endpoint.

Usage:
    python push_metrics.py
==============================================================================
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import duckdb
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MetricsPusher")


def load_environment() -> None:
    """Load environment variables from .env file in search hierarchy."""
    possible_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "pipeline" / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",
    ]
    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logger.info("Loaded environment configuration from: %s", env_path)
            return
    load_dotenv()


def collect_metrics_from_duckdb(duckdb_path: Path) -> List[Tuple[str, Dict[str, str], float]]:
    """
    Query analytics marts from DuckDB and extract metric data points.

    Returns:
        List of tuples: (metric_name, labels_dict, metric_value)
    """
    if not duckdb_path.exists():
        logger.error("DuckDB file does not exist at: %s", duckdb_path)
        return []

    con = duckdb.connect(str(duckdb_path), read_only=True)
    metrics: List[Tuple[str, Dict[str, str], float]] = []

    try:
        tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
        logger.info("Available tables/views in DuckDB: %s", tables)

        # ---------------------------------------------------------------------
        # 1. User Growth Metrics (mart_user_growth)
        # ---------------------------------------------------------------------
        if "mart_user_growth" in tables:
            query = """
                SELECT 
                    metric_date,
                    dau_count,
                    wau_count,
                    mau_count,
                    new_registrations_count,
                    cumulative_total_users
                FROM mart_user_growth
                ORDER BY metric_date DESC
                LIMIT 1;
            """
            row = con.execute(query).fetchone()
            if row:
                m_date, dau, wau, mau, new_users, total_users = row
                date_str = str(m_date)
                labels = {"source": "business_pipeline"}
                metrics.append(("business_users_dau", labels, float(dau or 0)))
                metrics.append(("business_users_wau", labels, float(wau or 0)))
                metrics.append(("business_users_mau", labels, float(mau or 0)))
                metrics.append(("business_users_new_daily", labels, float(new_users or 0)))
                metrics.append(("business_users_total", labels, float(total_users or 0)))
                logger.info("Collected User Growth metrics for date %s (DAU=%s, MAU=%s)", date_str, dau, mau)

        # ---------------------------------------------------------------------
        # 2. Revenue Metrics (mart_revenue)
        # ---------------------------------------------------------------------
        if "mart_revenue" in tables:
            query = """
                SELECT 
                    metric_date,
                    currency,
                    payment_method,
                    daily_gross_revenue,
                    daily_successful_transactions,
                    daily_average_order_value,
                    cumulative_total_revenue
                FROM mart_revenue
                WHERE metric_date = (SELECT MAX(metric_date) FROM mart_revenue);
            """
            rows = con.execute(query).fetchall()
            for row in rows:
                m_date, curr, pay_method, gross_rev, tx_count, aov, cum_rev = row
                labels = {
                    "currency": str(curr or "USD"),
                    "payment_method": str(pay_method or "all"),
                    "source": "business_pipeline",
                }
                metrics.append(("business_revenue_daily_amount", labels, float(gross_rev or 0)))
                metrics.append(("business_transactions_daily_count", labels, float(tx_count or 0)))
                metrics.append(("business_revenue_average_order_value", labels, float(aov or 0)))
                metrics.append(("business_revenue_cumulative_total", labels, float(cum_rev or 0)))
            logger.info("Collected Revenue metrics (%d records)", len(rows))

        # ---------------------------------------------------------------------
        # 3. Funnel Metrics (mart_event_funnel)
        # ---------------------------------------------------------------------
        if "mart_event_funnel" in tables:
            query = """
                SELECT 
                    funnel_step_order,
                    step_name,
                    event_name,
                    total_events,
                    unique_users_count,
                    step_conversion_rate,
                    overall_conversion_rate
                FROM mart_event_funnel
                ORDER BY funnel_step_order ASC;
            """
            rows = con.execute(query).fetchall()
            for row in rows:
                step_order, step_name, ev_name, total_events, users_count, step_cr, overall_cr = row
                labels = {
                    "step_order": str(step_order),
                    "step_name": str(step_name),
                    "event_name": str(ev_name),
                    "source": "business_pipeline",
                }
                metrics.append(("business_funnel_step_events_total", labels, float(total_events or 0)))
                metrics.append(("business_funnel_step_unique_users", labels, float(users_count or 0)))
                metrics.append(("business_funnel_step_conversion_ratio", labels, float(step_cr or 0)))
                metrics.append(("business_funnel_overall_conversion_ratio", labels, float(overall_cr or 0)))
            logger.info("Collected Funnel step metrics (%d steps)", len(rows))

        # ---------------------------------------------------------------------
        # 4. Platform Split Metrics (mart_platform_split)
        # ---------------------------------------------------------------------
        if "mart_platform_split" in tables:
            query = """
                SELECT 
                    platform,
                    active_users_count,
                    events_count,
                    revenue_amount
                FROM mart_platform_split
                WHERE metric_date = (SELECT MAX(metric_date) FROM mart_platform_split);
            """
            rows = con.execute(query).fetchall()
            for row in rows:
                platform, active_users, events_count, revenue = row
                labels = {"platform": str(platform or "unknown"), "source": "business_pipeline"}
                metrics.append(("business_platform_active_users", labels, float(active_users or 0)))
                metrics.append(("business_platform_events_total", labels, float(events_count or 0)))
                metrics.append(("business_platform_revenue_total", labels, float(revenue or 0)))
            logger.info("Collected Platform split metrics (%d platforms)", len(rows))

    finally:
        con.close()

    return metrics


def format_prometheus_payload(metrics: List[Tuple[str, Dict[str, str], float]]) -> str:
    """
    Format metrics into Prometheus OpenMetrics / Text Exposition format.

    Args:
        metrics: List of (name, labels, value).

    Returns:
        String in Prometheus exposition format.
    """
    lines = []
    timestamp_ms = int(time.time() * 1000)

    # Group metrics by name to emit HELP and TYPE headers
    handled_metric_types = set()

    for name, labels, val in metrics:
        if name not in handled_metric_types:
            lines.append(f"# HELP {name} Business flow telemetry metric")
            lines.append(f"# TYPE {name} gauge")
            handled_metric_types.add(name)

        if labels:
            label_str = ",".join([f'{k}="{v}"' for k, v in sorted(labels.items())])
            lines.append(f"{name}{{{label_str}}} {val} {timestamp_ms}")
        else:
            lines.append(f"{name} {val} {timestamp_ms}")

    # Prometheus exposition format requires trailing newline
    lines.append("")
    return "\n".join(lines)


def push_to_grafana(payload: str) -> bool:
    """
    Push OpenMetrics payload to Grafana Cloud Prometheus HTTP Push endpoint.

    Args:
        payload: Formatted Prometheus metrics text.

    Returns:
        bool: True if push succeeded or was gracefully skipped in dry-run mode.
    """
    url = os.getenv("GRAFANA_PROMETHEUS_URL")
    instance_id = os.getenv("GRAFANA_INSTANCE_ID")
    api_key = os.getenv("GRAFANA_API_KEY")

    if not url or "your-prometheus-url" in url or not api_key or "your_api_key" in api_key:
        logger.warning(
            "GRAFANA_PROMETHEUS_URL or credentials not configured. "
            "Skipping HTTP push (DRY RUN mode). Metric payload preview:\n%s",
            payload[:800],
        )
        return True

    headers = {
        "Content-Type": "text/plain; version=0.0.4; charset=utf-8",
        "User-Agent": "BusinessFlowsTelemetry/1.0",
    }
    
    # Grafana Cloud uses Instance ID as user and API Key / Token as password
    auth = (instance_id, api_key) if instance_id else None
    if not auth:
        headers["Authorization"] = f"Bearer {api_key}"

    logger.info("Pushing %d bytes of metrics to Grafana Cloud at: %s", len(payload), url)
    try:
        response = requests.post(url, data=payload, headers=headers, auth=auth, timeout=20)
        if response.status_code in (200, 202, 204):
            logger.info("Successfully pushed metrics to Grafana Cloud (HTTP %d).", response.status_code)
            return True
        else:
            logger.error(
                "Failed to push metrics to Grafana Cloud. HTTP %d: %s",
                response.status_code,
                response.text,
            )
            return False
    except Exception as e:
        logger.error("Exception occurred while pushing metrics to Grafana Cloud: %s", str(e))
        return False


def main() -> bool:
    """Main execution flow for push_metrics."""
    logger.info("=== Starting Grafana Cloud Metrics Push ===")
    load_environment()

    duckdb_path = Path(os.getenv("DUCKDB_PATH", "./analytics.duckdb")).resolve()
    metrics = collect_metrics_from_duckdb(duckdb_path)

    if not metrics:
        logger.warning("No metrics collected from DuckDB marts.")
        return True

    payload = format_prometheus_payload(metrics)
    success = push_to_grafana(payload)
    logger.info("=== Finished Metrics Push (status=%s) ===", success)
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
