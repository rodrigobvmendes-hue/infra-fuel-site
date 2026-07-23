"""Extrai a aba "Capacidade ALE" da planilha de capacidades para CSV.

Fonte:
- arquivos_apoio/02 - CAPACIDADES.xlsx (aba "Capacidade ALE")
  -> dados_tratados/capacidade_ale.csv

A aba de origem é um relatório em grão Base x Produto, com uma linha
"Total" adicional por base (produto vazio) usada nos pivôs da aba
"Resumo". Essa linha de total é descartada aqui: o CSV de saída fica
100% no grão Base x Produto, e totais por base podem ser somados a
partir dele quando necessário.
"""

import csv
from pathlib import Path

import openpyxl

BASE_DIR = Path(__file__).resolve().parent.parent
APOIO_DIR = BASE_DIR / "arquivos_apoio"
OUT_DIR = BASE_DIR / "dados_tratados"

CAPACIDADES_XLSX = APOIO_DIR / "02 - CAPACIDADES.xlsx"
SHEET_NAME = "Capacidade ALE"

HEADER = [
    "codigo_base",
    "unidade",
    "modelo_operacional",
    "produto",
    "tancagem_disponivel_m3",
    "capacidade_recebimento_rodo_m3",
    "capacidade_movimentacao_m3",
    "produto_misturado",
    "capacidade_venda_m3",
    "capacidade_expedicao_rodo_m3",
    "venda_media_6m_m3",
    "venda_media_12m_m3",
    "observacoes",
]


def extract_capacidade_ale():
    wb = openpyxl.load_workbook(CAPACIDADES_XLSX, data_only=True)
    ws = wb[SHEET_NAME]

    rows = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        unidade = row[5]
        produto = row[6]
        if not unidade or not produto:
            continue  # ignora linhas vazias e linhas de "Total" por base
        rows.append([
            row[4],   # E: Codigo Da Base
            unidade,  # F: Unidade
            row[3],   # D: Modelo operacional (Terceiros/Pool/Democratica/Propria)
            produto,  # G: Produto
            row[8],   # I: Tancagem disponivel para movimentacao (m3)
            row[10],  # K: Capacidade mensal de recebimento rodoviario (m3)
            row[11],  # L: Capacidade mensal de movimentacao (m3)
            row[13],  # N: Produto misturado
            row[14],  # O: Capacidade mensal de venda (m3)
            row[15],  # P: Capacidade mensal de expedicao rodoviaria (m3)
            row[19],  # T: Venda media mensal (m3) - 6 meses
            row[20],  # U: Venda media mensal (m3) - 12 meses
            row[16],  # Q: Observacoes
        ])

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / "capacidade_ale.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)

    return len(rows), out_path


if __name__ == "__main__":
    n, path = extract_capacidade_ale()
    print(f"{n} linhas escritas em {path}")
