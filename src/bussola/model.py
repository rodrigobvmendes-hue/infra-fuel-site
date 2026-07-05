"""Motor de otimização: LP de transporte multiproduto e multimodal (PuLP/CBC).

Variável de decisão: x[origem, destino, produto, MODAL] ≥ 0 (m³).
O modal não tem restrição de capacidade — o LP escolhe o mais barato de cada
rota e o REPORTA por fluxo (decisão de projeto: oportunidade, não ordem de
programação). A dimensão modal fica preservada para, no futuro, receber
limites físicos sem reescrever o modelo.

Restrições:
  - demanda por filial-produto: atendimento + ruptura == demanda
  - capacidade por origem-produto: Σ saídas ≤ Máx × fator de capacidade
  - ruptura penalizada (R$/m³) para o modelo nunca ser infactível
"""

from dataclasses import dataclass, field

import pulp

from .io_excel import Base, Demand, Supply
from .products import MODAL_LOCAL

DEFAULT_RUPTURE_PENALTY = 20_000.0  # R$/m³ — bem acima de qualquer molécula real


@dataclass
class Arc:
    """Um caminho possível: oferta s atende demanda d pelo modal, a custo unit."""

    s: Supply
    d: Demand
    modal: str
    frete: float
    armaz: float
    unit: float  # preço + frete + armazenagem (R$/m³)
    vol: float = 0.0  # preenchido após o solve


@dataclass
class RunParams:
    cap_factor: float = 1.0
    rupture_penalty: float = DEFAULT_RUPTURE_PENALTY
    fornecedores_off: set[str] = field(default_factory=set)
    origens_excluidas: set[str] = field(default_factory=set)


@dataclass
class RunResult:
    status: str                      # 'Optimal', 'Infeasible', ...
    flows: list[Arc]                 # arcos com volume alocado > 0
    ruptures: list[tuple[str, str, float]]  # (filial, produto, m³ não atendidos)
    total_cost: float                # custo real dos fluxos (sem penalidade)
    total_vol: float
    n_arcs: int
    params: RunParams

    @property
    def feasible(self) -> bool:
        return self.status == "Optimal"

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.total_vol if self.total_vol else 0.0


def build_arcs(base: Base, params: RunParams) -> list[Arc]:
    """Enumera os caminhos válidos: mesmo produto e (rota-modal ou praça local)."""
    sup = [
        s for s in base.supply
        if s.max > 0
        and s.forn not in params.fornecedores_off
        and s.ko not in params.origens_excluidas
    ]
    lane_idx = base.lane_index()
    arcs: list[Arc] = []
    for s in sup:
        for d in base.demand:
            if s.prod != d.prod:
                continue
            ar = base.arm_cost(d.kf, d.prod)
            if s.ko == d.kf:
                # atendimento na própria praça: frete zero, modal sintético LOCAL
                arcs.append(Arc(s=s, d=d, modal=MODAL_LOCAL, frete=0.0,
                                armaz=ar, unit=s.preco + ar))
                continue
            for ln in lane_idx.get((s.ko, d.kf), []):
                arcs.append(Arc(s=s, d=d, modal=ln.modal, frete=ln.frete,
                                armaz=ar, unit=s.preco + ln.frete + ar))
    return arcs


def solve(base: Base, params: RunParams | None = None) -> RunResult:
    """Monta e resolve o LP; devolve fluxos com modal reportado por arco."""
    params = params or RunParams()
    arcs = build_arcs(base, params)

    prob = pulp.LpProblem("bussola", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x{i}", lowBound=0) for i in range(len(arcs))]

    # ruptura por demanda agregada (filial, produto)
    dem_tot: dict[tuple[str, str], float] = {}
    for d in base.demand:
        dem_tot[(d.kf, d.prod)] = dem_tot.get((d.kf, d.prod), 0.0) + d.d
    slack = {k: pulp.LpVariable(f"F_{i}", lowBound=0) for i, k in enumerate(dem_tot)}

    prob += (
        pulp.lpSum(x[i] * a.unit for i, a in enumerate(arcs))
        + pulp.lpSum(v * params.rupture_penalty for v in slack.values())
    )

    arcs_by_dem: dict[tuple[str, str], list[int]] = {k: [] for k in dem_tot}
    arcs_by_sup: dict[str, list[int]] = {}
    for i, a in enumerate(arcs):
        arcs_by_dem[(a.d.kf, a.d.prod)].append(i)
        arcs_by_sup.setdefault(a.s.sid, []).append(i)

    for k, tot in dem_tot.items():
        prob += pulp.lpSum(x[i] for i in arcs_by_dem[k]) + slack[k] == tot
    for sid, idxs in arcs_by_sup.items():
        cap = next(s.max for s in base.supply if s.sid == sid) * params.cap_factor
        prob += pulp.lpSum(x[i] for i in idxs) <= cap

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]

    flows: list[Arc] = []
    for i, a in enumerate(arcs):
        v = x[i].value() or 0.0
        if v > 0.01:
            a.vol = v
            flows.append(a)
    ruptures = [
        (kf, prod, slack[(kf, prod)].value() or 0.0)
        for (kf, prod) in dem_tot
        if (slack[(kf, prod)].value() or 0.0) > 0.01
    ]
    total_vol = sum(a.vol for a in flows)
    total_cost = sum(a.vol * a.unit for a in flows)
    return RunResult(status=status, flows=flows, ruptures=ruptures,
                     total_cost=total_cost, total_vol=total_vol,
                     n_arcs=len(arcs), params=params)
