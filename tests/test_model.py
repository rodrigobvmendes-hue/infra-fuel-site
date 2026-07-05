"""Testes do motor LP — escolha de modal, ruptura, local e número de regressão.

O caso-base tem ótimo calculado à mão; se qualquer mudança no motor alterar
esses números, o teste quebra. Quando a base real for disponibilizada, um
segundo golden test deve travar o número oficial (R$ 574,2 MM).
"""

import pytest

from bussola.io_excel import Base, Demand, Lane, Supply
from bussola.model import RunParams, solve
from bussola.products import MODAL_LOCAL


def base_case() -> Base:
    """2 origens, 2 filiais, 2 produtos, modais concorrentes na rota X→A."""
    b = Base()
    b.demand = [
        Demand(fil="Fil A", prod="S10", d=100, kf="FIL A"),
        Demand(fil="Fil B", prod="S500", d=50, kf="FIL B"),
    ]
    b.prods = ["S10", "S500"]
    b.supply = [
        Supply(forn="F1", loc="X", prod="S10", preco=3000, max=80, med=0, ko="X", sid="F1|X|S10#0"),
        Supply(forn="F2", loc="Y", prod="S10", preco=3100, max=100, med=0, ko="Y", sid="F2|Y|S10#1"),
        Supply(forn="F1", loc="X", prod="S500", preco=2900, max=60, med=0, ko="X", sid="F1|X|S500#2"),
    ]
    b.lanes = [
        Lane(ko="X", kd="FIL A", modal="RODOVIARIO", modal_raw="Rodo", frete=120),
        Lane(ko="X", kd="FIL A", modal="FERROVIARIO", modal_raw="Ferro", frete=80),
        Lane(ko="Y", kd="FIL A", modal="RODOVIARIO", modal_raw="Rodo", frete=90),
        Lane(ko="X", kd="FIL B", modal="RODOVIARIO", modal_raw="Rodo", frete=70),
    ]
    return b


def test_regression_optimal_cost():
    """Golden number do caso-base: R$ 458.700 em 150 m³ (calculado à mão)."""
    res = solve(base_case())
    assert res.feasible
    # S10: 80 m³ por X-Ferro (3.080) + 20 m³ por Y-Rodo (3.190) = 310.200
    # S500: 50 m³ por X-Rodo (2.970) = 148.500
    assert res.total_cost == pytest.approx(458_700)
    assert res.total_vol == pytest.approx(150)
    assert not res.ruptures


def test_modal_choice_is_reported():
    """O LP deve preferir a ferrovia (frete 80 < 120) e reportar o modal."""
    res = solve(base_case())
    s10_x = [a for a in res.flows if a.d.prod == "S10" and a.s.ko == "X"]
    assert len(s10_x) == 1
    assert s10_x[0].modal == "FERROVIARIO"
    assert s10_x[0].vol == pytest.approx(80)
    s10_y = [a for a in res.flows if a.d.prod == "S10" and a.s.ko == "Y"]
    assert s10_y[0].modal == "RODOVIARIO"
    assert s10_y[0].vol == pytest.approx(20)


def test_rupture_when_supply_short():
    b = base_case()
    b.demand[0] = Demand(fil="Fil A", prod="S10", d=200, kf="FIL A")
    res = solve(b)
    assert res.feasible  # ruptura penalizada, nunca infactível
    rupt = {(kf, p): v for kf, p, v in res.ruptures}
    assert rupt[("FIL A", "S10")] == pytest.approx(20)  # 200 dem − 180 cap
    # custo real exclui a penalidade: 80×3.080 + 100×3.190 + 148.500
    assert res.total_cost == pytest.approx(80 * 3080 + 100 * 3190 + 148_500)


def test_local_supply_has_zero_freight():
    b = base_case()
    b.supply.append(Supply(forn="F3", loc="Fil A", prod="S10", preco=2950,
                           max=100, med=0, ko="FIL A", sid="F3|FIL A|S10#3"))
    res = solve(b)
    local = [a for a in res.flows if a.modal == MODAL_LOCAL]
    assert local and local[0].frete == 0
    assert local[0].vol == pytest.approx(100)  # 2.950 local bate qualquer rota


def test_cap_factor_scales_capacity():
    b = base_case()
    res = solve(b, RunParams(cap_factor=0.5))
    rupt = {(kf, p): v for kf, p, v in res.ruptures}
    # S10: capacidade vira 40+50=90 < 100 → ruptura 10
    # S500: capacidade vira 30 < 50 → ruptura 20
    assert rupt[("FIL A", "S10")] == pytest.approx(10)
    assert rupt[("FIL B", "S500")] == pytest.approx(20)


def test_fornecedor_off_removes_supply():
    b = base_case()
    res = solve(b, RunParams(fornecedores_off={"F2"}))
    assert not any(a.s.forn == "F2" for a in res.flows)
    assert sum(v for *_k, v in res.ruptures) == pytest.approx(20)  # só X: 80 de 100


def test_armazenagem_added_to_unit_cost():
    b = base_case()
    b.arm = {"FIL A|S10": 15.0}
    res = solve(b)
    s10_a = [a for a in res.flows if a.d.prod == "S10"]
    assert all(a.armaz == 15.0 for a in s10_a)
    assert res.total_cost == pytest.approx(458_700 + 15 * 100)
