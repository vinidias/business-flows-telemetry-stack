"""Local registration detail export, separate from aggregate telemetry snapshots."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import inspect


def verification(value):
    if pd.isna(value):
        return "unknown"
    value = str(value).strip().lower()
    return "verified" if value in ("1", "1.0", "true") else "unverified" if value in ("0", "0.0", "false") else "unknown"


def prepare_details(users, category_names=None, documents=None, pix=None):
    names, documents, pix = category_names or {}, documents or {}, pix or {}
    rows = []
    for user in users.to_dict("records"):
        role = str(user.get("user_type", user.get("role", ""))).lower()
        if role not in ("provider", "consultant"):
            continue
        category = user.get("professional_category_id")
        category_id = None if pd.isna(category) else str(int(category)) if isinstance(category, (float, int)) else str(category)
        email = verification(user.get("is_email_verified"))
        if "is_email_verified" not in user and "email_verified_at" in user:
            email = "unverified" if pd.isna(user["email_verified_at"]) else "verified"
        registration = user.get("professional_registration")
        status = str(user.get("status", "unknown")).lower()
        rows.append({
            "user_id": str(user["id"]),
            "registration": "" if pd.isna(registration) else str(registration),
            "category": names.get(category_id, f"Área #{category_id}" if category_id else "Não informada"),
            "registered_at": str(user["created_at"]),
            "status": {"1": "active", "0": "inactive", "1.0": "active", "0.0": "inactive", "true": "active", "false": "inactive"}.get(status, status),
            "documents": documents.get(str(user["id"]), "unknown"),
            "email": email,
            "pix": pix.get(str(user["id"]), "unknown"),
        })
    return rows


def extract_details(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    quote = engine.dialect.identifier_preparer.quote

    def read(table, allowed):
        columns = {c["name"] for c in inspector.get_columns(table)}
        selected = [c for c in allowed if c in columns]
        query = f"SELECT {', '.join(quote(c) for c in selected)} FROM {quote(table)}"
        if "deleted_at" in columns:
            query += f" WHERE {quote('deleted_at')} IS NULL"
        return pd.read_sql(query, engine)

    users = read("users", ["id", "user_type", "role", "status", "created_at",
                           "professional_registration", "professional_category_id",
                           "is_email_verified", "email_verified_at"])
    names = {}
    if "categories" in tables:
        categories = read("categories", ["id", "name"])
        if {"id", "name"}.issubset(categories.columns):
            names = {str(row.id): str(row.name) for row in categories.itertuples()}
    documents = {}
    if {"documents", "provider_documents"}.issubset(tables):
        definitions = read("documents", ["id", "is_required", "status", "type"])
        uploads = read("provider_documents", ["provider_id", "document_id", "is_verified"])
        if {"id", "is_required", "status", "type"}.issubset(definitions.columns) and {"provider_id", "document_id", "is_verified"}.issubset(uploads.columns):
            required = set(definitions.loc[
                (definitions.is_required == 1) & (definitions.status == 1)
                & (definitions.type == "provider_document"), "id"])
            approved = uploads.loc[uploads.is_verified == 1].groupby("provider_id").document_id.agg(set).to_dict()
            documents = {str(uid): "verified" if required and required.issubset(approved.get(uid, set())) else "unverified" for uid in users.id}
    pix = {}
    if "banks" in tables:
        bank_columns = {c["name"] for c in inspector.get_columns("banks")}
        # Account status or presence of a Pix key is not proof of verification.
        if "provider_id" in bank_columns and {"is_pix_verified", "pix_verified_at"} & bank_columns:
            banks = read("banks", ["provider_id", "is_pix_verified", "pix_verified_at"])
            for uid, group in banks.groupby("provider_id"):
                results = group.is_pix_verified.map(verification) if "is_pix_verified" in group else group.pix_verified_at.map(lambda v: "unverified" if pd.isna(v) else "verified")
                pix[str(uid)] = "verified" if "verified" in set(results) else "unverified" if set(results) == {"unverified"} else "unknown"
    return prepare_details(users, names, documents, pix)


def save_details(raw_dir: Path, rows, source):
    path = Path(raw_dir).parent / "registration_details.json"
    path.write_text(json.dumps({"source": source, "generated_at": datetime.now(timezone.utc).isoformat(), "rows": rows}, ensure_ascii=False), encoding="utf-8")
