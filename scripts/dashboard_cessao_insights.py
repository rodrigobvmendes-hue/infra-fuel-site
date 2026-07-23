"""
Geração dos blocos `insights` (texto para os cards de destaque do
dashboard). Estes textos são MELHOR ESFORÇO: as contagens centrais
("Apuração Pendente", "Bases Sem Receita", "Take or Pay — N registros")
foram validadas batendo exatamente com o D atual; os limiares de
"Estouro Orçamentário" e "Anomalia Tarifária", e o texto exato de
"Cobertura", não puderam ser reproduzidos com 100% de certeza (ver
relatório da tarefa) — a lógica aqui é uma aproximação razoável.
"""

import statistics
from collections import defaultdict


def _fmt_money(v):
    return f"{v:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")


def build_despesa_insights(d_contracts, d_kpi, r_kpi, d_cong_all, d_filiais, r_filiais):
    insights = []

    cobertura = round(r_kpi["total"] / d_kpi["total"] * 100, 1) if d_kpi["total"] else 0
    level = "critical" if cobertura < 15 else ("warning" if cobertura < 30 else "positive")
    texto = f"Receitas cobrem {cobertura}% das despesas totais."
    if cobertura < 15:
        texto += " ⚠ Abaixo de 15%."
    insights.append({"level": level, "title": f"Cobertura: {cobertura}%", "text": texto})

    top_recs = [c for c in d_contracts if c["status"] == "TOP Gerado"]
    if top_recs:
        grouped = defaultdict(lambda: {"total": 0.0, "periods": []})
        for c in top_recs:
            g = grouped[(c["filial"], c["congenere"])]
            g["total"] += c["top"] or 0
            g["periods"].append(c["period"])
        ranked = sorted(grouped.items(), key=lambda kv: -kv[1]["total"])
        partes = []
        for (filial, congenere), g in ranked[:5]:
            periods = sorted(g["periods"])
            qtd = len(periods)
            if qtd > 1:
                intervalo = f"{qtd}x, {periods[0]} a {periods[-1]}"
            else:
                intervalo = periods[0]
            partes.append(f"{filial}/{congenere}: R${_fmt_money(g['total'])} ({intervalo})")
        maiores = " | ".join(partes)
        insights.append({
            "level": "warning",
            "title": f"Take or Pay — {len(top_recs)} registros em {len(grouped)} contratos",
            "text": f"Maiores: {maiores}",
        })

    sem_dado = [c for c in d_contracts if c["status"] == "Sem dado"]
    if sem_dado:
        insights.append({
            "level": "info", "title": "Apuração Pendente",
            "text": f"{len(sem_dado)} registros de despesa sem valor realizado (usando orçado).",
        })

    sem_receita = sorted(d_filiais - r_filiais)
    if sem_receita:
        insights.append({
            "level": "warning", "title": f"Bases Sem Receita — {len(sem_receita)}",
            "text": "Só despesa: " + ", ".join(sem_receita[:10]),
        })

    by_filial_real = defaultdict(float)
    by_filial_orc = defaultdict(float)
    for c in d_contracts:
        if c["is_realizado"]:
            by_filial_real[c["filial"]] += c["valor"] or 0
        else:
            by_filial_orc[c["filial"]] += c["valor"] or 0
        # aproxima orc total com o próprio valor quando não realizado
    estouros = []
    for f, real in by_filial_real.items():
        orc = by_filial_orc.get(f, 0)
        base = real if orc == 0 else (real + orc)
        if orc and real > 1.10 * orc:
            estouros.append(f)
    if estouros:
        insights.append({
            "level": "warning", "title": f"Estouro Orçamentário — {len(estouros)} filiais",
            "text": "Realizado >110% orçado: " + ", ".join(sorted(estouros)[:10]),
        })

    tarifas = {c["congenere"]: c["tarifa"] for c in d_cong_all if c.get("tarifa")}
    if len(tarifas) >= 3:
        med = statistics.median(tarifas.values())
        anomalos = [(k, v) for k, v in tarifas.items() if med and v > 2 * med]
        if anomalos:
            texto = ", ".join(f"{k}:{v:.2f}" for k, v in anomalos[:5])
            insights.append({
                "level": "warning", "title": f"Anomalia Tarifária — {len(anomalos)} congêneres",
                "text": f"Tarifa efetiva >2× mediana: {texto}",
            })

    return insights


def build_receita_insights(r_contracts, topmon, bilaterais):
    insights = []

    sem_dado = [c for c in r_contracts if c["status"] == "Sem dado"]
    if sem_dado:
        insights.append({
            "level": "info", "title": "Apuração Pendente",
            "text": f"{len(sem_dado)} registros de receita sem valor realizado.",
        })

    top_recebido = sum(c["top"] or 0 for c in r_contracts if c["is_realizado"])
    insights.append({
        "level": "positive", "title": f"TOP Recebido: R$ {_fmt_money(top_recebido)}",
        "text": "Receita sem movimentação de volume (benefício contratual).",
    })

    for t in topmon:
        if t["max_consec"] >= 4:
            insights.append({
                "level": "warning",
                "title": f"Risco Renegociação: {t['filial']}/{t['congenere']}",
                "text": f"Abaixo do mínimo por {t['max_consec']} meses consecutivos — risco de renegociação contratual.",
            })

    if bilaterais:
        insights.append({
            "level": "info", "title": f"Bilateral — {len(bilaterais)} congêneres",
            "text": "Presentes em ambos os lados: " + ", ".join(bilaterais),
        })

    return insights
