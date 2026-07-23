"""Agrega "Detalhamento Tancagem" por Base x Papel operacional, para
expor bases "híbridas" (que operam sob mais de um modelo/papel ao mesmo
tempo).

Duque de Caxias é o caso que motivou esta granularidade: são 3 papéis
distintos na mesma base, não 2:
1. "{modelo} (uso próprio)" -- tancagem própria/pool que a ALE de fato
   usa (linhas de tipo_espaco = "ESPAÇO ALE - BASE PRÓPRIA").
2. "Cessão de espaço (cedente)" -- dentro dessa mesma base, parte da
   tancagem útil é cedida a um terceiro que opera junto com a ALE
   (coluna "Espaço Cedido (m³)" nas linhas de tipo_espaco =
   "ESPAÇO ALE - BASE PRÓPRIA"). A ALE é quem cede o espaço.
3. "Cessão de espaço (cessionária) - {modelo}" -- linhas de tipo_espaco =
   "ESPAÇO EM TERCEIROS": a ALE é quem usa espaço na base de um
   congênere (ex.: Raízen), movimentando parte das suas próprias
   movimentações lá. A ALE é quem recebe o espaço cedido.

Papéis 1 e 3 preservam o `modelo` original da linha (Própria/Pool na
base própria; Terceiros/Democrática na base de terceiro), já que a
mesma tancagem pode ser Pool-uso-próprio ou Terceiros-cessionária, por
exemplo. O papel 2 (cedente) só existe dentro de linhas "ESPAÇO ALE -
BASE PRÓPRIA" com espaço cedido > 0, e é sempre rotulado à parte porque
representa a operação oposta (ceder, não usar).

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

PAPEL_CEDENTE = "Cessão de espaço (cedente)"


def _papel_e_valor(row):
    """Retorna [(papel, valor_m3), ...] para uma linha do detalhamento.

    `modelo` já vem correto por linha (Própria/Pool/Democrática/Terceiros
    -- ver Detalhamento Tancagem). O que falta é separar, dentro de uma
    mesma base própria/pool, o uso próprio da tancagem do espaço que a
    ALE cede a um terceiro que opera junto (papel de cedente, via coluna
    "Espaço Cedido"). Uma linha "ESPAÇO ALE - BASE PRÓPRIA" pode gerar 2
    papéis ao mesmo tempo (uso próprio + cedente) quando isso ocorre."""
    modelo = row["modelo"]
    tipo_espaco = row["tipo_espaco"]
    disponivel = float(row["tancagem_disponivel_movimentacao_m3"] or 0)
    cedido = float(row["espaco_cedido_m3"] or 0)

    if tipo_espaco == "ESPAÇO ALE - BASE PRÓPRIA":
        out = [(f"{modelo} (uso próprio)", disponivel)]
        if cedido > 0:
            out.append((PAPEL_CEDENTE, cedido))
        return out
    if tipo_espaco == "ESPAÇO EM TERCEIROS":
        return [(f"Cessão de espaço (cessionária) - {modelo}", disponivel)]
    return [(modelo, disponivel)]  # CARREGAMENTO / outros: mantém o modelo original


def build_capacidade_por_modelo():
    with DETALHAMENTO_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tancagem = defaultdict(float)
    n_alocacoes = defaultdict(int)
    unidade_por_base = {}
    papeis_por_base = defaultdict(set)

    for r in rows:
        cod = r["codigo_base"]
        unidade_por_base[cod] = r["unidade"]
        for papel, valor in _papel_e_valor(r):
            key = (cod, papel)
            tancagem[key] += valor
            n_alocacoes[key] += 1
            papeis_por_base[cod].add(papel)

    out_rows = []
    for (cod, papel), tanc in sorted(tancagem.items()):
        papeis_base = papeis_por_base[cod]
        out_rows.append({
            "codigo_base": cod,
            "unidade": unidade_por_base[cod],
            "papel_operacional": papel,
            "tancagem_disponivel_movimentacao_m3": round(tanc, 3),
            "n_alocacoes": n_alocacoes[(cod, papel)],
            "base_hibrida": len(papeis_base) > 1,
            "papeis_presentes_na_base": "; ".join(sorted(papeis_base)),
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
