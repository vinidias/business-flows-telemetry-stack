"""Run the consultant signup report against the configured local database only."""

import json
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect, text

from extract import (
    build_database_engine,
    extract_table_to_parquet,
    load_environment,
    register_in_duckdb,
)
from generate_registration_dashboard import main as generate_dashboard


def main() -> int:
    root = Path(__file__).resolve().parent
    load_environment()
    if os.getenv("USE_MOCK_DATA", "").lower() in ("true", "1", "yes"):
        print("Remove USE_MOCK_DATA para executar com cadastros reais.", file=sys.stderr)
        return 1

    engine = build_database_engine()
    try:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            print(
                f"Banco local indisponível ({type(exc).__name__}). "
                "Inicie o serviço de banco configurado em pipeline/.env e tente novamente.",
                file=sys.stderr,
            )
            return 1
        columns = {column["name"] for column in inspect(engine).get_columns("users")}
        required = {"professional_category_id", "professional_registration"}
        if not required.issubset(columns):
            print(
                "A tabela users não contém os campos de especialidade e registro profissional: "
                + ", ".join(sorted(required - columns)),
                file=sys.stderr,
            )
            return 1
        raw_dir = root / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        snapshot = extract_table_to_parquet(engine, "users", raw_dir)
        if snapshot is None:
            return 1
    finally:
        engine.dispose()

    database = Path(os.getenv("DUCKDB_PATH", str(root / "analytics.duckdb"))).resolve()
    register_in_duckdb({"users": snapshot}, database)
    dbt = Path(sys.executable).with_name("dbt.exe" if os.name == "nt" else "dbt")
    dbt_command = str(dbt) if dbt.exists() else "dbt"
    for operation, selector in (("run", "+mart_consultant_registrations"),
                                ("test", "mart_consultant_registrations")):
        result = subprocess.run(
            [dbt_command, operation, "--profiles-dir", ".", "--select", selector],
            cwd=root / "analytics",
            check=False,
        )
        if result.returncode:
            return result.returncode
    marker = root / "data" / "source.json"
    marker.write_text(json.dumps({"source": "database"}), encoding="utf-8")
    generate_dashboard()
    return 0


if __name__ == "__main__":
    sys.exit(main())
