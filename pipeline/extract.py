"""
==============================================================================
Business Flows Telemetry Stack - Generic Data Extractor
==============================================================================
Extracts business and telemetry data from relational sources (MySQL / PostgreSQL),
saves local columnar Parquet snapshots, and registers raw tables into DuckDB.

Usage:
    python extract.py
==============================================================================
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

import duckdb
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("DataExtractor")


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
    logger.info("Loaded environment from system environment / default .env")


def build_database_engine() -> Engine:
    """
    Construct SQLAlchemy Engine for MySQL or PostgreSQL based on DB_DRIVER.

    Returns:
        Engine: Connected SQLAlchemy engine.
    """
    driver = (os.getenv("DB_DRIVER") or "mysql").lower().strip()
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306" if driver == "mysql" else "5432")
    database = os.getenv("DB_NAME", "analytics_source")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", "")

    encoded_password = quote_plus(password)

    if driver == "mysql":
        connection_url = f"mysql+pymysql://{user}:{encoded_password}@{host}:{port}/{database}?charset=utf8mb4"
    elif driver in ("postgres", "postgresql"):
        connection_url = f"postgresql+psycopg2://{user}:{encoded_password}@{host}:{port}/{database}"
    else:
        raise ValueError(
            f"Unsupported DB_DRIVER: '{driver}'. Supported drivers are 'mysql' or 'postgresql'."
        )

    logger.info("Connecting to %s database at %s:%s/%s (user: %s)", driver.upper(), host, port, database, user)
    
    engine = create_engine(
        connection_url,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={"connect_timeout": 15} if driver == "mysql" else {"connect_timeout": 15},
    )
    return engine


def get_target_tables(engine: Engine) -> List[str]:
    """
    Determine the list of tables to extract.
    If DB_TABLES is defined in .env, use that list; otherwise query inspection.

    Args:
        engine: Database engine.

    Returns:
        List of table names.
    """
    configured_tables = os.getenv("DB_TABLES")
    if configured_tables:
        tables = [t.strip() for t in configured_tables.split(",") if t.strip()]
        logger.info("Using configured tables from DB_TABLES: %s", tables)
        return tables

    # Default fallback list for standard business telemetry
    default_tables = ["users", "analytics_events", "transactions"]
    
    inspector = inspect(engine)
    available_tables = inspector.get_table_names()
    logger.info("Available tables in source database: %s", available_tables)

    matching_tables = [t for t in default_tables if t in available_tables]
    if matching_tables:
        return matching_tables
    
    # If standard tables are not present, return all available tables
    return available_tables


def extract_table_to_parquet(
    engine: Engine,
    table_name: str,
    output_dir: Path,
) -> Optional[Path]:
    """
    Extract a single table from database into local Parquet file.

    Args:
        engine: SQLAlchemy engine.
        table_name: Name of table to extract.
        output_dir: Path to directory where parquet file will be saved.

    Returns:
        Path to generated Parquet file, or None if failed.
    """
    start_time = time.time()
    parquet_path = output_dir / f"{table_name}.parquet"
    
    logger.info("Extracting table: '%s'...", table_name)
    query = f"SELECT * FROM {table_name}"
    
    try:
        df = pd.read_sql(query, con=engine)
        elapsed = time.time() - start_time
        logger.info(
            "Extracted %d rows and %d columns from '%s' in %.2fs",
            len(df),
            len(df.columns),
            table_name,
            elapsed,
        )
        
        # Save to Parquet format (Snappy compression for fast columnar reads)
        df.to_parquet(parquet_path, engine="pyarrow", index=False, compression="snappy")
        logger.info("Saved Parquet snapshot to: %s", parquet_path)
        return parquet_path
    except Exception as e:
        logger.error("Failed to extract table '%s': %s", table_name, str(e))
        return None


def generate_mock_dataset(raw_data_dir: Path) -> dict:
    """Generate synthetic sample dataset for demo / CI runs when database is unavailable."""
    import datetime
    import random
    
    raw_data_dir = Path(raw_data_dir)
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Generating synthetic demo dataset (users, analytics_events, transactions)...")
    now = datetime.datetime.now()
    
    # 1. Users
    user_ids = list(range(1, 51))
    users_data = []
    platforms = ["ios", "android", "web"]
    roles = ["customer", "provider", "admin"]
    statuses = ["active", "pending", "inactive"]
    
    for u_id in user_ids:
        reg_time = now - datetime.timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
        users_data.append({
            "id": u_id,
            "user_id": str(u_id),
            "name": f"User {u_id}",
            "email": f"user{u_id}@example.com",
            "role": random.choice(roles),
            "status": random.choice(statuses),
            "platform": random.choice(platforms),
            "country_code": "BR",
            "created_at": reg_time,
            "updated_at": reg_time,
        })
    df_users = pd.DataFrame(users_data)
    users_parquet = raw_data_dir / "users.parquet"
    df_users.to_parquet(users_parquet, engine="pyarrow", index=False)
    
    # 2. Analytics Events
    events_data = []
    event_names = ["screen_view", "button_click", "signup_started", "signup_completed", "item_viewed", "checkout_started", "purchase_completed"]
    event_categories = ["navigation", "interaction", "conversion"]
    
    for e_id in range(1, 301):
        ev_time = now - datetime.timedelta(days=random.randint(0, 14), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        u_id = random.choice(user_ids)
        ev_name = random.choice(event_names)
        events_data.append({
            "id": e_id,
            "user_id": str(u_id),
            "session_id": f"sess_{random.randint(100, 999)}",
            "event_name": ev_name,
            "event_category": random.choice(event_categories),
            "platform": random.choice(platforms),
            "app_version": "1.0.0",
            "properties_json": '{"source": "demo"}',
            "created_at": ev_time,
        })
    df_events = pd.DataFrame(events_data)
    events_parquet = raw_data_dir / "analytics_events.parquet"
    df_events.to_parquet(events_parquet, engine="pyarrow", index=False)
    
    # 3. Transactions
    tx_data = []
    pay_methods = ["credit_card", "pix", "paypal"]
    statuses_tx = ["completed", "pending", "failed"]
    
    for t_id in range(1, 61):
        tx_time = now - datetime.timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))
        u_id = random.choice(user_ids)
        amount = round(random.uniform(15.0, 350.0), 2)
        tx_data.append({
            "id": t_id,
            "user_id": str(u_id),
            "amount": amount,
            "currency": "BRL",
            "status": random.choice(statuses_tx),
            "payment_method": random.choice(pay_methods),
            "created_at": tx_time,
            "updated_at": tx_time,
        })
    df_tx = pd.DataFrame(tx_data)
    tx_parquet = raw_data_dir / "transactions.parquet"
    df_tx.to_parquet(tx_parquet, engine="pyarrow", index=False)
    
    return {
        "users": users_parquet,
        "analytics_events": events_parquet,
        "transactions": tx_parquet,
    }


def register_in_duckdb(
    parquet_files: dict,
    duckdb_path: Path,
) -> None:
    """
    Register extracted Parquet files inside DuckDB as raw tables/views for dbt transformation.

    Args:
        parquet_files: Dict mapping table_name -> parquet file path.
        duckdb_path: Path to DuckDB database file.
    """
    logger.info("Connecting to DuckDB at: %s", duckdb_path)
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    
    con = duckdb.connect(str(duckdb_path))
    try:
        # Ensure 'raw' schema exists for dbt source mapping
        con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
        for table_name, p_file in parquet_files.items():
            posix_path = p_file.as_posix()
            raw_table_name = f"raw_{table_name}"
            # Register in both raw schema and default schema for maximum compatibility
            con.execute(f"CREATE OR REPLACE TABLE raw.{raw_table_name} AS SELECT * FROM read_parquet('{posix_path}');")
            con.execute(f"CREATE OR REPLACE TABLE {raw_table_name} AS SELECT * FROM read_parquet('{posix_path}');")
            count_result = con.execute(f"SELECT COUNT(*) FROM raw.{raw_table_name};").fetchone()
            count = count_result[0] if count_result else 0
            logger.info("Registered DuckDB table 'raw.%s' with %d rows from '%s'", raw_table_name, count, p_file.name)
    finally:
        con.close()


def run_extraction() -> bool:
    """
    Main extraction coordinator.

    Returns:
        bool: True if successful, False otherwise.
    """
    logger.info("=== Starting Business Flows Data Extraction ===")
    load_environment()

    raw_data_dir = Path(os.getenv("RAW_DATA_PATH", "./data/raw")).resolve()
    raw_data_dir.mkdir(parents=True, exist_ok=True)

    duckdb_file = Path(os.getenv("DUCKDB_PATH", "./analytics.duckdb")).resolve()

    use_mock = os.getenv("USE_MOCK_DATA", "").lower() in ("true", "1", "yes")
    extracted_files = {}

    if not use_mock:
        try:
            engine = build_database_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Database connectivity test successful.")
            
            tables = get_target_tables(engine)
            for table in tables:
                p_path = extract_table_to_parquet(engine, table, raw_data_dir)
                if p_path:
                    extracted_files[table] = p_path
        except Exception as e:
            logger.warning("Database connection unavailable (%s). Falling back to synthetic demo dataset generation.", str(e))
            use_mock = True

    if use_mock or not extracted_files:
        extracted_files = generate_mock_dataset(raw_data_dir)

    if extracted_files:
        register_in_duckdb(extracted_files, duckdb_file)
        logger.info("=== Extraction completed successfully (%d tables processed) ===", len(extracted_files))
        return True
    else:
        logger.error("No tables were successfully extracted.")
        return False


if __name__ == "__main__":
    success = run_extraction()
    sys.exit(0 if success else 1)
