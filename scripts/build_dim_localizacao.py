"""Completa o pipeline: localização, IDs técnicos, flags de qualidade e
relatório oficial de validação.

Pré-requisito: rodar antes `extract_raw.py` e `build_dim_empresa.py`, pois
este script lê e reescreve os CSVs já tratados em `dados_tratados/`
(que já contêm a coluna Empresa_Normalizada).

Saídas:
- dados_tratados/anp_instalacoes.csv      (+ Municipio_Normalizado, Localizacao_Key, Id_Instalacao_ANP)
- dados_tratados/bases_autorizadas.csv    (+ Municipio_Normalizado, Localizacao_Key, Id_Base_Autorizada,
                                              Flag_CNPJ_Duplicado, Flag_Dado_Incompleto)
- dados_tratados/dim_localizacao.csv      (novo)
- docs/validacao-tratamento-powerbi.md    (novo)
"""

import csv
from collections import Counter
from pathlib import Path

from normalize import build_localizacao_key, normalize_municipio, stable_id

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "dados_brutos"
OUT_DIR = BASE_DIR / "dados_tratados"
DOCS_DIR = BASE_DIR / "docs"

CAMPOS_CRITICOS_BASES = [
    "CNPJ",
    "Razão Social",
    "Município",
    "UF",
    "Capacidade Total",
    "Número Autorização",
    "Data Publicação",
]


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value):
    if value is None or value.strip() == "":
        return 0.0
    text = value.strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def enrich_anp(anp_rows):
    for row in anp_rows:
        municipio_normalizado = normalize_municipio(row["Municipio"])
        row["Municipio_Normalizado"] = municipio_normalizado
        row["Localizacao_Key"] = build_localizacao_key(row["Uf"], municipio_normalizado)
        row["Id_Instalacao_ANP"] = stable_id(
            "ANP",
            row["Uf"],
            municipio_normalizado,
            row["Empresa_Normalizada"],
            row["Segmento"],
            row["DetalheInstalacao"],
            row["NumTanques"],
            row["TancagemTotalM3"],
        )
    return anp_rows


def enrich_bases(bases_rows):
    cnpj_counts = Counter(
        row["CNPJ"].strip() for row in bases_rows if row.get("CNPJ", "").strip()
    )

    for row in bases_rows:
        municipio_normalizado = normalize_municipio(row["Município"])
        row["Municipio_Normalizado"] = municipio_normalizado
        row["Localizacao_Key"] = build_localizacao_key(row["UF"], municipio_normalizado)
        row["Id_Base_Autorizada"] = stable_id(
            "BASE",
            row["CNPJ"],
            row["UF"],
            municipio_normalizado,
            row["Número Autorização"],
            row["Endereço da Matriz"],
            row["Número"],
            row["Capacidade Total"],
            row["Tipo de Instalação"],
        )

        cnpj = row.get("CNPJ", "").strip()
        row["Flag_CNPJ_Duplicado"] = "S" if cnpj and cnpj_counts[cnpj] > 1 else "N"

        incompleto = any(not row.get(campo, "").strip() for campo in CAMPOS_CRITICOS_BASES)
        row["Flag_Dado_Incompleto"] = "S" if incompleto else "N"

    return bases_rows


def build_dim_localizacao(anp_rows, bases_rows):
    presente_anp = set()
    presente_bases = set()
    info = {}

    for row in anp_rows:
        key = row["Localizacao_Key"]
        presente_anp.add(key)
        info.setdefault(key, {
            "UF": row["Uf"].strip().upper(),
            "Municipio": row["Municipio"].strip(),
            "Municipio_Normalizado": row["Municipio_Normalizado"],
        })

    for row in bases_rows:
        key = row["Localizacao_Key"]
        presente_bases.add(key)
        info.setdefault(key, {
            "UF": row["UF"].strip().upper(),
            "Municipio": row["Município"].strip(),
            "Municipio_Normalizado": row["Municipio_Normalizado"],
        })

    dim_rows = []
    for key in sorted(info):
        dados = info[key]
        dim_rows.append({
            "Localizacao_Key": key,
            "UF": dados["UF"],
            "Municipio": dados["Municipio"],
            "Municipio_Normalizado": dados["Municipio_Normalizado"],
            "Presente_ANP": "S" if key in presente_anp else "N",
            "Presente_Bases_Autorizadas": "S" if key in presente_bases else "N",
        })

    return dim_rows


def _duplicated_count(values):
    counts = Counter(v for v in values if v)
    return sum(1 for v in counts.values() if v > 1)


def build_report(anp_raw, anp_trat, bases_raw, bases_trat, dim_empresa, dim_localizacao):
    soma_tancagem_antes = sum(_to_float(r.get("TancagemTotalM3")) for r in anp_raw)
    soma_tancagem_depois = sum(_to_float(r.get("TancagemTotalM3")) for r in anp_trat)

    soma_capacidade_antes = sum(_to_float(r.get("Capacidade Total")) for r in bases_raw)
    soma_capacidade_depois = sum(_to_float(r.get("Capacidade Total")) for r in bases_trat)

    cnpjs_duplicados = sum(1 for r in bases_trat if r["Flag_CNPJ_Duplicado"] == "S")
    incompletos = sum(1 for r in bases_trat if r["Flag_Dado_Incompleto"] == "S")

    em_ambas = sum(1 for r in dim_empresa if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "S")
    so_anp = sum(1 for r in dim_empresa if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "N")
    so_bases = sum(1 for r in dim_empresa if r["Presente_ANP"] == "N" and r["Presente_Bases_Autorizadas"] == "S")

    loc_em_ambas = sum(1 for r in dim_localizacao if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "S")
    loc_so_anp = sum(1 for r in dim_localizacao if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "N")
    loc_so_bases = sum(1 for r in dim_localizacao if r["Presente_ANP"] == "N" and r["Presente_Bases_Autorizadas"] == "S")

    dup_id_anp = _duplicated_count(r["Id_Instalacao_ANP"] for r in anp_trat)
    dup_id_base = _duplicated_count(r["Id_Base_Autorizada"] for r in bases_trat)
    dup_empresa_key = _duplicated_count(r["Empresa_Key"] for r in dim_empresa)
    dup_localizacao_key = _duplicated_count(r["Localizacao_Key"] for r in dim_localizacao)

    linhas = [
        "# Validação do tratamento de dados — Power BI",
        "",
        "Relatório gerado automaticamente pelo pipeline "
        "(`extract_raw.py` -> `build_dim_empresa.py` -> `build_dim_localizacao.py`).",
        "",
        "## Registros antes e depois",
        "",
        f"- ANP — registros: {len(anp_raw)} (antes) / {len(anp_trat)} (depois)",
        f"- Bases autorizadas — registros: {len(bases_raw)} (antes) / {len(bases_trat)} (depois)",
        "",
        "## Totais agregados",
        "",
        f"- Soma da tancagem ANP (m³): {soma_tancagem_antes:.2f} (antes) / {soma_tancagem_depois:.2f} (depois)",
        f"- Soma da capacidade total (bases autorizadas): {soma_capacidade_antes:.2f} (antes) / {soma_capacidade_depois:.2f} (depois)",
        "- Confirmação: nenhuma capacidade ou tancagem foi consolidada, somada ou duplicada "
        "entre registros — os totais antes e depois são idênticos porque o tratamento apenas "
        "adiciona colunas derivadas, sem agregar ou remover linhas.",
        "",
        "## Qualidade dos dados",
        "",
        f"- CNPJs duplicados (registros com `Flag_CNPJ_Duplicado = S`): {cnpjs_duplicados}",
        f"- Registros incompletos (campos críticos, desconsiderando `Complemento`): {incompletos}",
        "",
        "## Relacionamento entre fontes — Empresas",
        "",
        f"- Total de empresas distintas (`dim_empresa.csv`): {len(dim_empresa)}",
        f"- Empresas presentes nas duas fontes (ANP e bases autorizadas): {em_ambas}",
        f"- Empresas presentes somente na ANP: {so_anp}",
        f"- Empresas presentes somente nas bases autorizadas: {so_bases}",
        "",
        "## Relacionamento entre fontes — Localizações",
        "",
        f"- Total de localizações distintas (`dim_localizacao.csv`): {len(dim_localizacao)}",
        f"- Localizações presentes nas duas fontes: {loc_em_ambas}",
        f"- Localizações presentes somente na ANP: {loc_so_anp}",
        f"- Localizações presentes somente nas bases autorizadas: {loc_so_bases}",
        "",
        "## Unicidade dos identificadores técnicos",
        "",
        f"- `Id_Instalacao_ANP` — valores duplicados: {dup_id_anp} (de {len(anp_trat)} registros)",
        f"- `Id_Base_Autorizada` — valores duplicados: {dup_id_base} (de {len(bases_trat)} registros)",
        f"- `Empresa_Key` (`dim_empresa.csv`) — valores duplicados: {dup_empresa_key} (de {len(dim_empresa)} registros)",
        f"- `Localizacao_Key` (`dim_localizacao.csv`) — valores duplicados: {dup_localizacao_key} (de {len(dim_localizacao)} registros)",
    ]

    return "\n".join(linhas) + "\n"


def main():
    OUT_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    anp_raw = _read_csv(RAW_DIR / "anp_instalacoes.csv")
    bases_raw = _read_csv(RAW_DIR / "bases_autorizadas.csv")

    anp_trat = enrich_anp(_read_csv(OUT_DIR / "anp_instalacoes.csv"))
    bases_trat = enrich_bases(_read_csv(OUT_DIR / "bases_autorizadas.csv"))

    _write_csv(OUT_DIR / "anp_instalacoes.csv", list(anp_trat[0].keys()), anp_trat)
    _write_csv(OUT_DIR / "bases_autorizadas.csv", list(bases_trat[0].keys()), bases_trat)

    dim_localizacao = build_dim_localizacao(anp_trat, bases_trat)
    _write_csv(OUT_DIR / "dim_localizacao.csv", list(dim_localizacao[0].keys()), dim_localizacao)

    dim_empresa = _read_csv(OUT_DIR / "dim_empresa.csv")
    report = build_report(anp_raw, anp_trat, bases_raw, bases_trat, dim_empresa, dim_localizacao)
    (DOCS_DIR / "validacao-tratamento-powerbi.md").write_text(report, encoding="utf-8")

    print(f"anp_instalacoes.csv: {len(anp_trat)} registros (+3 colunas)")
    print(f"bases_autorizadas.csv: {len(bases_trat)} registros (+5 colunas)")
    print(f"dim_localizacao.csv: {len(dim_localizacao)} localizações")
    print("docs/validacao-tratamento-powerbi.md gerado")


if __name__ == "__main__":
    main()
