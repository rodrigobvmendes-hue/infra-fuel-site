"""CLI headless: python -m bussola base.xlsx -o resultado.xlsx

Roda o mesmo núcleo da interface (diagnóstico → LP → export). Útil para
automação e para o teste de regressão contra a base real.
"""

import argparse
import sys

from .io_excel import load_base, make_template
from .model import DEFAULT_RUPTURE_PENALTY, RunParams, solve
from .report import export_xlsx, kpis
from .validate import has_errors, validate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bussola", description="Bússola Logística — CLI")
    ap.add_argument("base", nargs="?", help="arquivo .xlsx da base")
    ap.add_argument("-o", "--out", default="Bussola_resultado.xlsx", help="arquivo de saída")
    ap.add_argument("--template", metavar="ARQ", help="gera o template e sai")
    ap.add_argument("--cap-factor", type=float, default=1.0)
    ap.add_argument("--penalty", type=float, default=DEFAULT_RUPTURE_PENALTY)
    ap.add_argument("--force", action="store_true", help="roda mesmo com erros no diagnóstico")
    args = ap.parse_args(argv)

    if args.template:
        make_template(args.template)
        print(f"template gerado: {args.template}")
        return 0
    if not args.base:
        ap.error("informe a base .xlsx (ou use --template)")

    base = load_base(args.base)
    base.src_name = args.base
    msgs = validate(base)
    for m in msgs:
        print(f"[{m.level.upper():4}] {m.text}")
    if has_errors(msgs) and not args.force:
        print("\nDiagnóstico com erros — corrija a base (ou use --force).", file=sys.stderr)
        return 1

    res = solve(base, RunParams(cap_factor=args.cap_factor, rupture_penalty=args.penalty))
    if not res.feasible:
        print(f"solver: {res.status} — revise restrições", file=sys.stderr)
        return 2
    print(f"\nstatus: {res.status} · {len(res.flows)} fluxos · {res.n_arcs} arcos")
    for k, v in kpis(res).items():
        print(f"  {k}: {v:,}")
    export_xlsx(res, base, args.out, src_name=args.base)
    print(f"\nresultado exportado: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
