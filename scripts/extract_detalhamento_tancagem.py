"""Extrai a aba "Detalhamento Tancagem" para CSV.

Fonte:
- arquivos_apoio/02 - CAPACIDADES.xlsx (aba "Detalhamento Tancagem")
  -> dados_tratados/detalhamento_tancagem.csv

Grão: 1 linha = 1 alocação de tancagem por Base x Produto x Armazenador
x Tipo de Espaço. Esse é o grão em que operações "híbridas" aparecem:
uma mesma base (`unidade`) pode ter linhas com `modelo` = "Própria" e
outras com `modelo` = "Terceiros"/"Democrática"/"Pool" para o mesmo
produto (ex.: Duque de Caxias, que é Própria mas cede espaço a
terceiro/RAÍZEN em vários produtos). A aba "Capacidade ALE" resume cada
base a um único modelo e perde essa informação -- por isso esta
extração é a fonte correta para "quais modelos eu opero nesta base".
"""

import csv
from pathlib import Path

import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent
APOIO_DIR = BASE_DIR / "arquivos_apoio"
OUT_DIR = BASE_DIR / "dados_tratados"

CAPACIDADES_XLSX = APOIO_DIR / "02 - CAPACIDADES.xlsx"
SHEET_NAME = "Detalhamento Tancagem"

HEADER = [
    "codigo_base",
    "unidade",
    "tipo_espaco",
    "modelo",
    "tipo_operacao",
    "produto",
    "base_armazenador",
    "modal",
    "tancagem_operacional_m3",
    "lastro_m3",
    "tancagem_util_m3",
    "reducao_manutencao_m3",
    "espaco_cedido_m3",
    "tancagem_disponivel_movimentacao_m3",
]


def extract_detalhamento_tancagem():
    wb = openpyxl.load_workbook(CAPACIDADES_XLSX, data_only=True)
    ws = wb[SHEET_NAME]

    rows = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        codigo_base, unidade = row[0], row[1]
        if not unidade:
            continue
        rows.append(list(row[:14]))

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "detalhamento_tancagem.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)

    return len(rows), out_path


if __name__ == "__main__":
    n, path = extract_detalhamento_tancagem()
    print(f"{n} linhas escritas em {path}")
