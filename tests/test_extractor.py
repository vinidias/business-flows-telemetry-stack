"""
Unit tests for pipeline/extract.py.
Tests mock dataset generation, Parquet export, DuckDB registration, and engine helpers.
"""

import os
import sys
from pathlib import Path
import duckdb
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = REPO_ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

try:
    from extract import (
        generate_mock_dataset,
        extract_table_to_parquet,
        register_in_duckdb,
        get_target_tables,
        build_database_engine,
    )
except ImportError:
    from pipeline.extract import (
        generate_mock_dataset,
        extract_table_to_parquet,
        register_in_duckdb,
        get_target_tables,
        build_database_engine,
    )


class TestGenerateMockDataset:
    """Tests for synthetic data generation and Parquet serialization."""

    def test_generates_all_expected_parquet_files(self, tmp_path):
        """Verify that users, events, and transactions parquet files are created."""
        result = generate_mock_dataset(tmp_path)

        assert isinstance(result, dict)
        assert "users" in result
        assert "analytics_events" in result
        assert "transactions" in result

        for table_name, file_path in result.items():
            assert isinstance(file_path, Path)
            assert file_path.exists()
            assert file_path.suffix == ".parquet"
            assert file_path.stat().st_size > 0

    def test_mock_users_parquet_schema_and_content(self, tmp_path):
        """Verify users table structure and data validity."""
        result = generate_mock_dataset(tmp_path)
        df_users = pd.read_parquet(result["users"])

        expected_cols = {
            "id",
            "user_id",
            "name",
            "email",
            "role",
            "status",
            "platform",
            "country_code",
            "created_at",
            "updated_at",
        }
        assert expected_cols.issubset(set(df_users.columns))
        assert len(df_users) == 50
        assert df_users["id"].nunique() == 50
        assert df_users["country_code"].iloc[0] == "BR"
        assert set(df_users["platform"].unique()).issubset({"ios", "android", "web"})

    def test_mock_events_parquet_schema_and_content(self, tmp_path):
        """Verify analytics_events table structure and data validity."""
        result = generate_mock_dataset(tmp_path)
        df_events = pd.read_parquet(result["analytics_events"])

        expected_cols = {
            "id",
            "user_id",
            "session_id",
            "event_name",
            "event_category",
            "platform",
            "app_version",
            "properties_json",
            "created_at",
        }
        assert expected_cols.issubset(set(df_events.columns))
        assert len(df_events) == 300
        assert "purchase_completed" in df_events["event_name"].values
        assert "signup_completed" in df_events["event_name"].values

    def test_mock_transactions_parquet_schema_and_content(self, tmp_path):
        """Verify transactions table structure and data validity."""
        result = generate_mock_dataset(tmp_path)
        df_tx = pd.read_parquet(result["transactions"])

        expected_cols = {
            "id",
            "user_id",
            "amount",
            "currency",
            "status",
            "payment_method",
            "created_at",
            "updated_at",
        }
        assert expected_cols.issubset(set(df_tx.columns))
        assert len(df_tx) == 60
        assert (df_tx["amount"] > 0).all()
        assert (df_tx["currency"] == "BRL").all()
        assert set(df_tx["payment_method"].unique()).issubset({"credit_card", "pix", "paypal"})


class TestExtractTableToParquet:
    """Tests for relational database table extraction to Parquet."""

    def test_extract_table_success(self, tmp_path):
        """Test extraction of a table using an SQLite engine."""
        db_file = tmp_path / "test_source.db"
        engine = create_engine(f"sqlite:///{db_file}")

        # Seed sample table
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE customers (id INT, name TEXT, balance REAL);"))
            conn.execute(
                text("INSERT INTO customers VALUES (1, 'Alice', 150.5), (2, 'Bob', 200.0);")
            )

        parquet_path = extract_table_to_parquet(engine, "customers", tmp_path)

        assert parquet_path is not None
        assert parquet_path.exists()
        assert parquet_path.name == "customers.parquet"

        df = pd.read_parquet(parquet_path)
        assert len(df) == 2
        assert list(df["name"]) == ["Alice", "Bob"]
        assert list(df["balance"]) == [150.5, 200.0]

    def test_extract_nonexistent_table_returns_none(self, tmp_path):
        """Test extraction of an unexisting table handles error gracefully."""
        db_file = tmp_path / "test_source.db"
        engine = create_engine(f"sqlite:///{db_file}")

        parquet_path = extract_table_to_parquet(engine, "non_existent_table", tmp_path)
        assert parquet_path is None


class TestRegisterInDuckDB:
    """Tests for Parquet to DuckDB raw table registration."""

    def test_registers_raw_tables_in_duckdb(self, tmp_path):
        """Verify registered DuckDB database contains raw schema and tables."""
        raw_files = generate_mock_dataset(tmp_path / "raw")
        duckdb_path = tmp_path / "analytics.duckdb"

        register_in_duckdb(raw_files, duckdb_path)

        assert duckdb_path.exists()
        con = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            users_count = con.execute("SELECT COUNT(*) FROM raw.raw_users;").fetchone()[0]
            events_count = con.execute("SELECT COUNT(*) FROM raw.raw_analytics_events;").fetchone()[0]
            tx_count = con.execute("SELECT COUNT(*) FROM raw.raw_transactions;").fetchone()[0]

            assert users_count == 50
            assert events_count == 300
            assert tx_count == 60

            # Default schema fallback compatibility
            users_fallback = con.execute("SELECT COUNT(*) FROM raw_users;").fetchone()[0]
            assert users_fallback == 50
        finally:
            con.close()


class TestExtractorHelpers:
    """Tests for target table selection and engine driver validation."""

    def test_get_target_tables_from_env(self, monkeypatch, tmp_path):
        """Verify DB_TABLES environment variable overrides default discovery."""
        monkeypatch.setenv("DB_TABLES", "custom_orders, custom_customers")
        db_file = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_file}")

        tables = get_target_tables(engine)
        assert tables == ["custom_orders", "custom_customers"]

    def test_build_database_engine_invalid_driver(self, monkeypatch):
        """Verify unsupported database driver raises ValueError."""
        monkeypatch.setenv("DB_DRIVER", "oracle")
        with pytest.raises(ValueError, match="Unsupported DB_DRIVER: 'oracle'"):
            build_database_engine()
