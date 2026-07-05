"""Normalização de nomes — produtos, modais e localidades.

A carteira de produtos é ABERTA: qualquer produto presente na aba Demanda
entra na rodada. Os seis produtos esperados (S10, S500, GAA, AA, AH,
BIODIESEL) têm aliases reconhecidos; grafias fora da lista geram apenas
aviso no diagnóstico, nunca bloqueio.
"""

import unicodedata

# Produtos esperados da operação (carteira aberta — apenas referência)
EXPECTED_PRODUCTS = ["S10", "S500", "GAA", "AA", "AH", "BIODIESEL"]

# Aliases → produto canônico (chaves já normalizadas: maiúsculas, sem acento)
PRODUCT_ALIAS = {
    "DIESEL S10": "S10",
    "DIESEL S-10": "S10",
    "OLEO DIESEL S10": "S10",
    "S-10": "S10",
    "DIESEL S500": "S500",
    "DIESEL S-500": "S500",
    "OLEO DIESEL S500": "S500",
    "S-500": "S500",
    "GASOLINA A": "GAA",
    "GASOLINA": "GAA",
    "GAS A": "GAA",
    "ETANOL ANIDRO": "AA",
    "ANIDRO": "AA",
    "ALCOOL ANIDRO": "AA",
    "EAC": "AA",
    "ETANOL HIDRATADO": "AH",
    "HIDRATADO": "AH",
    "ALCOOL HIDRATADO": "AH",
    "EHC": "AH",
    "B100": "BIODIESEL",
    "BIO": "BIODIESEL",
    "BIODIESEL B100": "BIODIESEL",
}

# Modais canônicos e aliases
EXPECTED_MODALS = ["RODOVIARIO", "FERROVIARIO", "CABOTAGEM", "DUTOVIARIO", "HIDROVIARIO"]

MODAL_ALIAS = {
    "RODO": "RODOVIARIO",
    "RODOVIA": "RODOVIARIO",
    "CAMINHAO": "RODOVIARIO",
    "FERRO": "FERROVIARIO",
    "FERROVIA": "FERROVIARIO",
    "TREM": "FERROVIARIO",
    "CABOTAGEM": "CABOTAGEM",
    "MARITIMO": "CABOTAGEM",
    "NAVIO": "CABOTAGEM",
    "DUTO": "DUTOVIARIO",
    "OLEODUTO": "DUTOVIARIO",
    "POLIDUTO": "DUTOVIARIO",
    "HIDRO": "HIDROVIARIO",
    "HIDROVIA": "HIDROVIARIO",
    "BALSA": "HIDROVIARIO",
    "BARCACA": "HIDROVIARIO",
}

# Modal atribuído quando a coluna Modal vem em branco na Tabela de frete
MODAL_UNKNOWN = "NAO INFORMADO"

# Modal sintético do atendimento na própria praça (origem == destino, frete 0)
MODAL_LOCAL = "LOCAL"


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def norm(s) -> str | None:
    """Normaliza um nome: maiúsculas, sem acento, espaços colapsados."""
    if s is None:
        return None
    s = strip_accents(str(s).upper().strip())
    return " ".join(s.split())


def norm_product(s) -> str | None:
    """Produto canônico via aliases; grafia desconhecida passa normalizada."""
    n = norm(s)
    if not n:
        return None
    return PRODUCT_ALIAS.get(n, n)


def norm_modal(s) -> str:
    """Modal canônico via aliases; branco vira MODAL_UNKNOWN."""
    n = norm(s)
    if not n:
        return MODAL_UNKNOWN
    return MODAL_ALIAS.get(n, n)


def loc_base(s) -> str:
    """Remove sufixo entre parênteses de uma localidade: 'Santos (SP)' → 'Santos'."""
    return str(s).split("(")[0].strip()
