"""Agrega "Detalhamento Tancagem" por Base x Modelo operacional, para
expor bases "híbridas" (que operam sob mais de um modelo ao mesmo tempo
-- ex.: Duque de Caxias, Própria, que também cede espaço a terceiro).

A aba "Capacidade ALE" resume cada base a um único `modelo_operacional`
(o predominante); esta saída mostra a composição real por modelo,
somando `tancagem_disponivel_movimentacao_m3` do detalhamento.

Fonte: dados_tratados/detalhamento_tancagem.csv
Saída: dados_tratados/capacidade_por_modelo.csv
"""

import csv
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRATADOS_DIR = BASE_DIR / "dados_tratados"

DETALHAMENTO_CSV = TRATADOS_DIR / "detalhamento_tancagem.csv"
OUT_CSV = TRATADOS_DIR / "capacidade_por_modelo.csv"


def build_capacidade_por_modelo():
    with DETALHAMENTO_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tancagem = defaultdict(float)
    n_produtos = defaultdict(int)
    unidade_por_base = {}
    modelos_por_base = defaultdict(set)

    for r in rows:
        cod = r["codigo_base"]
        modelo = r["modelo"]
        key = (cod, modelo)
        tancagem[key] += float(r["tancagem_disponivel_movimentacao_m3"] or 0)
        n_produtos[key] += 1
        unidade_por_base[cod] = r["unidade"]
        modelos_por_base[cod].add(modelo)

    out_rows = []
    for (cod, modelo), tanc in sorted(tancagem.items()):
        modelos_base = modelos_por_base[cod]
        out_rows.append({
            "codigo_base": cod,
            "unidade": unidade_por_base[cod],
            "modelo": modelo,
            "tancagem_disponivel_movimentacao_m3": round(tanc, 3),
            "n_alocacoes": n_produtos[(cod, modelo)],
            "base_hibrida": len(modelos_base) > 1,
            "modelos_presentes_na_base": "; ".join(sorted(modelos_base)),
        })

    OUT_CSV.parent.mkdir(exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    n_hibridas = len({r["codigo_base"] for r in out_rows if r["base_hibrida"]})
    return len(out_rows), n_hibridas, OUT_CSV


if __name__ == "__main__":
    n, n_hibridas, path = build_capacidade_por_modelo()
    print(f"{n} linhas escritas em {path} ({n_hibridas} bases híbridas)")
