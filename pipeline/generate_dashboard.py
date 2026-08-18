"""
==============================================================================
Business Flows Telemetry Stack - Standalone HTML Dashboard Generator
==============================================================================
Connects to DuckDB marts (or generates realistic mock data if unavailable)
and generates a modern, standalone HTML analytics dashboard with Chart.js.

Usage:
    python generate_dashboard.py
==============================================================================
"""

import os
import sys
import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("DashboardGenerator")


def find_duckdb_path() -> Optional[Path]:
    """Locate the analytics.duckdb file across standard locations."""
    env_path = os.getenv("DUCKDB_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    candidates = [
        Path.cwd() / "analytics.duckdb",
        Path.cwd() / "pipeline" / "analytics.duckdb",
        Path(__file__).resolve().parent / "analytics.duckdb",
        Path(__file__).resolve().parent.parent / "pipeline" / "analytics.duckdb",
        Path(__file__).resolve().parent.parent / "analytics.duckdb",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return None


def generate_mock_data() -> Dict[str, Any]:
    """Generate realistic mock telemetry data for all 4 marts if DuckDB is missing."""
    logger.info("Generating mock telemetry data for dashboard visualization...")
    today = date.today()
    dates = [(today - timedelta(days=30 - i)).strftime("%Y-%m-%d") for i in range(31)]

    # 1. User Growth Mock
    user_growth = []
    cum_users = 10
    for i, d in enumerate(dates):
        new_u = max(1, int(3 + (i % 5) * 1.5 + (i * 0.4)))
        cum_users += new_u
        dau = max(2, int(cum_users * (0.15 + (i % 7) * 0.03)))
        wau = max(dau, int(cum_users * (0.45 + (i % 5) * 0.04)))
        mau = max(wau, int(cum_users * (0.80 + (i % 3) * 0.05)))
        stickiness = round(dau / mau if mau > 0 else 0.0, 4)
        user_growth.append({
            "metric_date": d,
            "dau_count": dau,
            "wau_count": wau,
            "mau_count": mau,
            "new_registrations_count": new_u,
            "cumulative_total_users": cum_users,
            "dau_to_mau_stickiness_ratio": stickiness,
        })

    # 2. Event Funnel Mock
    funnel_steps = [
        {"order": 1, "name": "Step 1: screen_view", "event": "screen_view", "users": 150, "events": 420},
        {"order": 2, "name": "Step 2: signup_started", "event": "signup_started", "users": 132, "events": 280},
        {"order": 3, "name": "Step 3: item_viewed", "event": "item_viewed", "users": 118, "events": 310},
        {"order": 4, "name": "Step 4: button_click", "event": "button_click", "users": 105, "events": 260},
        {"order": 5, "name": "Step 5: signup_completed", "event": "signup_completed", "users": 98, "events": 140},
        {"order": 6, "name": "Step 6: checkout_started", "event": "checkout_started", "users": 84, "events": 110},
        {"order": 7, "name": "Step 7: purchase_completed", "event": "purchase_completed", "users": 65, "events": 85},
    ]
    top_users = funnel_steps[0]["users"]
    event_funnel = []
    for i, s in enumerate(funnel_steps):
        prev_u = funnel_steps[i - 1]["users"] if i > 0 else s["users"]
        step_cr = round(s["users"] / prev_u, 4) if prev_u > 0 else 1.0
        overall_cr = round(s["users"] / top_users, 4) if top_users > 0 else 1.0
        dropoff = max(0, prev_u - s["users"]) if i > 0 else 0
        event_funnel.append({
            "funnel_step_order": s["order"],
            "step_name": s["name"],
            "event_name": s["event"],
            "total_events": s["events"],
            "unique_users_count": s["users"],
            "unique_sessions_count": int(s["users"] * 1.3),
            "step_conversion_rate": step_cr,
            "overall_conversion_rate": overall_cr,
            "step_dropoff_users_count": dropoff,
        })

    # 3. Revenue Mock
    revenue = []
    cum_rev = 0.0
    for i, d in enumerate(dates[-16:]):
        daily_tx = (i % 6) + 1
        daily_gross = round(daily_tx * (65.0 + (i % 4) * 35.5), 2)
        cum_rev = round(cum_rev + daily_gross, 2)
        aov = round(daily_gross / daily_tx, 2) if daily_tx > 0 else 0.0
        revenue.append({
            "metric_date": d,
            "currency": "BRL",
            "payment_method": "pix" if i % 2 == 0 else "credit_card",
            "total_transactions_count": daily_tx,
            "daily_successful_transactions": daily_tx,
            "daily_failed_transactions": 0,
            "daily_paying_users_count": max(1, daily_tx - 1),
            "daily_gross_revenue": daily_gross,
            "daily_average_order_value": aov,
            "cumulative_total_revenue": cum_rev,
        })

    # 4. Platform Split Mock
    platform_split = []
    for d in dates[-10:]:
        for p, share, rev_w in [("ios", 0.35, 1.2), ("android", 0.40, 0.9), ("web", 0.25, 1.4)]:
            ev_count = int(50 * share) + (len(d) % 5)
            rev = round(ev_count * 12.5 * rev_w, 2)
            platform_split.append({
                "metric_date": d,
                "platform": p,
                "active_users_count": int(ev_count * 0.7),
                "events_count": ev_count,
                "sessions_count": int(ev_count * 0.8),
                "registrations_count": max(1, int(ev_count * 0.15)),
                "transactions_count": max(1, int(ev_count * 0.1)),
                "revenue_amount": rev,
                "platform_event_share_ratio": round(share, 4),
            })

    return {
        "user_growth": user_growth,
        "event_funnel": event_funnel,
        "revenue": revenue,
        "platform_split": platform_split,
        "source": "Mock Data Generator",
    }


def query_duckdb_marts(duckdb_path: Path) -> Dict[str, Any]:
    """Query data from the 4 DuckDB marts."""
    try:
        import duckdb
    except ImportError:
        logger.warning("duckdb package not available. Falling back to mock data.")
        return generate_mock_data()

    logger.info("Connecting to DuckDB at: %s", duckdb_path)
    try:
        con = duckdb.connect(str(duckdb_path), read_only=True)
        tables = [r[0] for r in con.execute("SHOW TABLES;").fetchall()]
        logger.info("Found tables in DuckDB: %s", tables)

        required_marts = ["mart_user_growth", "mart_event_funnel", "mart_revenue", "mart_platform_split"]
        missing_marts = [m for m in required_marts if m not in tables]

        if missing_marts:
            logger.warning("Missing required marts in DuckDB: %s. Using mock fallback.", missing_marts)
            con.close()
            return generate_mock_data()

        # 1. mart_user_growth
        q_growth = """
            SELECT 
                CAST(metric_date AS VARCHAR) AS metric_date,
                COALESCE(dau_count, 0) AS dau_count,
                COALESCE(wau_count, 0) AS wau_count,
                COALESCE(mau_count, 0) AS mau_count,
                COALESCE(new_registrations_count, 0) AS new_registrations_count,
                COALESCE(cumulative_total_users, 0) AS cumulative_total_users,
                COALESCE(dau_to_mau_stickiness_ratio, 0.0) AS dau_to_mau_stickiness_ratio
            FROM mart_user_growth
            ORDER BY metric_date ASC;
        """
        growth_rows = [dict(zip(["metric_date", "dau_count", "wau_count", "mau_count", "new_registrations_count", "cumulative_total_users", "dau_to_mau_stickiness_ratio"], r))
                       for r in con.execute(q_growth).fetchall()]

        # 2. mart_event_funnel
        q_funnel = """
            SELECT 
                funnel_step_order,
                step_name,
                event_name,
                COALESCE(total_events, 0) AS total_events,
                COALESCE(unique_users_count, 0) AS unique_users_count,
                COALESCE(unique_sessions_count, 0) AS unique_sessions_count,
                COALESCE(step_conversion_rate, 0.0) AS step_conversion_rate,
                COALESCE(overall_conversion_rate, 0.0) AS overall_conversion_rate,
                COALESCE(step_dropoff_users_count, 0) AS step_dropoff_users_count
            FROM mart_event_funnel
            ORDER BY funnel_step_order ASC;
        """
        funnel_cols = ["funnel_step_order", "step_name", "event_name", "total_events", "unique_users_count", "unique_sessions_count", "step_conversion_rate", "overall_conversion_rate", "step_dropoff_users_count"]
        funnel_rows = [dict(zip(funnel_cols, r)) for r in con.execute(q_funnel).fetchall()]

        # 3. mart_revenue
        q_revenue = """
            SELECT 
                CAST(metric_date AS VARCHAR) AS metric_date,
                COALESCE(currency, 'BRL') AS currency,
                COALESCE(payment_method, 'all') AS payment_method,
                COALESCE(total_transactions_count, 0) AS total_transactions_count,
                COALESCE(daily_successful_transactions, 0) AS daily_successful_transactions,
                COALESCE(daily_failed_transactions, 0) AS daily_failed_transactions,
                COALESCE(daily_paying_users_count, 0) AS daily_paying_users_count,
                CAST(COALESCE(daily_gross_revenue, 0.0) AS DOUBLE) AS daily_gross_revenue,
                CAST(COALESCE(daily_average_order_value, 0.0) AS DOUBLE) AS daily_average_order_value,
                CAST(COALESCE(cumulative_total_revenue, 0.0) AS DOUBLE) AS cumulative_total_revenue
            FROM mart_revenue
            ORDER BY metric_date ASC, currency, payment_method;
        """
        revenue_cols = ["metric_date", "currency", "payment_method", "total_transactions_count", "daily_successful_transactions", "daily_failed_transactions", "daily_paying_users_count", "daily_gross_revenue", "daily_average_order_value", "cumulative_total_revenue"]
        revenue_rows = [dict(zip(revenue_cols, r)) for r in con.execute(q_revenue).fetchall()]

        # 4. mart_platform_split
        q_platform = """
            SELECT 
                CAST(metric_date AS VARCHAR) AS metric_date,
                COALESCE(platform, 'unknown') AS platform,
                COALESCE(active_users_count, 0) AS active_users_count,
                COALESCE(events_count, 0) AS events_count,
                COALESCE(sessions_count, 0) AS sessions_count,
                COALESCE(registrations_count, 0) AS registrations_count,
                COALESCE(transactions_count, 0) AS transactions_count,
                CAST(COALESCE(revenue_amount, 0.0) AS DOUBLE) AS revenue_amount,
                COALESCE(platform_event_share_ratio, 0.0) AS platform_event_share_ratio
            FROM mart_platform_split
            ORDER BY metric_date ASC, platform ASC;
        """
        platform_cols = ["metric_date", "platform", "active_users_count", "events_count", "sessions_count", "registrations_count", "transactions_count", "revenue_amount", "platform_event_share_ratio"]
        platform_rows = [dict(zip(platform_cols, r)) for r in con.execute(q_platform).fetchall()]

        con.close()
        logger.info("Successfully fetched all 4 marts from DuckDB (%s).", duckdb_path.name)

        return {
            "user_growth": growth_rows,
            "event_funnel": funnel_rows,
            "revenue": revenue_rows,
            "platform_split": platform_rows,
            "source": f"DuckDB ({duckdb_path.name})",
        }

    except Exception as e:
        logger.error("Error reading DuckDB: %s. Falling back to mock data.", str(e))
        return generate_mock_data()


def build_dashboard_html(data: Dict[str, Any]) -> str:
    """Generate standalone HTML dashboard string with modern dark UI and Chart.js."""
    user_growth = data.get("user_growth", [])
    event_funnel = data.get("event_funnel", [])
    revenue = data.get("revenue", [])
    platform_split = data.get("platform_split", [])
    data_source = data.get("source", "DuckDB Analytics")

    # Compute High Level KPIs
    latest_growth = user_growth[-1] if user_growth else {}
    total_users = int(latest_growth.get("cumulative_total_users", 0))
    current_dau = int(latest_growth.get("dau_count", 0))
    current_wau = int(latest_growth.get("wau_count", 0))
    current_mau = int(latest_growth.get("mau_count", 0))
    stickiness_pct = round(float(latest_growth.get("dau_to_mau_stickiness_ratio", 0)) * 100, 1)

    # Funnel KPIs
    funnel_top_users = event_funnel[0].get("unique_users_count", 0) if event_funnel else 0
    funnel_bottom_users = event_funnel[-1].get("unique_users_count", 0) if event_funnel else 0
    overall_funnel_cr = round(float(event_funnel[-1].get("overall_conversion_rate", 0)) * 100, 1) if event_funnel else 0.0

    # Revenue KPIs
    daily_rev_map = {}
    cum_rev_max = 0.0
    total_tx_count = 0
    total_successful_tx = 0
    currency = "BRL"

    for r in revenue:
        d = r.get("metric_date", "")
        currency = r.get("currency", currency)
        gross = float(r.get("daily_gross_revenue", 0.0))
        cum = float(r.get("cumulative_total_revenue", 0.0))
        tx = int(r.get("total_transactions_count", 0))
        s_tx = int(r.get("daily_successful_transactions", 0))

        daily_rev_map[d] = daily_rev_map.get(d, 0.0) + gross
        if cum > cum_rev_max:
            cum_rev_max = cum
        total_tx_count += tx
        total_successful_tx += s_tx

    total_gross_rev = round(cum_rev_max if cum_rev_max > 0 else sum(daily_rev_map.values()), 2)
    avg_aov = round(total_gross_rev / total_successful_tx, 2) if total_successful_tx > 0 else 0.0

    # Platform Totals
    platform_totals = {}
    for p in platform_split:
        plat = p.get("platform", "unknown")
        if plat not in platform_totals:
            platform_totals[plat] = {"events": 0, "users": 0, "revenue": 0.0}
        platform_totals[plat]["events"] += int(p.get("events_count", 0))
        platform_totals[plat]["users"] += int(p.get("active_users_count", 0))
        platform_totals[plat]["revenue"] += float(p.get("revenue_amount", 0.0))

    # JSON Serialized datasets for JavaScript
    json_growth = json.dumps(user_growth, ensure_ascii=False)
    json_funnel = json.dumps(event_funnel, ensure_ascii=False)
    json_revenue = json.dumps(revenue, ensure_ascii=False)
    json_platform = json.dumps(platform_split, ensure_ascii=False)
    json_platform_totals = json.dumps(platform_totals, ensure_ascii=False)

    generated_timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Safe placeholder replacement to avoid f-string escaping conflicts with JS syntax
    raw_template = """<!DOCTYPE html>
<html lang="pt-BR" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Business Flows Telemetry — Analytics Dashboard</title>
    <!-- Google Fonts: Inter -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-card: #111827;
            --bg-card-hover: #172033;
            --bg-subtle: #1f293d;
            --border-color: #232d42;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
            --accent-pink: #ec4899;
            --accent-rose: #f43f5e;
            --shadow-card: 0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 2px 6px -1px rgba(0, 0, 0, 0.4);
            --radius-sm: 8px;
            --radius-md: 12px;
            --radius-lg: 16px;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
            padding: 0 0 40px 0;
        }

        /* Header Bar */
        .top-navbar {
            background-color: rgba(17, 24, 39, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 50;
            padding: 14px 28px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .brand-section {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-logo {
            width: 38px;
            height: 38px;
            border-radius: var(--radius-sm);
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 800;
            font-size: 18px;
            color: #ffffff;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
        }

        .brand-info h1 {
            font-size: 1.15rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #ffffff;
        }

        .brand-info p {
            font-size: 0.78rem;
            color: var(--text-secondary);
        }

        .header-meta {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 5px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid var(--border-color);
            background-color: var(--bg-card);
        }

        .badge-live {
            color: var(--accent-emerald);
            border-color: rgba(16, 185, 129, 0.3);
            background-color: rgba(16, 185, 129, 0.1);
        }

        .badge-live::before {
            content: '';
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: var(--accent-emerald);
            box-shadow: 0 0 8px var(--accent-emerald);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }

        .badge-source {
            color: var(--accent-cyan);
            border-color: rgba(6, 182, 212, 0.3);
            background-color: rgba(6, 182, 212, 0.08);
        }

        .timestamp-text {
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        /* Main Container */
        .container {
            max-width: 1440px;
            margin: 0 auto;
            padding: 24px 28px;
        }

        /* KPI Cards Grid */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-md);
            padding: 20px 18px;
            box-shadow: var(--shadow-card);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: transform 0.2s ease, border-color 0.2s ease;
            position: relative;
            overflow: hidden;
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(99, 102, 241, 0.4);
            background: var(--bg-card-hover);
        }

        .kpi-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }

        .kpi-card.c-blue::after { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
        .kpi-card.c-purple::after { background: linear-gradient(90deg, #8b5cf6, #a78bfa); }
        .kpi-card.c-emerald::after { background: linear-gradient(90deg, #10b981, #34d399); }
        .kpi-card.c-amber::after { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
        .kpi-card.c-cyan::after { background: linear-gradient(90deg, #06b6d4, #38bdf8); }
        .kpi-card.c-pink::after { background: linear-gradient(90deg, #ec4899, #f472b6); }

        .kpi-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }

        .kpi-title {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            font-weight: 600;
        }

        .kpi-icon {
            font-size: 1.1rem;
            opacity: 0.8;
        }

        .kpi-value {
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #ffffff;
            margin: 4px 0;
        }

        .kpi-footer {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.75rem;
            color: var(--text-muted);
            margin-top: 4px;
        }

        .kpi-tag {
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
        }

        .kpi-tag.positive {
            color: #34d399;
            background-color: rgba(16, 185, 129, 0.15);
        }

        .kpi-tag.neutral {
            color: #93c5fd;
            background-color: rgba(59, 130, 246, 0.15);
        }

        /* Main Charts Grid */
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }

        @media (max-width: 1024px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }
        }

        .chart-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 22px;
            box-shadow: var(--shadow-card);
            display: flex;
            flex-direction: column;
            min-height: 420px;
        }

        .chart-card.full-width {
            grid-column: 1 / -1;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 18px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .chart-title-area h2 {
            font-size: 1.05rem;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.01em;
        }

        .chart-title-area p {
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .chart-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-toggle {
            background: var(--bg-subtle);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            padding: 5px 10px;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .btn-toggle:hover, .btn-toggle.active {
            background: var(--accent-blue);
            color: #ffffff;
            border-color: var(--accent-blue);
        }

        .chart-body {
            position: relative;
            flex: 1;
            width: 100%;
            height: 100%;
            min-height: 310px;
        }

        /* Table Card */
        .table-section {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            padding: 22px;
            box-shadow: var(--shadow-card);
            margin-top: 24px;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.84rem;
        }

        .custom-table th {
            text-align: left;
            padding: 10px 14px;
            background: var(--bg-subtle);
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.05em;
        }

        .custom-table td {
            padding: 12px 14px;
            border-bottom: 1px solid rgba(35, 45, 66, 0.7);
            color: var(--text-primary);
        }

        .custom-table tr:hover td {
            background-color: var(--bg-card-hover);
        }

        .progress-bar-bg {
            width: 100%;
            height: 6px;
            background-color: var(--bg-subtle);
            border-radius: 9999px;
            overflow: hidden;
            margin-top: 4px;
        }

        .progress-bar-fill {
            height: 100%;
            border-radius: 9999px;
            background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        }

        /* Footer */
        .footer-note {
            margin-top: 32px;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-muted);
        }

        .footer-note a {
            color: var(--accent-cyan);
            text-decoration: none;
        }
    </style>
</head>
<body>

    <!-- Header Navbar -->
    <header class="top-navbar">
        <div class="brand-section">
            <div class="brand-logo">⚡</div>
            <div class="brand-info">
                <h1>Business Flows Telemetry</h1>
                <p>Startup Data Analytics Stack &bull; Marts Visualization</p>
            </div>
        </div>
        <div class="header-meta">
            <span class="badge-pill badge-live">ONLINE</span>
            <span class="badge-pill badge-source">__DATA_SOURCE__</span>
            <span class="timestamp-text">Atualizado em: __GENERATED_TIMESTAMP__</span>
        </div>
    </header>

    <!-- Main Content Container -->
    <main class="container">

        <!-- KPI Grid -->
        <section class="kpi-grid">
            <!-- 1. Total Registered Users -->
            <div class="kpi-card c-blue">
                <div class="kpi-header">
                    <span class="kpi-title">Total de Usuários</span>
                    <span class="kpi-icon">👥</span>
                </div>
                <div class="kpi-value">__TOTAL_USERS__</div>
                <div class="kpi-footer">
                    <span class="kpi-tag neutral">+__NEW_USERS_TODAY__ novos</span>
                    <span>registrados hoje</span>
                </div>
            </div>

            <!-- 2. Daily Active Users (DAU) -->
            <div class="kpi-card c-purple">
                <div class="kpi-header">
                    <span class="kpi-title">Ativos Diários (DAU)</span>
                    <span class="kpi-icon">⚡</span>
                </div>
                <div class="kpi-value">__CURRENT_DAU__</div>
                <div class="kpi-footer">
                    <span class="kpi-tag positive">__STICKINESS_PCT__%</span>
                    <span>Stickiness (DAU/MAU)</span>
                </div>
            </div>

            <!-- 3. Monthly Active Users (MAU) -->
            <div class="kpi-card c-cyan">
                <div class="kpi-header">
                    <span class="kpi-title">Ativos Mensais (MAU)</span>
                    <span class="kpi-icon">📅</span>
                </div>
                <div class="kpi-value">__CURRENT_MAU__</div>
                <div class="kpi-footer">
                    <span class="kpi-tag neutral">WAU: __CURRENT_WAU__</span>
                    <span>últimos 30 dias</span>
                </div>
            </div>

            <!-- 4. Conversion Rate -->
            <div class="kpi-card c-emerald">
                <div class="kpi-header">
                    <span class="kpi-title">Conversão Global Funil</span>
                    <span class="kpi-icon">🎯</span>
                </div>
                <div class="kpi-value">__OVERALL_FUNNEL_CR__%</div>
                <div class="kpi-footer">
                    <span class="kpi-tag positive">__FUNNEL_BOTTOM_USERS__/__FUNNEL_TOP_USERS__</span>
                    <span>Etapa Inicial &rarr; Final</span>
                </div>
            </div>

            <!-- 5. Gross Revenue -->
            <div class="kpi-card c-amber">
                <div class="kpi-header">
                    <span class="kpi-title">Receita Bruta Acumulada</span>
                    <span class="kpi-icon">💰</span>
                </div>
                <div class="kpi-value">__CURRENCY__ __TOTAL_GROSS_REV__</div>
                <div class="kpi-footer">
                    <span class="kpi-tag positive">+__TOTAL_SUCCESSFUL_TX__</span>
                    <span>vendas concluídas</span>
                </div>
            </div>

            <!-- 6. Ticket Médio (AOV) -->
            <div class="kpi-card c-pink">
                <div class="kpi-header">
                    <span class="kpi-title">Ticket Médio (AOV)</span>
                    <span class="kpi-icon">🏷️</span>
                </div>
                <div class="kpi-value">__CURRENCY__ __AVG_AOV__</div>
                <div class="kpi-footer">
                    <span class="kpi-tag neutral">__TOTAL_TX_COUNT__ pedidos</span>
                    <span>total transações</span>
                </div>
            </div>
        </section>

        <!-- 4 Main Charts Grid -->
        <section class="charts-grid">

            <!-- Chart 1: User Growth (DAU, WAU, MAU) -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title-area">
                        <h2>1. Crescimento e Engajamento de Usuários</h2>
                        <p>Evolução diária de DAU, WAU e MAU ao longo do tempo</p>
                    </div>
                    <div class="chart-controls">
                        <span class="badge-pill" style="font-size: 0.7rem; color: #8b5cf6;">mart_user_growth</span>
                    </div>
                </div>
                <div class="chart-body">
                    <canvas id="userGrowthChart"></canvas>
                </div>
            </div>

            <!-- Chart 2: Conversion Funnel -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title-area">
                        <h2>2. Funil de Conversão de Eventos</h2>
                        <p>Volume de usuários únicos e drop-off por etapa do produto</p>
                    </div>
                    <div class="chart-controls">
                        <span class="badge-pill" style="font-size: 0.7rem; color: #10b981;">mart_event_funnel</span>
                    </div>
                </div>
                <div class="chart-body">
                    <canvas id="funnelChart"></canvas>
                </div>
            </div>

            <!-- Chart 3: Revenue over Time -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title-area">
                        <h2>3. Receita por Período & Acumulado</h2>
                        <p>Receita diária bruta (__CURRENCY__) e crescimento acumulado</p>
                    </div>
                    <div class="chart-controls">
                        <span class="badge-pill" style="font-size: 0.7rem; color: #f59e0b;">mart_revenue</span>
                    </div>
                </div>
                <div class="chart-body">
                    <canvas id="revenueChart"></canvas>
                </div>
            </div>

            <!-- Chart 4: Platform Split -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title-area">
                        <h2>4. Distribuição por Plataforma</h2>
                        <p>Proporção de engajamento entre iOS, Android e Web</p>
                    </div>
                    <div class="chart-controls">
                        <button class="btn-toggle active" id="btn-plat-users" onclick="switchPlatformMetric('users')">Usuários</button>
                        <button class="btn-toggle" id="btn-plat-events" onclick="switchPlatformMetric('events')">Eventos</button>
                        <button class="btn-toggle" id="btn-plat-revenue" onclick="switchPlatformMetric('revenue')">Receita</button>
                    </div>
                </div>
                <div class="chart-body">
                    <canvas id="platformChart"></canvas>
                </div>
            </div>

        </section>

        <!-- Funnel Step Details Table -->
        <section class="table-section">
            <div class="table-header">
                <div>
                    <h2 style="font-size: 1.05rem; font-weight: 700; color: #fff;">Detalhamento das Etapas do Funil</h2>
                    <p style="font-size: 0.8rem; color: var(--text-secondary);">Métricas detalhadas de telemetria por evento do aplicativo</p>
                </div>
                <span class="badge-pill badge-source">__FUNNEL_STEPS_COUNT__ Etapas Mapeadas</span>
            </div>
            <div style="overflow-x: auto;">
                <table class="custom-table" id="funnelTable">
                    <thead>
                        <tr>
                            <th>Ordem</th>
                            <th>Etapa / Evento</th>
                            <th>Usuários Únicos</th>
                            <th>Total Eventos</th>
                            <th>Conversão da Etapa (Step CR)</th>
                            <th>Conversão Geral (Overall CR)</th>
                            <th>Drop-off</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Injected via JavaScript -->
                    </tbody>
                </table>
            </div>
        </section>

        <footer class="footer-note">
            <p>Business Flows Telemetry Stack &bull; Gerado localmente a partir de <code>pipeline/analytics.duckdb</code></p>
            <p style="margin-top: 4px; font-size: 0.72rem; color: #4b5563;">Stack: DuckDB + dbt-duckdb + Chart.js &bull; Compatível com Grafana Cloud</p>
        </footer>

    </main>

    <!-- Embedded Analytics Data & Chart.js Initialization -->
    <script>
        const rawGrowth = __JSON_GROWTH__;
        const rawFunnel = __JSON_FUNNEL__;
        const rawRevenue = __JSON_REVENUE__;
        const rawPlatform = __JSON_PLATFORM__;
        const platformTotals = __JSON_PLATFORM_TOTALS__;
        const appCurrency = '__CURRENCY__';

        // Dark Chart.js Global Defaults
        Chart.defaults.color = '#9ca3af';
        Chart.defaults.borderColor = '#232d42';
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.plugins.tooltip.backgroundColor = '#111827';
        Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
        Chart.defaults.plugins.tooltip.bodyColor = '#e5e7eb';
        Chart.defaults.plugins.tooltip.borderColor = '#374151';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;

        // -------------------------------------------------------------
        // Chart 1: User Growth (Line Chart)
        // -------------------------------------------------------------
        const growthLabels = rawGrowth.map(d => d.metric_date);
        const dauData = rawGrowth.map(d => d.dau_count);
        const wauData = rawGrowth.map(d => d.wau_count);
        const mauData = rawGrowth.map(d => d.mau_count);

        const ctxGrowth = document.getElementById('userGrowthChart').getContext('2d');
        const userGrowthChart = new Chart(ctxGrowth, {
            type: 'line',
            data: {
                labels: growthLabels,
                datasets: [
                    {
                        label: 'DAU (Ativos Diários)',
                        data: dauData,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.12)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.35,
                        pointRadius: growthLabels.length > 25 ? 1 : 3,
                    },
                    {
                        label: 'WAU (Ativos Semanais)',
                        data: wauData,
                        borderColor: '#818cf8',
                        backgroundColor: 'rgba(129, 140, 248, 0.05)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.35,
                        pointRadius: growthLabels.length > 25 ? 1 : 3,
                    },
                    {
                        label: 'MAU (Ativos Mensais)',
                        data: mauData,
                        borderColor: '#a855f7',
                        backgroundColor: 'rgba(168, 85, 247, 0.05)',
                        borderWidth: 2.5,
                        fill: false,
                        tension: 0.35,
                        pointRadius: growthLabels.length > 25 ? 1 : 3,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { boxWidth: 12, usePointStyle: true, padding: 16 }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 8 }
                    },
                    y: {
                        grid: { color: '#1f293d' },
                        beginAtZero: true
                    }
                }
            }
        });

        // -------------------------------------------------------------
        // Chart 2: Event Funnel (Horizontal Bar Chart)
        // -------------------------------------------------------------
        const funnelLabels = rawFunnel.map(f => f.step_name || f.event_name);
        const funnelUsers = rawFunnel.map(f => f.unique_users_count);

        const ctxFunnel = document.getElementById('funnelChart').getContext('2d');
        const funnelChart = new Chart(ctxFunnel, {
            type: 'bar',
            data: {
                labels: funnelLabels,
                datasets: [{
                    label: 'Usuários Únicos na Etapa',
                    data: funnelUsers,
                    backgroundColor: [
                        '#3b82f6', '#06b6d4', '#10b981', '#84cc16', '#eab308', '#f97316', '#ec4899'
                    ],
                    borderRadius: 6,
                    borderWidth: 0,
                    barPercentage: 0.7,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: function(context) {
                                const idx = context.dataIndex;
                                const step = rawFunnel[idx];
                                const stepCr = (step.step_conversion_rate * 100).toFixed(1);
                                const overallCr = (step.overall_conversion_rate * 100).toFixed(1);
                                return [
                                    'Conversão da Etapa: ' + stepCr + '%',
                                    'Conversão Geral: ' + overallCr + '%',
                                    'Drop-off: -' + step.step_dropoff_users_count + ' usuários'
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: '#1f293d' },
                        beginAtZero: true
                    },
                    y: {
                        grid: { display: false }
                    }
                }
            }
        });

        // -------------------------------------------------------------
        // Chart 3: Revenue (Combo Bar + Line Chart)
        // -------------------------------------------------------------
        const revByDate = {};
        const cumByDate = {};
        rawRevenue.forEach(r => {
            const d = r.metric_date;
            revByDate[d] = (revByDate[d] || 0) + Number(r.daily_gross_revenue || 0);
            const cum = Number(r.cumulative_total_revenue || 0);
            if (!cumByDate[d] || cum > cumByDate[d]) {
                cumByDate[d] = cum;
            }
        });

        const revDates = Object.keys(revByDate).sort();
        const dailyGrossValues = revDates.map(d => revByDate[d]);
        const cumulativeValues = revDates.map(d => cumByDate[d] || 0);

        const ctxRevenue = document.getElementById('revenueChart').getContext('2d');
        const revenueChart = new Chart(ctxRevenue, {
            data: {
                labels: revDates,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Receita Diária (' + appCurrency + ')',
                        data: dailyGrossValues,
                        backgroundColor: 'rgba(245, 158, 11, 0.75)',
                        borderColor: '#f59e0b',
                        borderRadius: 4,
                        yAxisID: 'y'
                    },
                    {
                        type: 'line',
                        label: 'Receita Acumulada (' + appCurrency + ')',
                        data: cumulativeValues,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        borderWidth: 2.5,
                        fill: false,
                        tension: 0.3,
                        pointRadius: revDates.length > 20 ? 1 : 4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { boxWidth: 12, usePointStyle: true, padding: 16 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return context.dataset.label + ': ' + appCurrency + ' ' + Number(context.raw).toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 8 }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: '#1f293d' },
                        title: { display: true, text: 'Diária (' + appCurrency + ')', color: '#9ca3af' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: 'Acumulada (' + appCurrency + ')', color: '#10b981' }
                    }
                }
            }
        });

        // -------------------------------------------------------------
        // Chart 4: Platform Split (Donut Chart)
        // -------------------------------------------------------------
        const platformNames = ['iOS', 'Android', 'Web'];
        const platformKeys = ['ios', 'android', 'web'];

        function getPlatformData(metric) {
            return platformKeys.map(k => {
                const item = platformTotals[k] || { users: 0, events: 0, revenue: 0 };
                if (metric === 'users') return item.users;
                if (metric === 'events') return item.events;
                if (metric === 'revenue') return item.revenue;
                return 0;
            });
        }

        const ctxPlatform = document.getElementById('platformChart').getContext('2d');
        const platformChart = new Chart(ctxPlatform, {
            type: 'doughnut',
            data: {
                labels: platformNames,
                datasets: [{
                    data: getPlatformData('users'),
                    backgroundColor: ['#38bdf8', '#34d399', '#f43f5e'],
                    borderColor: '#111827',
                    borderWidth: 3,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '68%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { boxWidth: 14, usePointStyle: true, padding: 20 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const value = Number(context.raw);
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0.0';
                                return ' ' + context.label + ': ' + value.toLocaleString() + ' (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });

        function switchPlatformMetric(metric) {
            document.querySelectorAll('.chart-card .btn-toggle').forEach(btn => btn.classList.remove('active'));
            if (metric === 'users') document.getElementById('btn-plat-users').classList.add('active');
            if (metric === 'events') document.getElementById('btn-plat-events').classList.add('active');
            if (metric === 'revenue') document.getElementById('btn-plat-revenue').classList.add('active');
            
            platformChart.data.datasets[0].data = getPlatformData(metric);
            platformChart.update();
        }

        // -------------------------------------------------------------
        // Populate Funnel Table
        // -------------------------------------------------------------
        const tableTbody = document.querySelector('#funnelTable tbody');
        rawFunnel.forEach((step, idx) => {
            const tr = document.createElement('tr');
            const stepCr = (Number(step.step_conversion_rate || 0) * 100).toFixed(1);
            const overallCr = (Number(step.overall_conversion_rate || 0) * 100).toFixed(1);
            const tagClass = Number(stepCr) >= 80 ? 'positive' : 'neutral';
            const dropoffVal = Number(step.step_dropoff_users_count || 0);
            const dropColor = dropoffVal > 0 ? '#f87171' : '#9ca3af';
            const dropText = dropoffVal > 0 ? '-' + dropoffVal : '0';

            tr.innerHTML = 
                '<td style="font-weight: 700; color: #818cf8;">#' + step.funnel_step_order + '</td>' +
                '<td>' +
                    '<div style="font-weight: 600;">' + (step.step_name || step.event_name) + '</div>' +
                    '<div style="font-size: 0.72rem; color: #6b7280;">event: ' + step.event_name + '</div>' +
                '</td>' +
                '<td style="font-weight: 700;">' + Number(step.unique_users_count).toLocaleString() + '</td>' +
                '<td style="color: #9ca3af;">' + Number(step.total_events).toLocaleString() + '</td>' +
                '<td><span class="kpi-tag ' + tagClass + '">' + stepCr + '%</span></td>' +
                '<td>' +
                    '<div style="display: flex; align-items: center; gap: 8px;">' +
                        '<span style="font-weight: 600; min-width: 42px;">' + overallCr + '%</span>' +
                        '<div class="progress-bar-bg" style="flex: 1; max-width: 120px;">' +
                            '<div class="progress-bar-fill" style="width: ' + overallCr + '%;"></div>' +
                        '</div>' +
                    '</div>' +
                '</td>' +
                '<td style="color: ' + dropColor + ';">' + dropText + '</td>';
            tableTbody.appendChild(tr);
        });
    </script>
</body>
</html>
"""

    replacements = {
        "__DATA_SOURCE__": data_source,
        "__GENERATED_TIMESTAMP__": generated_timestamp,
        "__TOTAL_USERS__": f"{total_users:,}",
        "__NEW_USERS_TODAY__": str(latest_growth.get("new_registrations_count", 0)),
        "__CURRENT_DAU__": f"{current_dau:,}",
        "__CURRENT_WAU__": f"{current_wau:,}",
        "__CURRENT_MAU__": f"{current_mau:,}",
        "__STICKINESS_PCT__": str(stickiness_pct),
        "__OVERALL_FUNNEL_CR__": str(overall_funnel_cr),
        "__FUNNEL_TOP_USERS__": str(funnel_top_users),
        "__FUNNEL_BOTTOM_USERS__": str(funnel_bottom_users),
        "__CURRENCY__": currency,
        "__TOTAL_GROSS_REV__": f"{total_gross_rev:,.2f}",
        "__TOTAL_SUCCESSFUL_TX__": str(total_successful_tx),
        "__TOTAL_TX_COUNT__": str(total_tx_count),
        "__AVG_AOV__": f"{avg_aov:,.2f}",
        "__FUNNEL_STEPS_COUNT__": str(len(event_funnel)),
        "__JSON_GROWTH__": json_growth,
        "__JSON_FUNNEL__": json_funnel,
        "__JSON_REVENUE__": json_revenue,
        "__JSON_PLATFORM__": json_platform,
        "__JSON_PLATFORM_TOTALS__": json_platform_totals,
    }

    final_html = raw_template
    for placeholder, val in replacements.items():
        final_html = final_html.replace(placeholder, val)

    return final_html


def main() -> Path:
    """Main dashboard generator entrypoint."""
    logger.info("=== Business Flows Telemetry - HTML Dashboard Generator ===")
    pipeline_dir = Path(__file__).resolve().parent
    duckdb_path = find_duckdb_path()

    if duckdb_path and duckdb_path.exists():
        logger.info("Using DuckDB file at: %s", duckdb_path)
        data = query_duckdb_marts(duckdb_path)
    else:
        logger.warning("No analytics.duckdb file found. Using mock telemetry data.")
        data = generate_mock_data()

    html_content = build_dashboard_html(data)
    output_path = pipeline_dir / "dashboard.html"

    logger.info("Writing standalone HTML dashboard to: %s", output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    file_size_kb = output_path.stat().st_size / 1024
    logger.info("Dashboard HTML successfully generated! File size: %.2f KB at %s", file_size_kb, output_path)
    return output_path


if __name__ == "__main__":
    main()
