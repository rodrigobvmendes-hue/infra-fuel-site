"""Normalização de produtos, modais e localidades."""

from bussola.products import MODAL_UNKNOWN, loc_base, norm, norm_modal, norm_product


def test_norm_strips_accents_case_spaces():
    assert norm("  Paulínia   Pool ") == "PAULINIA POOL"
    assert norm(None) is None


def test_product_aliases():
    assert norm_product("Diesel S10") == "S10"
    assert norm_product("diesel s-500") == "S500"
    assert norm_product("Gasolina A") == "GAA"
    assert norm_product("Etanol Anidro") == "AA"
    assert norm_product("álcool hidratado") == "AH"
    assert norm_product("B100") == "BIODIESEL"


def test_product_open_list_passes_through():
    # carteira aberta: produto desconhecido passa normalizado, sem bloqueio
    assert norm_product("QAV") == "QAV"


def test_modal_aliases_and_unknown():
    assert norm_modal("Rodo") == "RODOVIARIO"
    assert norm_modal("ferrovia") == "FERROVIARIO"
    assert norm_modal("Navio") == "CABOTAGEM"
    assert norm_modal("Duto") == "DUTOVIARIO"
    assert norm_modal("balsa") == "HIDROVIARIO"
    assert norm_modal(None) == MODAL_UNKNOWN
    assert norm_modal("") == MODAL_UNKNOWN


def test_loc_base_strips_parenthetical():
    assert loc_base("Santos (SP)") == "Santos"
    assert loc_base("Itaqui") == "Itaqui"
