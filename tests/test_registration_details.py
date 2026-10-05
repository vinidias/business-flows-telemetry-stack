"""Verify source semantics and safe rendering of the individual signup query."""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from registration_details import extract_details
from generate_registration_dashboard import detail_card


def source(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'source.db'}")
    pd.DataFrame([
        {"id": 1, "user_type": "provider", "status": 0, "created_at": "2026-10-05", "professional_category_id": 7, "professional_registration": "CRM 12345/SP", "is_email_verified": 0, "email_verified_at": "2026-10-01", "email": "private@example.test"},
        {"id": 2, "user_type": "provider", "status": 1, "created_at": "2026-10-05", "professional_category_id": 7, "professional_registration": "CREA 98765", "is_email_verified": 1},
        {"id": 3, "user_type": "customer", "status": 1, "created_at": "2026-10-05"},
    ]).to_sql("users", engine, index=False)
    pd.DataFrame([{"id": 7, "name": "Agronomia"}]).to_sql("categories", engine, index=False)
    pd.DataFrame([
        {"id": 10, "is_required": 1, "status": 1, "type": "provider_document", "deleted_at": None},
        {"id": 11, "is_required": 1, "status": 1, "type": "provider_document", "deleted_at": None},
        {"id": 12, "is_required": 1, "status": 1, "type": "provider_document", "deleted_at": "2026-10-01"},
    ]).to_sql("documents", engine, index=False)
    pd.DataFrame([
        {"provider_id": 1, "document_id": 10, "is_verified": 1, "deleted_at": None},
        {"provider_id": 1, "document_id": 11, "is_verified": 1, "deleted_at": "2026-10-01"},
        {"provider_id": 2, "document_id": 10, "is_verified": 1, "deleted_at": None},
        {"provider_id": 2, "document_id": 11, "is_verified": 1, "deleted_at": None},
    ]).to_sql("provider_documents", engine, index=False)
    pd.DataFrame([{"provider_id": 1, "status": 1, "pix_key": "private-key"}]).to_sql("banks", engine, index=False)
    return engine


def test_detail_query_requires_actual_verification(tmp_path):
    rows = extract_details(source(tmp_path))
    assert len(rows) == 2
    first, second = rows
    assert first["registration"] == "CRM 12345/SP"
    assert first["category"] == "Agronomia"
    assert first["status"] == "inactive"
    assert first["documents"] == "unverified"  # Deleted approval cannot count.
    assert second["documents"] == "verified"
    assert first["email"] == "unverified"  # Flag takes precedence over timestamp.
    assert second["email"] == "verified"
    assert first["pix"] == "unknown"  # Active bank + key is insufficient.
    assert "private-key" not in str(rows)
    assert "private@example.test" not in str(rows)


def test_detail_card_escapes_values_and_exposes_requested_columns(tmp_path):
    rows = extract_details(source(tmp_path))
    rows[0]["registration"] = '<script>alert("x")</script>'
    rows[0]["category"] = '\"><img src=x onerror=alert(1)>'
    markup = detail_card(rows)
    assert '<script>alert' not in markup
    assert '<img src=' not in markup
    assert '&lt;script&gt;' in markup
    for label in ("CRM / registro profissional", "Data de cadastro", "Documentos", "E-mail", "Pix", "Inativo"):
        assert label in markup
