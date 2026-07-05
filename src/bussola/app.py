"""Bússola Logística — interface Streamlit.

Rodar:  streamlit run src/bussola/app.py
Fluxo:  template → upload da base → diagnóstico → premissas → rodada → export.
"""

import io
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bussola.io_excel import load_base, make_template  # noqa: E402
from bussola.model import DEFAULT_RUPTURE_PENALTY, RunParams, solve  # noqa: E402
from bussola.report import (  # noqa: E402
    atendimento_df, export_xlsx, flows_df, kpis, modal_mix_df, polos_df,
)
from bussola.validate import has_errors, validate  # noqa: E402

st.set_page_config(page_title="Bússola Logística", page_icon="🧭", layout="wide")
st.title("🧭 Bússola Logística")
st.caption("Otimização de malha · multiproduto · multimodal — menor custo da molécula entregue")

# ── 0 · Template ──────────────────────────────────────────────────────────
with st.expander("0 · Modelo de planilha (template)"):
    st.markdown(
        "- **Tabela de frete:** Origem · UF Origem · Destino · UF Destino · Frete (R$/m³) · **Modal**\n"
        "- **Disponibilidade:** Fornecedor · Localidade · Produto · Preço (R$/m³) · Volume mínimo · Média · Máx (m³)\n"
        "- **Demanda:** Desc Filial · Produto · Demanda (m³)\n"
        "- **Estoque (opcional):** Local · Produto · Volume disponível (m³) · Custo (R$/m³)\n"
        "- **Armazenagem (opcional):** Filial · Produto · Custo armazenagem (R$/m³)"
    )
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        make_template(tf.name)
        st.download_button("⬇️ Baixar template", Path(tf.name).read_bytes(),
                           "Bussola_template.xlsx")

# ── 1 · Base de dados ─────────────────────────────────────────────────────
st.header("1 · Base de dados")
up = st.file_uploader("Carregue a base (.xlsx)", type=["xlsx"])
if not up:
    st.info("Carregue a base para habilitar o diagnóstico e a rodada.")
    st.stop()

with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
    tf.write(up.getvalue())
    tmp_path = tf.name
try:
    base = load_base(tmp_path)
    base.src_name = up.name
except ValueError as e:
    st.error(str(e))
    st.stop()

# ── 2 · Diagnóstico ───────────────────────────────────────────────────────
st.header("2 · Diagnóstico da base")
msgs = validate(base)
icon = {"err": "🛑", "warn": "⚠️", "ok": "✅"}
fn = {"err": st.error, "warn": st.warning, "ok": st.success}
for m in msgs:
    fn[m.level](f"{icon[m.level]} {m.text}")
if has_errors(msgs):
    st.stop()

# ── 3 · Premissas da rodada ───────────────────────────────────────────────
st.header("3 · Premissas da rodada")
c1, c2 = st.columns(2)
cap_factor = c1.number_input("Fator de capacidade (multiplica o Máx de todas as origens)",
                             0.1, 3.0, 1.0, 0.05)
penalty = c2.number_input("Penalidade de ruptura (R$/m³)", 1_000.0, 100_000.0,
                          DEFAULT_RUPTURE_PENALTY, 1_000.0)
forns = sorted({s.forn for s in base.supply})
origs = sorted({s.ko for s in base.supply if s.max > 0})
forn_on = st.multiselect("Fornecedores ativos", forns, default=forns)
orig_on = st.multiselect("Origens ativas", origs, default=origs)
params = RunParams(cap_factor=cap_factor, rupture_penalty=penalty,
                   fornecedores_off=set(forns) - set(forn_on),
                   origens_excluidas=set(origs) - set(orig_on))

# ── 4 · Painel da rodada ──────────────────────────────────────────────────
if st.button("▶️ Rodar otimização", type="primary"):
    with st.spinner("Resolvendo o LP…"):
        st.session_state["res"] = solve(base, params)

res = st.session_state.get("res")
if res:
    st.header("4 · Painel da rodada")
    if not res.feasible:
        st.error(f"Solver terminou com status {res.status} — revise as restrições.")
        st.stop()
    st.caption(f"{len(res.flows)} fluxos · {res.n_arcs} arcos no modelo · status {res.status}")
    cols = st.columns(5)
    for col, (k, v) in zip(cols, kpis(res).items()):
        col.metric(k, f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) else v)
    if res.ruptures:
        st.error("**Ruptura em:** " + " · ".join(
            f"{kf} {prod} ({v:,.0f} m³)" for kf, prod, v in res.ruptures
        ) + " — falta física de oferta/rota, não decisão recomendada.")

    st.subheader("Mix modal — como o volume viaja")
    st.dataframe(modal_mix_df(res), use_container_width=True, hide_index=True)
    st.subheader("Consumo por polo de disponibilidade")
    st.dataframe(polos_df(res), use_container_width=True, hide_index=True)
    st.subheader("Plano de atendimento por filial — custo aberto por componente e modal")
    st.dataframe(flows_df(res), use_container_width=True, hide_index=True)
    st.subheader("Atendimento da demanda")
    st.dataframe(atendimento_df(res, base), use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
        export_xlsx(res, base, tf.name, src_name=up.name)
        buf.write(Path(tf.name).read_bytes())
    st.download_button("⬇️ Exportar resultado (.xlsx, com trilha de auditoria)",
                       buf.getvalue(), "Bussola_resultado.xlsx")
