#!/usr/bin/env python3
"""
Reconstrói o objeto `const D = {...}` do dashboard_cessao.html a partir
das planilhas de apoio Receitas.xlsx / Despesas.xlsx.

Uso:
    python3 build_dashboard_cessao.py \
        --despesas caminho/Despesas.xlsx \
        --receitas caminho/Receitas.xlsx \
        [--out saida.json]           # só gera o JSON, não mexe no HTML
        [--patch-html caminho.html]  # substitui o `const D = ...;` nesse arquivo

Sem --patch-html, o script só imprime/salva o JSON (modo de validação).

Ver dashboard_cessao_lib.py e dashboard_cessao_aggregate.py para a lógica
de transformação, e o relatório da tarefa para o que foi validado com
exatidão vs. aproximado (ex.: `d.tancagem` não é derivável destas
planilhas — depende de capacidade física de tanques, dado externo — e é
mantido igual ao que já está no HTML atual).
"""

import argparse
import json
import sys

import openpyxl

from dashboard_cessao_lib import read_rows, build_periods
from dashboard_cessao_aggregate import (
    aggregate_monthly, build_contracts, aggregate_filial, aggregate_cong,
    build_kpi, build_top_data, build_topmon, build_sinergia,
)
from dashboard_cessao_insights import (
    build_despesa_insights, build_receita_insights, build_last_month_insight,
)

DESPESA_COLMAP = {
    "data": "DATA CONTABIL", "filial": "FILIAL", "congenere": "CONGENERE",
    "tipo": "TIPO DE COBRANÇA", "orc": "ORC.TOTAL", "valor_total": "Valor Total R$",
    "vol_mov": "Vol. Movimentado M³", "vol_minimo": "Volume Mínimo ",
    "vol_1giro": "Volume 1º Giro", "tarifa_1giro": "Tarifa 1º Giro",
    "tarifa_2giro": "Tarifa 2º Giro", "tarifa_efetiva": "Tarifa Efetiva",
    "valor_contrato": "Valor Contrato", "valor_movimentado": "Valor Movimentado",
    "top_col": "Take or Pay", "vol_orc": "ORC.VOLUME GMR +TRANSF",
}

RECEITA_COLMAP = {
    "data": "DATA CONTABIL", "filial": "FILIAL", "congenere": "CONGENERE",
    "tipo": "TIPO DE COBRANÇA", "orc": "Valor Orçado", "valor_total": "Valor Total R$",
    "vol_mov": "Vol. Movimentado M³", "vol_minimo": "Volume Mínimo ",
    "vol_1giro": "Volume 1º Giro", "tarifa_1giro": "Tarifa 1º Giro",
    "tarifa_2giro": "Tarifa 2º Giro", "tarifa_efetiva": "Tarifa Efetiva",
    "valor_contrato": "Valor Contrato", "valor_movimentado": "Valor Movimentado",
    "vol_orc": "Volume Orçado",
    # Receitas.xlsx não tem coluna "Take or Pay" pronta; é calculada
    # (ver _row_top em dashboard_cessao_aggregate.py).
}


def load_rows(path, sheet_name, colmap):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb[sheet_name]
    header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    colmap_present = dict(colmap)
    if "Take or Pay" not in [str(h).strip() if h else h for h in header]:
        colmap_present.pop("top_col", None)
    rows = read_rows(ws, header, colmap_present)
    if "top_col" not in colmap_present:
        for r in rows:
            r["top_col"] = None
    return rows


def build_side(rows, lado, periods):
    monthly = aggregate_monthly(rows, periods)
    periods_set = set(periods)
    contracts = build_contracts(rows, lado, periods_set)
    filial = aggregate_filial(contracts, periods)
    cong = aggregate_cong(contracts, rows, periods)
    kpi = build_kpi(contracts, monthly)
    return monthly, contracts, filial, cong, kpi


def extract_tancagem_from_html(html_path):
    """d.tancagem depende de capacidade física de tancagem por base — não
    existe nenhuma coluna nas planilhas de Receitas/Despesas com essa
    informação. Reaproveita o bloco já existente no HTML atual em vez de
    inventar números."""
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return []

    idx = content.find("const D = ")
    if idx == -1:
        return []
    start = content.find("{", idx)
    i = start
    depth = 0
    in_string = False
    string_char = None
    escape = False
    while i < len(content):
        c = content[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == string_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                string_char = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    try:
        data = json.loads(content[start:i])
        return data.get("d", {}).get("tancagem", [])
    except Exception:
        return []


def build_dashboard_json(despesas_path, receitas_path, reference_html=None):
    d_rows = load_rows(despesas_path, "Despesas", DESPESA_COLMAP)
    r_rows = load_rows(receitas_path, "Receitas", RECEITA_COLMAP)

    periods = build_periods(d_rows + r_rows)

    d_monthly, d_contracts, d_filial, d_cong, d_kpi = build_side(d_rows, "D", periods)
    r_monthly, r_contracts, r_filial, r_cong, r_kpi = build_side(r_rows, "R", periods)

    d_top_data = build_top_data(d_contracts, d_monthly)
    r_topmon = build_topmon(r_contracts, "TOP Recebido")

    tancagem = extract_tancagem_from_html(reference_html) if reference_html else []

    # Insights: restritos a 2026 (o resto do dashboard segue com o
    # histórico completo, só os cards de insight são limitados ao ano
    # corrente).
    d_contracts_26 = [c for c in d_contracts if c["period"].startswith("2026")]
    r_contracts_26 = [c for c in r_contracts if c["period"].startswith("2026")]
    d_monthly_26 = [m for m in d_monthly if m["period"].startswith("2026")]
    r_monthly_26 = [m for m in r_monthly if m["period"].startswith("2026")]
    d_rows_26 = [r for r in d_rows if r["data"] and r["data"].year == 2026]
    r_rows_26 = [r for r in r_rows if r["data"] and r["data"].year == 2026]
    periods_26 = [p for p in periods if p.startswith("2026")]

    d_kpi_26 = build_kpi(d_contracts_26, d_monthly_26)
    r_kpi_26 = build_kpi(r_contracts_26, r_monthly_26)
    d_cong_26_all = aggregate_cong(d_contracts_26, d_rows_26, periods_26)["__all__"]

    d_filiais_26 = {c["filial"] for c in d_contracts_26}
    r_filiais_26 = {c["filial"] for c in r_contracts_26}
    d_insights = build_despesa_insights(
        d_contracts_26, d_kpi_26, r_kpi_26, d_cong_26_all, d_filiais_26, r_filiais_26
    )

    sinergia_26 = build_sinergia(d_contracts_26, r_contracts_26, d_rows_26, r_rows_26)
    r_topmon_26 = build_topmon(r_contracts_26, "TOP Recebido")
    r_insights = build_receita_insights(r_contracts_26, r_topmon_26, sinergia_26["bilaterais"])

    d_last_month = build_last_month_insight(d_contracts_26, d_monthly_26, "Despesas")
    if d_last_month:
        d_insights.append(d_last_month)
    r_last_month = build_last_month_insight(r_contracts_26, r_monthly_26, "Receitas")
    if r_last_month:
        r_insights.append(r_last_month)

    # `sinergia` (aba dedicada) continua com o histórico completo.
    sinergia = build_sinergia(d_contracts, r_contracts, d_rows, r_rows)

    D = {
        "periods": periods,
        "d": {
            "monthly": d_monthly, "filial": d_filial, "cong": d_cong,
            "contracts": d_contracts, "tancagem": tancagem,
            "top_data": d_top_data, "insights": d_insights, "kpi": d_kpi,
        },
        "r": {
            "monthly": r_monthly, "filial": r_filial, "cong": r_cong,
            "contracts": r_contracts, "topmon": r_topmon,
            "insights": r_insights, "kpi": r_kpi,
        },
        "sinergia": sinergia,
    }
    return D


def patch_html(html_path, D):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.find("const D = ")
    if idx == -1:
        raise RuntimeError("`const D = ` não encontrado em " + html_path)
    start = content.find("{", idx)
    i = start
    depth = 0
    in_string = False
    string_char = None
    escape = False
    while i < len(content):
        c = content[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == string_char:
                in_string = False
        else:
            if c in ('"', "'"):
                in_string = True
                string_char = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1

    new_json = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
    new_content = content[:start] + new_json + content[i:]
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--despesas", required=True)
    ap.add_argument("--receitas", required=True)
    ap.add_argument("--out")
    ap.add_argument("--patch-html")
    ap.add_argument("--reference-html", help="HTML de onde copiar d.tancagem (padrão: o próprio --patch-html)")
    args = ap.parse_args()

    reference_html = args.reference_html or args.patch_html
    D = build_dashboard_json(args.despesas, args.receitas, reference_html)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(D, f, ensure_ascii=False)
        print(f"JSON salvo em {args.out}", file=sys.stderr)

    if args.patch_html:
        patch_html(args.patch_html, D)
        print(f"HTML atualizado: {args.patch_html}", file=sys.stderr)

    if not args.out and not args.patch_html:
        json.dump(D, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
