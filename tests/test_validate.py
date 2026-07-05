"""Verificações defensivas — os erros que já custaram caro devem ser barrados."""

from bussola.io_excel import Base, Demand, Lane, Supply
from bussola.validate import has_errors, validate


def minimal_base() -> Base:
    b = Base()
    b.demand = [Demand(fil="A", prod="S10", d=100, kf="A")]
    b.prods = ["S10"]
    b.supply = [Supply(forn="F1", loc="X", prod="S10", preco=3000, max=200,
                       med=0, ko="X", sid="F1|X|S10#0")]
    b.lanes = [Lane(ko="X", kd="A", modal="RODOVIARIO", modal_raw="Rodo", frete=120)]
    return b


def _texts(msgs, level=None):
    return [m.text for m in msgs if level is None or m.level == level]


def test_clean_base_has_no_errors():
    assert not has_errors(validate(minimal_base()))


def test_empty_inputs_block_run():
    assert has_errors(validate(Base()))


def test_freight_in_reais_per_litre_blocks():
    b = minimal_base()
    b.lanes = [Lane(ko="X", kd="A", modal="RODOVIARIO", modal_raw="Rodo", frete=0.12)]
    msgs = validate(b)
    assert has_errors(msgs)
    assert any("R$/litro" in t for t in _texts(msgs, "err"))


def test_product_without_origin_blocks():
    b = minimal_base()
    b.demand.append(Demand(fil="A", prod="GAA", d=50, kf="A"))
    b.prods = ["GAA", "S10"]
    msgs = validate(b)
    assert has_errors(msgs)
    assert any("GAA" in t for t in _texts(msgs, "err"))


def test_filial_without_inbound_freight_blocks():
    b = minimal_base()
    b.demand.append(Demand(fil="Z", prod="S10", d=10, kf="Z"))
    msgs = validate(b)
    assert any("Z" in t and "frete de chegada" in t for t in _texts(msgs, "err"))


def test_artificial_capacity_warns():
    b = minimal_base()
    b.supply = [Supply(forn="F", loc=f"L{i}", prod="S10", preco=3000, max=120,
                       med=100, ko=f"L{i}", sid=f"F|L{i}|S10#{i}") for i in range(5)]
    b.lanes = [Lane(ko=f"L{i}", kd="A", modal="RODOVIARIO", modal_raw="Rodo", frete=100)
               for i in range(5)]
    msgs = validate(b)
    assert any("Máx = Média × 1,20" in t for t in _texts(msgs, "warn"))


def test_lane_without_modal_warns():
    b = minimal_base()
    b.lanes.append(Lane(ko="X", kd="A", modal="NAO INFORMADO", modal_raw="", frete=100))
    msgs = validate(b)
    assert any("sem modal informado" in t for t in _texts(msgs, "warn"))
    assert not has_errors(msgs)


def test_unknown_modal_spelling_warns():
    b = minimal_base()
    b.lanes.append(Lane(ko="X", kd="A", modal="TELETRANSPORTE", modal_raw="Teletransporte", frete=100))
    msgs = validate(b)
    assert any("Teletransporte" in t for t in _texts(msgs, "warn"))


def test_unexpected_product_warns_not_blocks():
    b = minimal_base()
    b.demand.append(Demand(fil="A", prod="QAV", d=10, kf="A"))
    b.prods = ["QAV", "S10"]
    b.supply.append(Supply(forn="F1", loc="X", prod="QAV", preco=4000, max=50,
                           med=0, ko="X", sid="F1|X|QAV#1"))
    msgs = validate(b)
    assert any("QAV" in t for t in _texts(msgs, "warn"))
    assert not has_errors(msgs)


def test_domestic_deficit_warns():
    b = minimal_base()
    b.supply[0].max = 60  # demanda 100 > capacidade 60
    msgs = validate(b)
    assert any("Déficit" in t for t in _texts(msgs, "warn"))
