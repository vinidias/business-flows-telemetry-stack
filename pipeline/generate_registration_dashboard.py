"""Build the local consultant registration dashboard and searchable detail card."""

import html
import json
import os
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import duckdb

LABELS = {"active": "Ativo", "inactive": "Inativo", "pending": "Pendente",
          "verified": "Verificado", "unverified": "Não verificado", "unknown": "Indisponível"}


def detail_card(rows):
    if rows is None:
        return "<section><h2>Consulta de cadastros</h2><p>Atualize a extração para carregar os atributos individuais.</p></section>"
    filters = []
    for key, label in (("category", "Área"), ("status", "Status"), ("documents", "Documentos"), ("email", "E-mail"), ("pix", "Pix")):
        values = sorted({str(row[key]) for row in rows})
        options = "".join(f'<option value="{html.escape(value, quote=True)}">{html.escape(LABELS.get(value, value))}</option>' for value in values)
        filters.append(f'<label>{label}<select data-filter="{key}"><option value="">Todos</option>{options}</select></label>')
    body = []
    for row in rows:
        attrs = " ".join(f'data-{key}="{html.escape(str(row[key]), quote=True)}"' for key in ("category", "status", "documents", "email", "pix"))
        cells = [row["user_id"], row["registration"] or "Não informado", row["category"], row["registered_at"][:10]]
        cells += [LABELS.get(row[key], "Indisponível") for key in ("status", "documents", "email", "pix")]
        body.append(f'<tr {attrs}>' + "".join(f'<td>{html.escape(str(value))}</td>' for value in cells) + '</tr>')
    return f'''<section id="registration-query"><h2>Consulta de cadastros</h2>
<p>Filtre os cadastros dos últimos 30 dias. A verificação de documentos exige aprovação de todos os documentos obrigatórios. Pix indisponível significa que a fonte não informou uma verificação.</p>
<div class="filters"><label>CRM, registro ou ID<input id="registration-search" type="search" placeholder="Buscar registro ou ID"></label>{''.join(filters)}<label>De<input id="registration-from" type="date"></label><label>Até<input id="registration-to" type="date"></label></div>
<div class="scroll"><table id="registration-details"><thead><tr><th>ID</th><th>CRM / registro profissional</th><th>Área</th><th>Data de cadastro</th><th>Status</th><th>Documentos</th><th>E-mail</th><th>Pix</th></tr></thead><tbody>{''.join(body)}</tbody></table></div>
<p id="query-count" role="status" aria-live="polite">{len(rows)} cadastros</p>
<p id="query-empty" hidden>Nenhum cadastro encontrado para os filtros selecionados.</p>
<button id="query-prev" type="button">Anterior</button> <button id="query-next" type="button">Próxima</button>
</section>'''


QUERY_SCRIPT = """<script>
(() => {
  const card = document.getElementById('registration-query');
  if (!card) return;
  const rows = Array.from(card.querySelectorAll('tbody tr'));
  const filters = Array.from(card.querySelectorAll('[data-filter]'));
  const search = document.getElementById('registration-search');
  const previous = document.getElementById('query-prev');
  const next = document.getElementById('query-next');
  const from = document.getElementById('registration-from');
  const to = document.getElementById('registration-to');
  let page = 0;
  const update = () => {
    const term = search.value.trim().toLocaleLowerCase('pt-BR');
    const matches = rows.filter(row =>
      (row.cells[0].textContent + ' ' + row.cells[1].textContent).toLocaleLowerCase('pt-BR').includes(term) &&
      filters.every(filter => !filter.value || row.dataset[filter.dataset.filter] === filter.value) &&
      (!from.value || row.cells[3].textContent >= from.value) &&
      (!to.value || row.cells[3].textContent <= to.value));
    const pages = Math.max(1, Math.ceil(matches.length / 25));
    page = Math.min(page, pages - 1);
    rows.forEach(row => { row.hidden = true; });
    matches.slice(page * 25, (page + 1) * 25).forEach(row => { row.hidden = false; });
    document.getElementById('query-count').textContent = `${matches.length} cadastros encontrados · página ${page + 1} de ${pages}`;
    previous.disabled = page === 0;
    next.disabled = page + 1 >= pages;
    document.getElementById('query-empty').hidden = matches.length > 0;
  };
  search.addEventListener('input', () => { page = 0; update(); });
  filters.forEach(filter => filter.addEventListener('change', () => { page = 0; update(); }));
  [from, to].forEach(filter => filter.addEventListener('change', () => { page = 0; update(); }));
  previous.addEventListener('click', () => { page--; update(); });
  next.addEventListener('click', () => { page++; update(); });
  update();
})();
</script>"""


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


def render(rows: list[dict], source: str, days: int = 30, details_rows=None, generated_at=None) -> str:
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
            ("Cadastros inativos", statuses["inactive"]),
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
.filters{{display:flex;flex-wrap:wrap;gap:.75rem;margin:1rem 0}} label{{display:flex;flex-direction:column;gap:.3rem;font-size:.85rem}}
input,select,button{{font:inherit;padding:.6rem;border:1px solid #c6cfdd;border-radius:6px;background:#fff;color:#172033}}
button{{cursor:pointer}} button:disabled{{opacity:.45;cursor:default}} #registration-details td{{text-align:left;white-space:nowrap}}
</style></head><body><main>
<h1>Cadastros de consultores</h1><p>Últimos {days} dias · agregado por área de formação.</p>
<span class="source">{source_label}</span><p>{html.escape(note)}</p>
<p>Extração: {html.escape(generated_at or 'horário não disponível')} · Retrato da base no momento da extração.</p>
<div class="cards">{cards}</div>
<section><h2>Por área de formação</h2><div class="scroll">{make_table(aggregate(rows, 'category'), 'Área')}</div></section>
<section><h2>Por dia</h2><div class="scroll">{make_table(aggregate(rows, 'date'), 'Data')}</div></section>
<p>CRM informado indica apenas um valor com prefixo CRM e dígitos; não verifica o registro em conselho profissional.</p>
{detail_card(details_rows)}
</main>{QUERY_SCRIPT}</body></html>"""


def main() -> None:
    root = Path(__file__).resolve().parent
    database = Path(os.getenv("DUCKDB_PATH", str(root / "analytics.duckdb"))).resolve()
    marker = root / "data" / "source.json"
    source = json.loads(marker.read_text(encoding="utf-8")).get("source", "unknown") if marker.exists() else "unknown"
    output = root / "registration_dashboard.html"
    details_path = root / "data" / "registration_details.json"
    details = None
    if details_path.exists():
        bundle = json.loads(details_path.read_text(encoding="utf-8"))
        if bundle.get("source") == source:
            cutoff = (date.today() - timedelta(days=29)).isoformat()
            details = sorted([row for row in bundle["rows"] if cutoff <= row["registered_at"][:10] <= date.today().isoformat()], key=lambda row: row["registered_at"], reverse=True)
    output.write_text(render(load_rows(database), source, details_rows=details), encoding="utf-8")
    print(f"Generated {output} ({source})")


if __name__ == "__main__":
    main()
