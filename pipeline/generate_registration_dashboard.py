"""Build a local, aggregate-only consultant registration dashboard from DuckDB."""

import html
import json
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import duckdb


def load_rows(database: Path, days: int = 30) -> list[dict]:
    cutoff = date.today() - timedelta(days=days - 1)
    with duckdb.connect(str(database), read_only=True) as con:
        rows = con.execute(
            """
            SELECT metric_date, professional_category_name, user_status,
                   registrations_count, crm_informed_count,
                   other_registration_count, registration_missing_count
            FROM mart_consultant_registrations
            WHERE metric_date >= ?
            ORDER BY metric_date, professional_category_name, user_status
            """,
            [cutoff],
        ).fetchall()
    return [
        dict(zip(("date", "category", "status", "registrations", "crm", "other", "missing"), row))
        for row in rows
    ]


def aggregate(rows: list[dict], dimension: str) -> list[tuple]:
    totals = defaultdict(lambda: [0, 0, 0, 0])
    for row in rows:
        counts = totals[str(row[dimension])]
        for index, field in enumerate(("registrations", "crm", "other", "missing")):
            counts[index] += int(row[field] or 0)
    return sorted(totals.items(), key=lambda item: (-item[1][0], item[0]))


def make_table(rows: list[tuple], first_heading: str) -> str:
    body = "".join(
        "<tr><th scope='row'>%s</th><td>%d</td><td>%d</td><td>%d</td><td>%d</td></tr>"
        % (html.escape(str(name)), *counts)
        for name, counts in rows
    )
    return (
        "<table><thead><tr><th>%s</th><th>Cadastros</th><th>CRM informado</th>"
        "<th>Outro registro</th><th>Sem registro</th></tr></thead><tbody>%s</tbody></table>"
        % (html.escape(first_heading), body or "<tr><td colspan='5'>Sem dados neste período.</td></tr>")
    )


def render(rows: list[dict], source: str, days: int = 30) -> str:
    totals = [sum(int(row[field] or 0) for row in rows) for field in
              ("registrations", "crm", "other", "missing")]
    statuses = defaultdict(int)
    for row in rows:
        statuses[str(row["status"])] += int(row["registrations"] or 0)
    is_demo = source != "database"
    source_label = "DADOS DE DEMONSTRAÇÃO" if is_demo else "DADOS DO BANCO CONFIGURADO"
    note = (
        "A fonte de usuários não trouxe as colunas professional_category_id e "
        "professional_registration, ou não há cadastros de consultores neste período."
        if not rows and not is_demo else ""
    )
    cards = "".join(
        f"<article><small>{html.escape(label)}</small><strong>{value}</strong></article>"
        for label, value in (
            ("Consultores cadastrados", totals[0]),
            ("CRM informado", totals[1]),
            ("Outro registro", totals[2]),
            ("Sem registro", totals[3]),
            ("Cadastros ativos", statuses["active"]),
            ("Cadastros pendentes", statuses["pending"]),
        )
    )
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cadastros de consultores — Propaga</title>
<style>
body{{font:16px system-ui,sans-serif;background:#f5f7fb;color:#172033;margin:0;padding:2rem}}
main{{max-width:1100px;margin:auto}} h1{{margin-bottom:.2rem}} p{{color:#526078}}
.source{{display:inline-block;border-radius:20px;background:{'#fff1cf' if is_demo else '#d9f4e4'};padding:.45rem .8rem;font-weight:700;font-size:.8rem}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8rem;margin:1.5rem 0}}
article,section{{background:#fff;border:1px solid #dce3ee;border-radius:12px;padding:1rem;margin-bottom:1rem}}
article small{{display:block;color:#526078}} article strong{{display:block;font-size:1.8rem;margin-top:.35rem}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:.55rem;border-bottom:1px solid #e5e9f1;text-align:right}}
th:first-child,td:first-child{{text-align:left}} .scroll{{overflow:auto}}
</style></head><body><main>
<h1>Cadastros de consultores</h1><p>Últimos {days} dias · agregado por área de formação.</p>
<span class="source">{source_label}</span><p>{html.escape(note)}</p>
<div class="cards">{cards}</div>
<section><h2>Por área de formação</h2><div class="scroll">{make_table(aggregate(rows, 'category'), 'Área')}</div></section>
<section><h2>Por dia</h2><div class="scroll">{make_table(aggregate(rows, 'date'), 'Data')}</div></section>
<p>CRM informado indica apenas um valor com prefixo CRM e dígitos; não verifica o registro em conselho profissional. Nenhum número é exibido ou armazenado na análise.</p>
</main></body></html>"""


def main() -> None:
    root = Path(__file__).resolve().parent
    database = Path(os.getenv("DUCKDB_PATH", str(root / "analytics.duckdb"))).resolve()
    marker = root / "data" / "source.json"
    source = json.loads(marker.read_text(encoding="utf-8")).get("source", "unknown") if marker.exists() else "unknown"
    output = root / "registration_dashboard.html"
    output.write_text(render(load_rows(database), source), encoding="utf-8")
    print(f"Generated {output} ({source})")


if __name__ == "__main__":
    main()
