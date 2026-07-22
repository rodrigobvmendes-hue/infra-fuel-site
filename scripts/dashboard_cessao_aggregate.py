"""
Funções de agregação que constroem cada bloco do JSON `D` do
dashboard_cessao.html a partir das linhas normalizadas lidas de
Receitas.xlsx / Despesas.xlsx.

Ver dashboard_cessao_lib.py para o parsing bruto das planilhas e notas
sobre o que foi validado com exatidão vs. aproximado.
"""

from collections import defaultdict

from dashboard_cessao_lib import classe_for, period_key, add_months


def aggregate_monthly(rows, periods):
    by_period = defaultdict(list)
    for r in rows:
        p = period_key(r["data"])
        if p:
            by_period[p].append(r)

    out = []
    for p in periods:
        rows_p = by_period.get(p, [])
        year = int(p.split("-")[0])
        n_total = len(rows_p)
        n_real = sum(1 for r in rows_p if r["valor_total"] not in (None, 0))
        orc = sum((r["orc"] or 0) for r in rows_p)
        real = sum((r["valor_total"] or 0) for r in rows_p if r["valor_total"] is not None)
        if n_real == 0:
            # Período sem nenhuma realização (projetado): usa o volume
            # orçado como estimativa, já que não há Vol. Movimentado.
            vol = sum((r.get("vol_orc") or 0) for r in rows_p)
        else:
            vol = sum((r["vol_mov"] or 0) for r in rows_p if r["vol_mov"] is not None)

        val_a = sum((r["valor_total"] or 0) for r in rows_p if r["vol_mov"] and r["vol_mov"] > 0)
        vol_a = sum((r["vol_mov"] or 0) for r in rows_p if r["vol_mov"] and r["vol_mov"] > 0)
        tarifa_ef = round(val_a / vol_a, 6) if vol_a else None

        top = sum(_row_top(r) for r in rows_p)
        is_proj = 1 if n_real == 0 else 0

        out.append({
            "period": p, "year": year, "is_proj": is_proj,
            "orc": round(orc, 4), "real": round(real, 4),
            "n_real": n_real, "n_total": n_total,
            "vol": round(vol, 4) if not is_proj else round(vol, 6),
            "tarifa_ef": tarifa_ef, "top": round(top, 6),
        })
    return out


def _row_top(r):
    """Take or Pay de uma linha. Usa a coluna direta quando existe
    (Despesas.xlsx tem 'Take or Pay' pronto); senão calcula
    max(0, Valor Contrato - Valor Movimentado), que reproduz a mesma
    coluna com precisão de centavos onde pôde ser conferido.

    Em ambos os casos, só conta TOP para linhas com valor realizado
    (Valor Total R$ != None/0) -- linhas "Sem dado" nunca geram TOP,
    mesmo que Valor Contrato/Valor Movimentado estejam preenchidos com
    valores "fantasma" da planilha (confirmado comparando com o D atual)."""
    if r["valor_total"] in (None, 0):
        return 0.0
    if r.get("top_col") is not None:
        return r["top_col"] or 0
    vc = r.get("valor_contrato")
    vm = r.get("valor_movimentado")
    if vc is None:
        return 0.0
    return max(0.0, (vc or 0) - (vm or 0))


def build_contracts(rows, lado, periods_set=None):
    """Um registro por (período, filial, congênere), a partir das linhas
    com TIPO DE COBRANÇA == 'Operação Normal' (a única linha, dentre as
    ~4-6 por combinação, que carrega os dados de realização/contrato)."""
    out = []
    for r in rows:
        if r["tipo"] != "Operação Normal":
            continue
        p = period_key(r["data"])
        if periods_set is not None and p not in periods_set:
            continue

        vol_minimo = r["vol_minimo"]
        if not vol_minimo:
            vol_minimo = None

        vol_mov = r["vol_mov"]
        valor_total = r["valor_total"]
        is_realizado = valor_total not in (None, 0)
        valor = valor_total if is_realizado else (r["orc"] or 0)

        top = round(_row_top(r), 6)

        utilizacao = None
        if vol_minimo and vol_mov is not None:
            utilizacao = round(100 * vol_mov / vol_minimo, 1)

        if not is_realizado:
            status = "Sem dado"
        elif top > 0:
            status = "TOP Gerado" if lado == "D" else "TOP Recebido"
        elif vol_minimo is not None and vol_mov is not None and vol_mov < vol_minimo:
            status = "Abaixo Mínimo"
        else:
            status = "Normal"

        out.append({
            "period": p, "filial": r["filial"], "congenere": r["congenere"],
            "classe": classe_for(r["congenere"]),
            "vol_minimo": vol_minimo, "vol_1giro": r["vol_1giro"] or 0,
            "tarifa_1giro": r["tarifa_1giro"] or 0, "tarifa_2giro": r["tarifa_2giro"] or 0,
            "tarifa_efetiva": r["tarifa_efetiva"],
            "vol_mov": vol_mov, "utilizacao": utilizacao,
            "top": top, "valor": round(valor, 4) if valor is not None else 0,
            "is_realizado": is_realizado, "status": status, "lado": lado,
        })
    return out


def aggregate_filial(contracts, periods):
    def agg(items):
        by_filial = defaultdict(lambda: {"valor": 0.0, "vol": 0.0})
        dom = defaultdict(lambda: defaultdict(float))
        for c in items:
            # dominância usa todo contrato (com fallback orçado quando
            # não há realizado ainda), para que toda filial tenha uma
            # classe dominante mesmo sem nenhum mês realizado
            dom[c["filial"]][c["congenere"]] += c["valor"] or 0
            if not c["is_realizado"]:
                continue
            by_filial[c["filial"]]["valor"] += c["valor"] or 0
            by_filial[c["filial"]]["vol"] += c["vol_mov"] or 0
        # inclui toda filial com pelo menos um contrato (mesmo sem
        # nenhum valor realizado ainda), igual ao D atual
        all_filiais = {c["filial"] for c in items}
        result = []
        for filial in all_filiais:
            v = by_filial.get(filial, {"valor": 0.0, "vol": 0.0})
            dom_cong = max(dom[filial], key=dom[filial].get) if dom[filial] else None
            classe_dom = classe_for(dom_cong) if dom_cong else None
            tarifa = round(v["valor"] / v["vol"], 6) if v["vol"] else 0
            result.append({
                "filial": filial, "valor": round(v["valor"], 4),
                "vol": round(v["vol"], 4), "tarifa": tarifa, "classe_dom": classe_dom,
            })
        result.sort(key=lambda x: -x["valor"])
        return result

    out = {"__all__": agg(contracts)}
    for p in periods:
        out[p] = agg([c for c in contracts if c["period"] == p])
    return out


def aggregate_cong(contracts, rows, periods):
    def agg_valor_vol(items):
        by_cong = defaultdict(lambda: {"valor": 0.0, "vol": 0.0})
        for c in items:
            if not c["is_realizado"]:
                continue
            by_cong[c["congenere"]]["valor"] += c["valor"] or 0
            by_cong[c["congenere"]]["vol"] += c["vol_mov"] or 0
        return by_cong

    def agg_orc(rows_subset):
        by_cong = defaultdict(float)
        for r in rows_subset:
            by_cong[r["congenere"]] += r["orc"] or 0
        return by_cong

    def build(items, rows_subset):
        vv = agg_valor_vol(items)
        orc = agg_orc(rows_subset)
        congs = {c["congenere"] for c in items} | set(orc.keys())
        result = []
        for cong in congs:
            v = vv.get(cong, {"valor": 0.0, "vol": 0.0})
            tarifa = round(v["valor"] / v["vol"], 6) if v["vol"] else 0
            result.append({
                "congenere": cong, "classe": classe_for(cong),
                "valor": round(v["valor"], 4), "orc": round(orc.get(cong, 0), 4),
                "vol": round(v["vol"], 4), "tarifa": tarifa,
            })
        result.sort(key=lambda x: -x["valor"])
        return result

    out = {"__all__": build(contracts, rows)}
    for p in periods:
        rows_p = [r for r in rows if period_key(r["data"]) == p]
        contracts_p = [c for c in contracts if c["period"] == p]
        out[p] = build(contracts_p, rows_p)
    return out


def build_kpi(contracts, monthly):
    non_proj = [m for m in monthly if not m["is_proj"]]
    if not non_proj:
        last6_periods = []
        last_period = None
    else:
        last6_periods = [m["period"] for m in non_proj[-6:]]
        last_period = non_proj[-1]["period"]

    real_c = [c for c in contracts if c["period"] in last6_periods and c["is_realizado"]]
    total = sum(c["valor"] or 0 for c in real_c)
    vol = sum(c["vol_mov"] or 0 for c in real_c if c["vol_mov"] is not None)
    top = sum(c["top"] or 0 for c in real_c)
    tef = round(total / vol, 6) if vol else 0
    top_pct = round(top / total * 100, 6) if total else 0

    # total_n / top_n: melhor esforço -- fotografia do último período
    # fechado (contratos realizados / em TOP nesse mês). Não foi possível
    # reproduzir os valores exatos do D atual com confiança total; ver
    # relatório da tarefa.
    last_c = [c for c in contracts if c["period"] == last_period]
    total_n = sum(1 for c in last_c if c["is_realizado"])
    top_status = "TOP Gerado" if contracts and contracts[0]["lado"] == "D" else "TOP Recebido"
    top_n = sum(1 for c in last_c if c["status"] == top_status)

    return {
        "total": round(total, 4), "vol": round(vol, 4), "tef": tef,
        "top": round(top, 6), "top_pct": top_pct,
        "top_n": top_n, "total_n": total_n, "last_period": last_period,
    }


def build_top_data(contracts, monthly):
    # by_period usa a mesma base que by_filial (TOP por contrato,
    # somente linhas "Operação Normal" realizadas) -- NÃO é igual a
    # monthly.top (que soma TOP de todos os tipos de cobrança); os dois
    # divergem em alguns meses no D atual, e bater com contracts é o
    # que reproduz o total por filial corretamente.
    per_period_top = defaultdict(float)
    for c in contracts:
        if c["is_realizado"]:
            per_period_top[c["period"]] += c["top"] or 0
    by_period = [{"period": m["period"], "top": round(per_period_top.get(m["period"], 0), 2)} for m in monthly]

    by_filial = defaultdict(lambda: defaultdict(float))
    filial_classe = {}
    for c in contracts:
        if not c["is_realizado"]:
            continue
        by_filial[c["filial"]][c["period"]] += c["top"] or 0
        if c["top"]:
            filial_classe[c["filial"]] = c["classe"]

    result = []
    for filial, per_period in by_filial.items():
        top_total = sum(per_period.values())
        if top_total <= 0:
            continue
        monthly_list = [{"period": p, "top": round(v, 2)} for p, v in sorted(per_period.items())]
        result.append({
            "filial": filial, "classe": filial_classe.get(filial, classe_for("")),
            "top_total": round(top_total, 2), "monthly": monthly_list,
        })
    result.sort(key=lambda x: -x["top_total"])
    return {"by_period": by_period, "by_filial": result}


def build_topmon(contracts, top_status, min_consec=3):
    """Contratos com sequência de meses consecutivos em TOP (>= min_consec).
    Estrutura e campos numéricos são recalculados diretamente dos
    contratos; o texto de 'alerta' é melhor-esforço (só um nível de
    severidade foi confirmado nas amostras do D atual)."""
    by_combo = defaultdict(list)
    for c in contracts:
        by_combo[(c["filial"], c["congenere"])].append(c)

    result = []
    for (filial, cong), items in by_combo.items():
        items.sort(key=lambda x: x["period"])
        streak = 0
        max_consec = 0
        top_periods = []
        for c in items:
            if c["status"] == top_status:
                streak += 1
                top_periods.append(c)
            else:
                streak = 0
            max_consec = max(max_consec, streak)
        n_meses_top = len(top_periods)
        if max_consec < min_consec or n_meses_top == 0:
            continue
        top_total = sum(c["top"] or 0 for c in top_periods)
        vol_medio = sum((c["vol_mov"] or 0) for c in top_periods) / n_meses_top
        vol_minimo = next((c["vol_minimo"] for c in items if c["vol_minimo"]), None)
        gap_medio = round(vol_minimo - vol_medio, 0) if vol_minimo else None
        classe = items[0]["classe"]
        result.append({
            "filial": filial, "congenere": cong, "classe": classe,
            "n_meses_top": n_meses_top, "top_total": round(top_total, 2),
            "top_medio": round(top_total / n_meses_top, 2),
            "vol_minimo": vol_minimo, "vol_medio": round(vol_medio, 0),
            "gap_medio": gap_medio, "max_consec": max_consec,
            "alerta": "🟡 3+ meses consecutivos" if max_consec < 6 else "🔴 6+ meses consecutivos",
        })
    result.sort(key=lambda x: -x["top_total"])
    return result


def _row_valor(r):
    """Valor 'efetivo' de uma linha: realizado quando existe, senão o
    orçado como estimativa (mesma regra usada em contracts.valor, mas
    aqui aplicada a TODAS as linhas de TIPO DE COBRANÇA, não só
    'Operação Normal' -- é a base que a seção `sinergia` usa)."""
    vt = r["valor_total"]
    return vt if vt not in (None, 0) else (r["orc"] or 0)


def _cong_period_totals(rows):
    """Agrega (valor, volume, top) por (congênere, período), somando
    TODAS as linhas de tipo de cobrança -- é o mesmo estilo de cálculo
    de `aggregate_monthly`, mas quebrado por congênere."""
    out = defaultdict(lambda: defaultdict(lambda: {"val": 0.0, "vol": 0.0, "top": 0.0}))
    filiais = defaultdict(set)
    for r in rows:
        p = period_key(r["data"])
        cong = r["congenere"]
        bucket = out[cong][p]
        bucket["val"] += _row_valor(r)
        if r["vol_mov"]:
            bucket["vol"] += r["vol_mov"]
        bucket["top"] += _row_top(r)
        if r["tipo"] == "Operação Normal":
            filiais[cong].add(r["filial"])
    return out, filiais


def _contract_to_row(c):
    return {
        "period": c["period"], "filial": c["filial"], "lado": c["lado"],
        "congenere": c["congenere"], "classe": c["classe"],
        "vol_minimo": c["vol_minimo"], "vol_mov": c["vol_mov"],
        "utilizacao": c["utilizacao"], "tarifa_ef": c["tarifa_efetiva"],
        "valor": c["valor"], "top": c["top"],
    }


def build_sinergia(d_contracts, r_contracts, d_rows, r_rows):
    """Nota sobre d_pct/r_pct: o denominador (total geral, todas as
    linhas, com fallback orçado) reproduz o percentual do D atual com
    ~1 ponto percentual de diferença no lado despesas e ~0,15 ponto no
    lado receitas -- não foi possível fechar a fórmula exata (ver
    relatório da tarefa); os valores absolutos (d_total/r_total,
    d_top/r_top etc.) batem exatamente."""
    d_congs = {c["congenere"] for c in d_contracts}
    r_congs = {c["congenere"] for c in r_contracts}
    bilaterais = sorted(d_congs & r_congs)

    d_by_cong_period, d_filiais = _cong_period_totals(d_rows)
    r_by_cong_period, r_filiais = _cong_period_totals(r_rows)

    by_cong = {}
    for cong in bilaterais:
        d_periods = d_by_cong_period.get(cong, {})
        r_periods = r_by_cong_period.get(cong, {})
        d_val = sum(b["val"] for b in d_periods.values())
        d_vol = sum(b["vol"] for b in d_periods.values())
        d_top = sum(b["top"] for b in d_periods.values())
        r_val = sum(b["val"] for b in r_periods.values())
        r_vol = sum(b["vol"] for b in r_periods.values())

        periods = sorted(set(d_periods.keys()) | set(r_periods.keys()))
        monthly = []
        for p in periods:
            db = d_periods.get(p, {"val": 0, "vol": 0, "top": 0})
            rb = r_periods.get(p, {"val": 0, "vol": 0, "top": 0})
            monthly.append({
                "period": p,
                "d_val": round(db["val"], 2), "d_vol": round(db["vol"], 3),
                "d_tef": round(db["val"] / db["vol"], 6) if db["vol"] else 0,
                "d_top": round(db["top"], 6),
                "r_val": round(rb["val"], 2), "r_vol": round(rb["vol"], 3),
                "r_tef": round(rb["val"] / rb["vol"], 6) if rb["vol"] else 0,
            })

        by_cong[cong] = {
            "classe": classe_for(cong),
            "d_total": round(d_val, 4), "d_vol": round(d_vol, 3),
            "d_tef": round(d_val / d_vol, 6) if d_vol else 0,
            "d_top": round(d_top, 6),
            "d_contratos": len(d_filiais.get(cong, ())),
            "r_total": round(r_val, 4), "r_vol": round(r_vol, 3),
            "r_tef": round(r_val / r_vol, 6) if r_vol else 0,
            "r_contratos": len(r_filiais.get(cong, ())),
            "monthly": monthly,
            "rows": (
                [_contract_to_row(c) for c in d_contracts if c["congenere"] == cong]
                + [_contract_to_row(c) for c in r_contracts if c["congenere"] == cong]
            ),
        }

    d_bi_total = sum(v["d_total"] for v in by_cong.values())
    r_bi_total = sum(v["r_total"] for v in by_cong.values())
    d_grand_total = sum(_row_valor(r) for r in d_rows)
    r_grand_total = sum(_row_valor(r) for r in r_rows)
    summary = {
        "d_total": round(d_bi_total, 4),
        "d_pct": round(d_bi_total / d_grand_total * 100, 6) if d_grand_total else 0,
        "r_total": round(r_bi_total, 4),
        "r_pct": round(r_bi_total / r_grand_total * 100, 6) if r_grand_total else 0,
    }
    return {"bilaterais": bilaterais, "by_cong": by_cong, "summary": summary}
