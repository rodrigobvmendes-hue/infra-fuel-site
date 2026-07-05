"""Relatórios da rodada: KPIs, mix modal, plano de atendimento e export XLSX.

Toda exportação carrega a aba Auditoria (arquivo, data, parâmetros) — o
resultado precisa ser rastreável até a base e as premissas que o geraram.
"""

from datetime import datetime

import pandas as pd

from .model import RunResult
from .products import MODAL_LOCAL


def flows_df(res: RunResult) -> pd.DataFrame:
    """Plano de atendimento: um fluxo por linha, com o MODAL usado."""
    rows = [{
        "Filial": a.d.kf, "Produto": a.d.prod,
        "Origem do atendimento": a.s.ko, "Fornecedor": a.s.forn,
        "Modal": a.modal,
        "Volume (m³)": round(a.vol, 1),
        "Produto (R$/m³)": round(a.s.preco, 2),
        "Frete (R$/m³)": round(a.frete, 2),
        "Armazenagem (R$/m³)": round(a.armaz, 2),
        "Total (R$/m³)": round(a.unit, 2),
        "Custo (R$)": round(a.vol * a.unit, 0),
        "Atendimento": "Local" if a.modal == MODAL_LOCAL else "Inter-praça",
    } for a in res.flows]
    return pd.DataFrame(rows)


def modal_mix_df(res: RunResult) -> pd.DataFrame:
    """Mix modal: volume, custo e participação por modal — o KPI novo."""
    agg: dict[str, dict[str, float]] = {}
    for a in res.flows:
        m = agg.setdefault(a.modal, {"vol": 0.0, "cost": 0.0, "freight": 0.0})
        m["vol"] += a.vol
        m["cost"] += a.vol * a.unit
        m["freight"] += a.vol * a.frete
    rows = [{
        "Modal": modal,
        "Volume (m³)": round(m["vol"], 1),
        "Participação (%)": round(100 * m["vol"] / res.total_vol, 1) if res.total_vol else 0,
        "Frete médio (R$/m³)": round(m["freight"] / m["vol"], 2) if m["vol"] else 0,
        "Custo total (R$)": round(m["cost"], 0),
    } for modal, m in sorted(agg.items(), key=lambda kv: -kv[1]["vol"])]
    return pd.DataFrame(rows)


def polos_df(res: RunResult) -> pd.DataFrame:
    """Consumo por polo de disponibilidade (origem-fornecedor-produto)."""
    agg: dict[str, dict] = {}
    for a in res.flows:
        p = agg.setdefault(a.s.sid, {
            "forn": a.s.forn, "orig": a.s.ko, "prod": a.s.prod,
            "cap": a.s.max * res.params.cap_factor, "preco": a.s.preco,
            "vol": 0.0, "wfr": 0.0, "war": 0.0, "wtot": 0.0,
        })
        p["vol"] += a.vol
        p["wfr"] += a.frete * a.vol
        p["war"] += a.armaz * a.vol
        p["wtot"] += a.unit * a.vol
    rows = [{
        "Fornecedor": p["forn"], "Polo (origem)": p["orig"], "Produto": p["prod"],
        "Oferta (m³)": round(p["cap"], 0),
        "Consumido (m³)": round(p["vol"], 1),
        "Utilização (%)": round(100 * p["vol"] / p["cap"], 1) if p["cap"] else 0,
        "Produto (R$/m³)": round(p["preco"], 2),
        "Frete médio (R$/m³)": round(p["wfr"] / p["vol"], 2),
        "Armazenagem média (R$/m³)": round(p["war"] / p["vol"], 2),
        "Custo médio (R$/m³)": round(p["wtot"] / p["vol"], 2),
    } for p in sorted(agg.values(), key=lambda p: -p["vol"])]
    return pd.DataFrame(rows)


def atendimento_df(res: RunResult, base) -> pd.DataFrame:
    """Atendimento da demanda por filial-produto (% e custo médio)."""
    dem: dict[tuple[str, str], float] = {}
    for d in base.demand:
        dem[(d.kf, d.prod)] = dem.get((d.kf, d.prod), 0.0) + d.d
    got: dict[tuple[str, str], dict[str, float]] = {k: {"vol": 0.0, "cost": 0.0} for k in dem}
    for a in res.flows:
        g = got[(a.d.kf, a.d.prod)]
        g["vol"] += a.vol
        g["cost"] += a.vol * a.unit
    rows = [{
        "Filial": kf, "Produto": prod,
        "Demanda (m³)": round(tot, 1),
        "Atendido (m³)": round(got[(kf, prod)]["vol"], 1),
        "Atendimento (%)": round(100 * got[(kf, prod)]["vol"] / tot, 1) if tot else 0,
        "Custo médio (R$/m³)": round(got[(kf, prod)]["cost"] / got[(kf, prod)]["vol"], 2)
        if got[(kf, prod)]["vol"] else 0,
    } for (kf, prod), tot in sorted(dem.items())]
    return pd.DataFrame(rows)


def kpis(res: RunResult) -> dict:
    local_vol = sum(a.vol for a in res.flows if a.modal == MODAL_LOCAL)
    return {
        "Custo total (R$)": round(res.total_cost, 0),
        "Custo da molécula colocada (R$/m³)": round(res.avg_cost, 2),
        "Volume atendido (m³)": round(res.total_vol, 1),
        "Atendimento local (%)": round(100 * local_vol / res.total_vol, 1) if res.total_vol else 0,
        "Ruptura (m³)": round(sum(v for *_x, v in res.ruptures), 0),
    }


def audit_params(res: RunResult, src_name: str) -> dict:
    p = res.params
    return {
        "arquivo": src_name,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fatorCapacidade": p.cap_factor,
        "penalidadeRuptura (R$/m³)": p.rupture_penalty,
        "fornecedoresInativos": "; ".join(sorted(p.fornecedores_off)) or "nenhum",
        "origensExcluidas": "; ".join(sorted(p.origens_excluidas)) or "nenhuma",
        "status do solver": res.status,
        "arcos no modelo": res.n_arcs,
    }


def export_xlsx(res: RunResult, base, path: str, src_name: str = "") -> None:
    """Exporta o resultado completo com trilha de auditoria."""
    kpi_rows = [{"Indicador": k, "Valor": v} for k, v in kpis(res).items()]
    audit_rows = [{"Parâmetro": k, "Valor": str(v)}
                  for k, v in audit_params(res, src_name or base.src_name).items()]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        flows_df(res).to_excel(xw, sheet_name="Plano de atendimento", index=False)
        modal_mix_df(res).to_excel(xw, sheet_name="Mix modal", index=False)
        polos_df(res).to_excel(xw, sheet_name="Consumo por polo", index=False)
        atendimento_df(res, base).to_excel(xw, sheet_name="Atendimento da demanda", index=False)
        pd.DataFrame(kpi_rows).to_excel(xw, sheet_name="KPIs", index=False)
        pd.DataFrame(audit_rows).to_excel(xw, sheet_name="Auditoria", index=False)
