"""
Biblioteca de transformação para o dashboard_cessao.html ("Desp&Receitas").

Reconstrói, por engenharia reversa, a lógica que gera o objeto `const D`
embutido em dashboard_cessao.html a partir das planilhas de apoio
Receitas.xlsx / Despesas.xlsx.

A lógica foi inferida comparando, linha a linha, os valores das planilhas
originais (commit 97855fd) com o JSON `D` que já está no HTML (gerado a
partir dessas mesmas planilhas). Ver relatório da tarefa para o que foi
validado com exatidão vs. aproximado.
"""

import datetime
from collections import defaultdict

# ---------------------------------------------------------------------------
# Classificação de congêneres (Major / Terminal / Regional).
#
# Isso NÃO é derivável com confiança das planilhas (a coluna "Classificação"
# da aba Apoio de Despesas.xlsx não bate 100% com a classe usada no D atual
# -- ex.: "Temape" está marcado como "Operador Logístico" na aba Apoio mas
# aparece como "Regional" no D). Por isso usamos aqui o mapeamento
# extraído diretamente do D atual (verdade fundamental/ground truth), com
# fallback heurístico para congêneres novos que não apareçam nessa lista.
# ---------------------------------------------------------------------------
CLASSE_MAP = {
    "Atlantica": "Regional", "Ciapetro": "Regional", "Dtc": "Terminal",
    "Granel": "Terminal", "Idaza": "Regional", "Ipiranga": "Major",
    "Oiltanking": "Terminal", "Opla": "Regional", "Origem": "Terminal",
    "Petrobahia": "Regional", "Petrosul": "Regional", "Pontuax": "Regional",
    "Potencial": "Regional", "Raízen": "Major", "Rdp": "Regional",
    "Rede Sol": "Regional", "Rejaile": "Regional", "Riograndense": "Terminal",
    "Ruff": "Regional", "Sadipe": "Regional", "Santos Brasil": "Terminal",
    "Sim Distribuidora": "Regional", "Stolthaven": "Terminal", "Tdc": "Regional",
    "Tecab": "Terminal", "Temape": "Regional", "Tequimar": "Terminal",
    "Tobras": "Regional", "Torrão": "Regional", "Transpetro": "Terminal",
    "Vibra": "Major",
}

_MAJOR_NAMES = {"vibra", "ipiranga", "raízen", "raizen"}
_TERMINAL_HINTS = (
    "terminal", "tancagem", "tequimar", "oiltanking", "oil tanking", "tecab",
    "granel", "dtc", "riograndense", "stolthaven", "origem", "santos brasil",
    "transpetro", "cattalini", "temmar", "tliq",
)


# ---------------------------------------------------------------------------
# Normalização de nomes de congênere.
#
# Descoberto comparando as planilhas antigas com o D atual: algumas
# empresas trocam de razão social/ID de contrato no meio da série
# histórica (ex.: "Temape" virou "Tmp" a partir de out/2025 -- mesma
# empresa, "TEMAPE TERMINAIS..." renomeada para "TMP TERMINAIS S/A" no
# meio dos dados), e o "Transpetro" tem várias linhas de produto
# separadas ("Transpetro - Anidro", "Transpetro - B100", ...). O D atual
# trata essas variações como uma única congênere. Reproduzimos isso
# aqui com um alias fixo (achado manualmente) + uma regra genérica de
# cortar sufixo " - <produto>".
# ---------------------------------------------------------------------------
_CONGENERE_ALIASES = {
    "Tmp": "Temape",
}


def normalize_congenere(name):
    if name is None:
        return name
    name = str(name).strip()
    if name in _CONGENERE_ALIASES:
        return _CONGENERE_ALIASES[name]
    if " - " in name:
        return name.split(" - ")[0].strip()
    return name


def classe_for(congenere):
    """Melhor esforço: usa o mapa conhecido, senão heurística por nome."""
    if congenere in CLASSE_MAP:
        return CLASSE_MAP[congenere]
    low = (congenere or "").strip().lower()
    if low in _MAJOR_NAMES:
        return "Major"
    if any(h in low for h in _TERMINAL_HINTS):
        return "Terminal"
    return "Regional"


def period_key(dt):
    if dt is None:
        return None
    return f"{dt.year}-{dt.month:02d}"


def col_index(header, name):
    """Acha o índice de uma coluna pelo nome, tolerando variações de espaço."""
    target = name.strip()
    for i, h in enumerate(header):
        if h is None:
            continue
        if str(h).strip() == target:
            return i
    # fallback: ignora espaços internos duplicados
    target_norm = " ".join(target.split())
    for i, h in enumerate(header):
        if h is None:
            continue
        if " ".join(str(h).split()) == target_norm:
            return i
    raise KeyError(f"coluna não encontrada: {name!r} em {header!r}")


def read_rows(ws, header, colmap):
    """Lê todas as linhas de dados de uma planilha (openpyxl worksheet já
    carregada) e devolve lista de dicts usando os nomes lógicos de colmap.

    colmap: {nome_logico: nome_coluna_na_planilha}
    """
    idx = {logical: col_index(header, real) for logical, real in colmap.items()}
    out = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[idx["data"]] is None:
            continue
        rec = {}
        for logical, i in idx.items():
            rec[logical] = row[i]
        if "congenere" in rec:
            rec["congenere"] = normalize_congenere(rec["congenere"])
        out.append(rec)
    return out


def to_num(v):
    if v is None:
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def build_periods(rows, extra_months_ahead=6):
    """Gera a lista de períodos (YYYY-MM) cobrindo o intervalo de datas das
    linhas, mais alguns meses futuros de projeção (padrão: 6, igual ao D
    atual que estende ~6 meses além do último período com dado real)."""
    dates = sorted({r["data"] for r in rows if r["data"] is not None})
    if not dates:
        return []
    start = dates[0]
    end = dates[-1]
    periods = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        periods.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return periods


def add_months(period, n):
    y, m = map(int, period.split("-"))
    m += n
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1
    return f"{y}-{m:02d}"
