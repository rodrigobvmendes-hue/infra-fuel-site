"""Monta o objeto `const CAP = {...};` embutido em dashboard_cessao.html
(aba "Capacidades") a partir dos CSVs tratados da aba Capacidade ALE.

Fontes:
- dados_tratados/capacidade_ale.csv       (grão Base x Produto)
- dados_tratados/capacidade_ale_top.csv   (TOP por base, mesmo grão)
- dados_tratados/capacidade_por_modelo.csv (papel operacional por base)

Uso:
    python3 scripts/build_capacidade_dashboard_data.py [--patch-html caminho.html]

Sem --patch-html, só imprime o JSON (modo de validação).
"""

import argparse
import csv
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRATADOS_DIR = BASE_DIR / "dados_tratados"

sys.path.insert(0, str(BASE_DIR / "scripts"))
from normalize import normalize_municipio  # noqa: E402

CAPACIDADE_CSV = TRATADOS_DIR / "capacidade_ale.csv"
TOP_CSV = TRATADOS_DIR / "capacidade_ale_top.csv"
PAPEL_CSV = TRATADOS_DIR / "capacidade_por_modelo.csv"


def _num(v):
    if v in (None, ""):
        return None
    return round(float(v), 3)


def build_cap_data():
    with CAPACIDADE_CSV.open(encoding="utf-8") as f:
        cap_rows = list(csv.DictReader(f))
    with TOP_CSV.open(encoding="utf-8") as f:
        top_rows = list(csv.DictReader(f))
    with PAPEL_CSV.open(encoding="utf-8") as f:
        papel_rows = list(csv.DictReader(f))

    # `codigo_base` não é uma chave estável entre abas (ver docstring de
    # build_capacidade_top.py) -- o join entre fontes usa `unidade`
    # normalizada. `capacidade_ale.csv` e `capacidade_ale_top.csv` vêm da
    # mesma extração e compartilham `codigo_base`, então esse par pode
    # usar a chave bruta; `capacidade_por_modelo.csv` vem de outra aba
    # (Detalhamento Tancagem) e precisa da chave normalizada.
    top_por_base = {r["codigo_base"]: r for r in top_rows}
    papeis_por_base = {}
    for r in papel_rows:
        chave = normalize_municipio(r["unidade"])
        papeis_por_base.setdefault(chave, []).append({
            "papel": r["papel_operacional"],
            "tancagem_m3": _num(r["tancagem_disponivel_movimentacao_m3"]),
        })

    bases = {}
    for r in cap_rows:
        cod = r["codigo_base"]
        base = bases.setdefault(cod, {
            "codigo_base": cod,
            "unidade": r["unidade"],
            "modelo_principal": r["modelo_operacional"],
            "produtos": [],
        })
        base["produtos"].append({
            "produto": r["produto"],
            "produto_misturado": r["produto_misturado"] or None,
            "tancagem_disponivel_m3": _num(r["tancagem_disponivel_m3"]),
            "capacidade_recebimento_rodo_m3": _num(r["capacidade_recebimento_rodo_m3"]),
            "capacidade_movimentacao_m3": _num(r["capacidade_movimentacao_m3"]),
            "capacidade_venda_m3": _num(r["capacidade_venda_m3"]),
            "capacidade_expedicao_rodo_m3": _num(r["capacidade_expedicao_rodo_m3"]),
            "venda_media_6m_m3": _num(r["venda_media_6m_m3"]),
            "venda_media_12m_m3": _num(r["venda_media_12m_m3"]),
        })

    out_bases = []
    for cod, base in sorted(bases.items(), key=lambda kv: kv[1]["unidade"]):
        top = top_por_base.get(cod, {})
        tancagem_total = sum(p["tancagem_disponivel_m3"] or 0 for p in base["produtos"])
        venda_total = sum(p["capacidade_venda_m3"] or 0 for p in base["produtos"])
        papeis = papeis_por_base.get(normalize_municipio(base["unidade"]), [])
        out_bases.append({
            **base,
            "tancagem_total_m3": round(tancagem_total, 3),
            "capacidade_venda_total_m3": round(venda_total, 3),
            "papeis": papeis,
            "hibrida": len(papeis) > 1,
            "tem_top": (top.get("tem_top") == "True"),
            "congeneres_top": [c for c in (top.get("congeneres_top") or "").split("; ") if c],
            "top_valor_realizado": _num(top.get("top_valor_realizado")),
            "meses_com_top_realizado": int(top.get("meses_com_top_realizado") or 0),
        })

    return {"bases": out_bases}


def patch_html(html_path, cap_data):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    cap_line = "const CAP = " + json.dumps(cap_data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    anchor = "\nconst charts={};"

    start = content.find("\nconst CAP = ")
    if start != -1:
        end = content.find(anchor)
        content = content[:start + 1] + content[end + 1:]

    idx = content.find(anchor)
    if idx == -1:
        raise RuntimeError("Âncora 'const charts={};' não encontrada em " + str(html_path))
    content = content[:idx + 1] + cap_line + content[idx + 1:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch-html")
    args = ap.parse_args()

    cap_data = build_cap_data()

    if args.patch_html:
        patch_html(args.patch_html, cap_data)
        print(f"{len(cap_data['bases'])} bases escritas em {args.patch_html} (const CAP)")
    else:
        print(json.dumps(cap_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
