"""Constrói a dimensão de empresa e o relatório de validação.

Usa Empresa_Normalizada como chave comum entre anp_instalacoes.csv,
bases_autorizadas.csv e empresas_alias.csv. CNPJ não é usado como chave
entre ANP e bases autorizadas (a fonte ANP não possui CNPJ). As razões
sociais originais são preservadas nas tabelas-fato para rastreabilidade.
"""

import csv
from collections import defaultdict
from pathlib import Path

from normalize import normalize_empresa

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "dados_brutos"
OUT_DIR = BASE_DIR / "dados_tratados"


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def add_empresa_normalizada(rows, source_field):
    for row in rows:
        row["Empresa_Normalizada"] = normalize_empresa(row[source_field])
    return rows


def build_alias_lookup(alias_rows):
    """Empresa_Normalizada -> melhor Nome_Reduzido / Tipo_Empresa / Razao_Social."""
    lookup = {}
    for row in alias_rows:
        key = row["Empresa_Normalizada"]
        if key and key not in lookup:
            lookup[key] = row
    return lookup


def build_dim_empresa(anp_rows, bases_rows, alias_rows):
    alias_lookup = build_alias_lookup(alias_rows)

    anp_by_key = defaultdict(list)
    for row in anp_rows:
        if row["Empresa_Normalizada"]:
            anp_by_key[row["Empresa_Normalizada"]].append(row)

    bases_by_key = defaultdict(list)
    for row in bases_rows:
        if row["Empresa_Normalizada"]:
            bases_by_key[row["Empresa_Normalizada"]].append(row)

    all_keys = sorted(set(anp_by_key) | set(bases_by_key))

    dim_rows = []
    for i, key in enumerate(all_keys, start=1):
        bases_for_key = bases_by_key.get(key, [])
        anp_for_key = anp_by_key.get(key, [])
        alias = alias_lookup.get(key)

        if bases_for_key:
            razao_referencia = bases_for_key[0]["Razão Social"]
        elif alias:
            razao_referencia = alias["RazaoSocialOriginal"]
        else:
            razao_referencia = anp_for_key[0]["NomeEmpresarial"]

        cnpjs = {r["CNPJ"] for r in bases_for_key if r.get("CNPJ")}

        dim_rows.append({
            "Empresa_Key": f"EMP{i:05d}",
            "Empresa_Normalizada": key,
            "Razao_Social_Referencia": razao_referencia,
            "Nome_Reduzido": alias["NomeReduzido"] if alias else "",
            "Tipo_Empresa": alias["TipoEmpresa"] if alias else "",
            "Qtd_CNPJs": len(cnpjs),
            "Qtd_Instalacoes_ANP": len(anp_for_key),
            "Presente_ANP": "S" if anp_for_key else "N",
            "Presente_Bases_Autorizadas": "S" if bases_for_key else "N",
        })

    return dim_rows, anp_by_key, bases_by_key


def build_validation_report(dim_rows, anp_by_key, bases_by_key, anp_rows, bases_rows):
    em_ambas = [r for r in dim_rows if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "S"]
    so_anp = [r for r in dim_rows if r["Presente_ANP"] == "S" and r["Presente_Bases_Autorizadas"] == "N"]
    so_bases = [r for r in dim_rows if r["Presente_ANP"] == "N" and r["Presente_Bases_Autorizadas"] == "S"]
    multi_cnpj = [r for r in dim_rows if r["Qtd_CNPJs"] > 1]

    multi_grafia = []
    for key in sorted(set(anp_by_key) | set(bases_by_key)):
        grafias = set()
        for r in anp_by_key.get(key, []):
            grafias.add(r["NomeEmpresarial"])
        for r in bases_by_key.get(key, []):
            grafias.add(r["Razão Social"])
        if len(grafias) > 1:
            multi_grafia.append((key, sorted(grafias)))

    lines = [
        "# Relatório de validação - relacionamento entre fontes de empresa",
        "",
        f"- Total de empresas distintas (Empresa_Normalizada): {len(dim_rows)}",
        f"- Empresas presentes nas duas fontes (ANP e bases autorizadas): {len(em_ambas)}",
        f"- Empresas presentes somente na ANP: {len(so_anp)}",
        f"- Empresas presentes somente na base autorizada: {len(so_bases)}",
        f"- Empresas com mais de um CNPJ associado: {len(multi_cnpj)}",
        f"- Empresas com mais de uma grafia original (ANP x Razão Social): {len(multi_grafia)}",
        "",
        "## Empresas com mais de um CNPJ",
        "",
    ]
    for r in multi_cnpj:
        lines.append(f"- {r['Empresa_Key']} | {r['Empresa_Normalizada']} | Qtd_CNPJs={r['Qtd_CNPJs']}")

    lines += ["", "## Empresas com mais de uma grafia original", ""]
    for key, grafias in multi_grafia:
        lines.append(f"- {key}: " + " | ".join(grafias))

    lines += ["", "## Somente na ANP (amostra)", ""]
    for r in so_anp[:50]:
        lines.append(f"- {r['Empresa_Key']} | {r['Empresa_Normalizada']}")

    lines += ["", "## Somente na base autorizada (amostra)", ""]
    for r in so_bases[:50]:
        lines.append(f"- {r['Empresa_Key']} | {r['Empresa_Normalizada']}")

    return "\n".join(lines) + "\n"


def main():
    OUT_DIR.mkdir(exist_ok=True)

    anp_rows = add_empresa_normalizada(_read_csv(RAW_DIR / "anp_instalacoes.csv"), "NomeEmpresarial")
    bases_rows = add_empresa_normalizada(_read_csv(RAW_DIR / "bases_autorizadas.csv"), "Razão Social")
    alias_rows = add_empresa_normalizada(_read_csv(RAW_DIR / "empresas_alias.csv"), "RazaoSocialOriginal")

    _write_csv(OUT_DIR / "anp_instalacoes.csv", list(anp_rows[0].keys()), anp_rows)
    _write_csv(OUT_DIR / "bases_autorizadas.csv", list(bases_rows[0].keys()), bases_rows)
    _write_csv(OUT_DIR / "empresas_alias.csv", list(alias_rows[0].keys()), alias_rows)

    dim_rows, anp_by_key, bases_by_key = build_dim_empresa(anp_rows, bases_rows, alias_rows)
    dim_header = list(dim_rows[0].keys())
    _write_csv(OUT_DIR / "dim_empresa.csv", dim_header, dim_rows)

    report = build_validation_report(dim_rows, anp_by_key, bases_by_key, anp_rows, bases_rows)
    (OUT_DIR / "relatorio_validacao_empresas.md").write_text(report, encoding="utf-8")

    print(f"dim_empresa.csv: {len(dim_rows)} empresas")
    print("relatorio_validacao_empresas.md gerado")


if __name__ == "__main__":
    main()
