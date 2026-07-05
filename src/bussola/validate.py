"""Diagnóstico defensivo da base — as verificações que já custaram caro.

Portadas do protótipo HTML (frete em R$/L, cabeçalhos trocados, entrada
vazia, capacidade artificial...) mais as novas de modal. Mensagens de nível
'err' bloqueiam a rodada; 'warn' e 'ok' apenas informam.
"""

from dataclasses import dataclass

from .io_excel import Base
from .products import EXPECTED_MODALS, EXPECTED_PRODUCTS, MODAL_UNKNOWN


@dataclass
class Msg:
    level: str  # 'err' | 'warn' | 'ok'
    text: str


def _fmt(v: float, dec: int = 0) -> str:
    s = f"{v:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return s


def validate(base: Base) -> list[Msg]:
    M: list[Msg] = []
    sup_valid = [s for s in base.supply if s.max > 0]
    lane_idx = base.lane_index()

    # --- bloqueios estruturais ---
    if not base.supply:
        M.append(Msg("err", "Nenhuma linha válida na aba Disponibilidade. Verifique produto "
                            "(mesma grafia da Demanda), preço (R$/m³) e capacidade Máx (m³)."))
    elif not sup_valid:
        M.append(Msg("err", "Todas as origens têm capacidade Máx = 0. Sem oferta não há o que otimizar."))
    if not base.demand:
        M.append(Msg("err", "Nenhuma linha válida na aba Demanda. Esperado: filial, produto e demanda em m³ > 0."))
    if not base.lanes:
        M.append(Msg("err", "Nenhuma rota válida na Tabela de frete. Esperado: origem, destino, frete em R$/m³ > 0 e modal."))

    if base.prods:
        M.append(Msg("ok", "Produtos da rodada: " + " · ".join(base.prods) + " (aprendidos da aba Demanda)."))
        unexpected = [p for p in base.prods if p not in EXPECTED_PRODUCTS]
        if unexpected:
            M.append(Msg("warn", "Produto(s) fora da carteira esperada (S10, S500, GAA, AA, AH, BIODIESEL): "
                                 + ", ".join(unexpected) + ". Confira se não é erro de grafia."))
    for p in base.prods:
        if not any(s.prod == p for s in sup_valid):
            M.append(Msg("err", f"Produto {p} tem demanda mas nenhuma origem com capacidade na "
                                "Disponibilidade — resultaria em ruptura total. Confira a grafia nas duas abas."))

    n_routes = len({(ln.ko, ln.kd) for ln in base.lanes})
    M.append(Msg("ok", f"Linhas reconhecidas — frete: {n_routes} rotas ({len(base.lanes)} rota-modal) · "
                       f"disponibilidade: {len(sup_valid)} origens com capacidade · "
                       f"demanda: {len(base.demand)} registros."))
    if base.blank_freight:
        M.append(Msg("warn", f"{base.blank_freight} linha(s) de frete em branco ou inválida(s) foram ignoradas."))

    # --- modal ---
    sem_modal = sum(1 for ln in base.lanes if ln.modal == MODAL_UNKNOWN)
    if sem_modal:
        M.append(Msg("warn", f"{sem_modal} rota(s) sem modal informado — tratadas como modal "
                             f"'{MODAL_UNKNOWN}'. O custo é usado normalmente, mas o mix modal fica impreciso."))
    desconhecidos = sorted({ln.modal_raw for ln in base.lanes
                            if ln.modal not in EXPECTED_MODALS and ln.modal != MODAL_UNKNOWN})
    if desconhecidos:
        M.append(Msg("warn", "Modal(is) com grafia não reconhecida: " + ", ".join(desconhecidos)
                             + ". Esperados: Rodo, Ferro, Cabotagem, Duto, Hidro (e variações)."))

    # --- unidade do frete (R$/L disfarçado de R$/m³) ---
    fretes = sorted(ln.frete for ln in base.lanes)
    if fretes:
        med = fretes[len(fretes) // 2]
        if 0 < med < 10:
            M.append(Msg("err", f"Mediana de frete = R$ {_fmt(med, 3)}/m³ — parece estar em R$/litro. "
                                "Corrija a unidade antes de rodar."))

    # --- conectividade ---
    lane_orig = {ko for (ko, _kd) in lane_idx}
    orfas: dict[str, float] = {}
    for s in sup_valid:
        if s.ko not in lane_orig:
            orfas[s.ko] = orfas.get(s.ko, 0.0) + s.max
    for o, v in orfas.items():
        M.append(Msg("warn", f"Origem {o} tem {_fmt(v)} m³ de oferta mas nenhum frete de saída — "
                             "atenderá só a própria praça, se houver demanda local."))
    lane_dest = {kd for (_ko, kd) in lane_idx}
    sem_frete = sorted({
        d.kf for d in base.demand
        if d.kf not in lane_dest and not any(s.ko == d.kf for s in sup_valid)
    })
    if sem_frete:
        M.append(Msg("err", "Filiais sem nenhum frete de chegada nem oferta local: "
                            + ", ".join(sem_frete) + ". O modelo declararia ruptura nelas."))

    # --- capacidade artificial (Máx = Média × 1,2 em toda a base) ---
    with_med = [s for s in base.supply if s.med > 0]
    if len(with_med) > 3 and all(abs(s.max / s.med - 1.2) < 0.001 for s in with_med):
        M.append(Msg("warn", "Coluna Máx = Média × 1,20 em 100% das origens — capacidade artificial, "
                             "não contratada. Resultados que dependam do teto (ex.: volume importado) "
                             "são sensíveis a este dado."))

    # --- estoque e armazenagem ---
    if base.est_n:
        M.append(Msg("ok", f"Estoque considerado como origem: {base.est_n} ponto(s), "
                           f"{_fmt(base.est_vol)} m³ disponíveis (custo conforme informado; vazio = R$ 0/m³)."))
    if base.arm_n:
        M.append(Msg("ok", f"Custo de armazenagem aplicado a {base.arm_n} registro(s) de filial — "
                           "incluído no custo da molécula."))
    else:
        M.append(Msg("warn", "Aba Armazenagem sem custos — molécula calculada como produto + frete apenas."))

    # --- balanço capacidade doméstica × demanda ---
    for p in base.prods:
        dem = sum(d.d for d in base.demand if d.prod == p)
        cap = sum(s.max for s in base.supply if s.prod == p and s.forn.upper() != "IMPORTADO")
        if dem > 0 and cap < dem:
            M.append(Msg("warn", f"{p}: capacidade doméstica ({_fmt(cap)} m³) < demanda ({_fmt(dem)} m³). "
                                 f"Déficit de {_fmt(dem - cap)} m³ será coberto por importação ou ruptura."))

    return M


def has_errors(msgs: list[Msg]) -> bool:
    return any(m.level == "err" for m in msgs)
