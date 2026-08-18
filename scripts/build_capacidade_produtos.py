"""Extrai e agrega a tancagem por produto (tanque a tanque) da planilha ANP.

Fonte: arquivos_apoio/bases-tancagem-produtos.xlsx (aba única, cabeçalho na
linha 5, dados a partir da linha 6). Cada linha é um tanque, com o CNPJ do
proprietário daquele tanque especificamente -- isso permite atribuir a
tancagem à empresa certa mesmo em bases compartilhadas (pool), sem precisar
estimar via percentual de participação.

Saídas:
- dados_tratados/capacidade_produtos_base.csv    (uma linha por base+empresa proprietária)
- dados_tratados/capacidade_produtos_empresa.csv (ranking nacional por empresa)
- capacidade-produtos-data.js                    (dados para a página capacidade-produtos.html)
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

import openpyxl

from normalize import grupo_empresarial, nome_grupo

BASE_DIR = Path(__file__).resolve().parent.parent
APOIO_DIR = BASE_DIR / "arquivos_apoio"
RAW_DIR = BASE_DIR / "dados_brutos"
OUT_DIR = BASE_DIR / "dados_tratados"

TANCAGEM_XLSX = APOIO_DIR / "bases-tancagem-produtos.xlsx"

CATEGORIAS = ["Gasolina", "S10", "S500", "B100", "Anidro", "Hidratado", "Outros"]

_CATEGORIA_EXATA = {
    "GASOLINA A COMUM": "Gasolina",
    "GASOLINA C COMUM": "Gasolina",
    "GASOLINA A": "Gasolina",
    "GASOLINAS": "Gasolina",
    "GASOLINA C": "Gasolina",
    "GASOLINAS AUTOMOTIVAS": "Gasolina",
    "GASOLINA AUTOMOTIVA PADRÃO": "Gasolina",
    "ÓLEO DIESEL A S10": "S10",
    "ÓLEO DIESEL B S10 - COMUM": "S10",
    "ÓLEO DIESEL C S10": "S10",
    "ÓLEOS DIESEL A S10": "S10",
    "ÓLEO DIESEL A S500": "S500",
    "ÓLEO DIESEL B S500 - COMUM": "S500",
    "ÓLEOS DIESEL A S500": "S500",
    "BIODIESEL B100": "B100",
    "BIODIESEL": "B100",
    "ETANOL ANIDRO": "Anidro",
    "ETANOL ANIDRO FORA DE ESPECIFICAÇÃO": "Anidro",
    "ETANOL HIDRATADO COMUM": "Hidratado",
    "ETANOL HIDRATADO": "Hidratado",
    "ETANOL HIDRATADO FORA DE ESPECIFICAÇÃO": "Hidratado",
}

# Produtos "Outros" que são especificamente diesel marítimo -- mantidos como
# subcategoria visível dentro de Outros, em vez de ficarem escondidos junto
# com óleo combustível/querosene/etc.
_MARITIMO_SET = {
    "ÓLEO DIESEL MARÍTIMO",
    "ÓLEO DIESEL MARÍTIMO A2 OU DMA2",
    "DMA - MGO",
    "DMB - MDO",
}


def categoria_for(produto):
    p = (produto or "").strip().upper()
    if p in _CATEGORIA_EXATA:
        return _CATEGORIA_EXATA[p], None
    if p in _MARITIMO_SET:
        return "Outros", "Maritimo"
    return "Outros", None


def _to_num(v):
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _load_rows():
    wb = openpyxl.load_workbook(TANCAGEM_XLSX, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    header = [c.value for c in next(ws.iter_rows(min_row=5, max_row=5))]
    idx = {name: i for i, name in enumerate(header)}
    rows = []
    for row in ws.iter_rows(min_row=6, values_only=True):
        if not row[idx["NR_ORDEM_BASE"]]:
            continue
        rows.append(row)
    return idx, rows


def aggregate(idx, rows):
    """Agrega por (NR_ORDEM_BASE, CNPJ_PROPRIETARIO) -> totais por categoria.

    Em bases compartilhadas (pool), a planilha-fonte repete o manifesto
    INTEIRO de tanques para cada empresa co-proprietária (a mesma NR_TANQUE
    aparece várias vezes, uma por empresa, sempre com a mesma capacidade) --
    não é uma partição física do tanque. A capacidade real de cada empresa
    é o "%_PARTICIPACAO" (constante por base+empresa) aplicado sobre o total
    de tanques ÚNICOS da base. Somar direto por CNPJ sem deduplicar
    multiplicaria a capacidade nacional por empresas co-proprietárias.
    """
    # Passo 1: manifesto de tanques únicos por base -> total por categoria.
    tanques_por_base = defaultdict(dict)  # nr_ordem -> {nr_tanque: (categoria, subcategoria, capacidade)}
    meta_base = {}
    for r in rows:
        nr_ordem = str(r[idx["NR_ORDEM_BASE"]]).strip()
        nr_tanque = r[idx["NR_TANQUE"]]
        if nr_tanque not in tanques_por_base[nr_ordem]:
            capacidade = _to_num(r[idx["CAPACIDADE OPERACIONAL"]])
            categoria, subcategoria = categoria_for(r[idx["PRODUTO"]])
            tanques_por_base[nr_ordem][nr_tanque] = (categoria, subcategoria, capacidade)
        meta_base.setdefault(nr_ordem, {
            "municipio": r[idx["MUNICIPIO"]],
            "uf": r[idx["UF"]],
        })

    base_totais = {}
    for nr_ordem, tanques in tanques_por_base.items():
        por_categoria = defaultdict(float)
        maritimo = 0.0
        total = 0.0
        for categoria, subcategoria, capacidade in tanques.values():
            por_categoria[categoria] += capacidade
            if subcategoria == "Maritimo":
                maritimo += capacidade
            total += capacidade
        base_totais[nr_ordem] = {"por_categoria": por_categoria, "maritimo_m3": maritimo, "total_m3": total}

    # Passo 2: participação por (base, empresa) -- constante em todas as linhas.
    participacao = {}
    empresa_info = {}
    admin_info = {}
    for r in rows:
        nr_ordem = str(r[idx["NR_ORDEM_BASE"]]).strip()
        cnpj = str(r[idx["CNPJ_PROPRIETARIO"]] or "").strip()
        participacao[(nr_ordem, cnpj)] = _to_num(r[idx["%_PARTICIPACAO"]])
        empresa_info[(nr_ordem, cnpj)] = r[idx["RAZAO_SOCIAL_PROPRIETARIO"]]
        admin_info[nr_ordem] = (r[idx["CNPJ_ADMIN"]], r[idx["RAZAO_SOCIAL_ADMIN"]])

    # Passo 3: aplica a participação de cada empresa sobre o total (deduplicado) da base.
    por_base_empresa = {}
    for (nr_ordem, cnpj), pct in participacao.items():
        base_tot = base_totais[nr_ordem]
        fator = pct / 100.0
        cnpj_admin, razao_admin = admin_info[nr_ordem]
        por_base_empresa[(nr_ordem, cnpj)] = {
            "nr_ordem_base": nr_ordem,
            "cnpj_proprietario": cnpj,
            "razao_social": empresa_info[(nr_ordem, cnpj)],
            "municipio": meta_base[nr_ordem]["municipio"],
            "uf": meta_base[nr_ordem]["uf"],
            "cnpj_admin": cnpj_admin,
            "razao_social_admin": razao_admin,
            "por_categoria": {cat: v * fator for cat, v in base_tot["por_categoria"].items()},
            "maritimo_m3": base_tot["maritimo_m3"] * fator,
            "total_m3": base_tot["total_m3"] * fator,
            "participacao_pct": pct,
            "qtd_tanques": len(tanques_por_base[nr_ordem]),
        }

    return list(por_base_empresa.values())


def build_empresa_ranking(base_empresa_rows):
    """Agrupa por GRUPO empresarial (não por CNPJ nem por razão social
    isolada): uma mesma distribuidora pode ter várias filiais/CNPJs, e
    marcas adquiridas (ex.: Petróleo Sabbá, Raízen Mime -> Raízen) devem
    somar no grupo controlador -- ver grupo_empresarial()/nome_grupo() em
    normalize.py, fonte única dessa consolidação para todos os dashboards."""
    por_empresa = {}
    for row in base_empresa_rows:
        cnpj = row["cnpj_proprietario"]
        if not cnpj or not row["razao_social"]:
            continue
        key = grupo_empresarial(row["razao_social"])
        if not key:
            continue
        if key not in por_empresa:
            por_empresa[key] = {
                "empresa_key": key,
                "razao_social": row["razao_social"],
                "nome_reduzido": nome_grupo(row["razao_social"]),
                "cnpjs": set(),
                "total_m3": 0.0,
                "qtd_bases": 0,
                "por_categoria": defaultdict(float),
            }
        emp = por_empresa[key]
        emp["cnpjs"].add(cnpj)
        emp["total_m3"] += row["total_m3"]
        emp["qtd_bases"] += 1
        for cat in CATEGORIAS:
            emp["por_categoria"][cat] += row["por_categoria"].get(cat, 0.0)

    ranking = list(por_empresa.values())
    ranking.sort(key=lambda e: e["total_m3"], reverse=True)
    return ranking


def _write_csv_base_empresa(rows, path):
    header = (
        ["NR_Ordem_Base", "CNPJ_Proprietario", "Razao_Social", "Municipio", "UF",
         "CNPJ_Admin", "Razao_Social_Admin", "Qtd_Tanques", "Total_M3", "Maritimo_M3"]
        + CATEGORIAS
    )
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in rows:
            writer.writerow([
                r["nr_ordem_base"], r["cnpj_proprietario"], r["razao_social"],
                r["municipio"], r["uf"], r["cnpj_admin"], r["razao_social_admin"],
                r["qtd_tanques"], round(r["total_m3"], 2), round(r["maritimo_m3"], 2),
            ] + [round(r["por_categoria"].get(cat, 0.0), 2) for cat in CATEGORIAS])


def _write_csv_empresa(ranking, path):
    header = ["Empresa_Key", "Razao_Social", "Nome_Reduzido", "Qtd_CNPJs", "Qtd_Bases", "Total_M3"] + CATEGORIAS
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in ranking:
            writer.writerow([
                r["empresa_key"], r["razao_social"], r["nome_reduzido"], len(r["cnpjs"]), r["qtd_bases"],
                round(r["total_m3"], 2),
            ] + [round(r["por_categoria"].get(cat, 0.0), 2) for cat in CATEGORIAS])


def _write_js_data(base_empresa_rows, ranking, path):
    bases_out = []
    for r in base_empresa_rows:
        bases_out.append({
            "ordem": r["nr_ordem_base"],
            "cnpj": r["cnpj_proprietario"],
            "empresaKey": grupo_empresarial(r["razao_social"] or ""),
            "empresa": r["razao_social"],
            "nomeReduzido": nome_grupo(r["razao_social"] or ""),
            "municipio": (r["municipio"] or "").strip(),
            "uf": (r["uf"] or "").strip(),
            "cnpjAdmin": r["cnpj_admin"],
            "administradora": r["razao_social_admin"],
            "participacaoPct": r["participacao_pct"],
            "totalM3": round(r["total_m3"], 2),
            "maritimoM3": round(r["maritimo_m3"], 2),
            "categorias": {cat: round(r["por_categoria"].get(cat, 0.0), 2) for cat in CATEGORIAS},
        })

    ranking_out = []
    for r in ranking:
        ranking_out.append({
            "empresaKey": r["empresa_key"],
            "empresa": r["razao_social"],
            "nomeReduzido": r["nome_reduzido"],
            "qtdCnpjs": len(r["cnpjs"]),
            "qtdBases": r["qtd_bases"],
            "totalM3": round(r["total_m3"], 2),
            "categorias": {cat: round(r["por_categoria"].get(cat, 0.0), 2) for cat in CATEGORIAS},
        })

    payload = {
        "categorias": CATEGORIAS,
        "bases": bases_out,
        "ranking": ranking_out,
        "metrica": "Capacidade Operacional (m³)",
    }

    with open(path, "w", encoding="utf-8") as f:
        f.write("// Gerado por scripts/build_capacidade_produtos.py -- não editar manualmente.\n")
        f.write("const CAPACIDADE_PRODUTOS = ")
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write(";\n")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    idx, rows = _load_rows()
    base_empresa_rows = aggregate(idx, rows)
    ranking = build_empresa_ranking(base_empresa_rows)

    _write_csv_base_empresa(base_empresa_rows, OUT_DIR / "capacidade_produtos_base.csv")
    _write_csv_empresa(ranking, OUT_DIR / "capacidade_produtos_empresa.csv")
    _write_js_data(base_empresa_rows, ranking, BASE_DIR / "capacidade-produtos-data.js")

    print(f"Tanques processados: {len(rows)}")
    print(f"Combinações base+empresa: {len(base_empresa_rows)}")
    print(f"Empresas no ranking: {len(ranking)}")
    print(f"Capacidade operacional total: {sum(r['total_m3'] for r in ranking):,.2f} m³")


if __name__ == "__main__":
    main()
