"""Launcher do executável (PyInstaller) — sobe o Streamlit com o app embutido.

No bundle, o pacote `bussola` é colocado na raiz extraída (sys._MEIPASS);
fora dele (desenvolvimento), cai em src/bussola. O navegador abre sozinho.
"""

import sys
from pathlib import Path


def main() -> None:
    frozen = getattr(sys, "frozen", False)
    base = Path(getattr(sys, "_MEIPASS", "")) if frozen else Path(__file__).resolve().parents[1] / "src"
    app = base / "bussola" / "app.py"
    if not app.exists():
        print(f"ERRO: app não encontrado em {app}", file=sys.stderr)
        raise SystemExit(1)

    print("Bússola Logística — iniciando… o navegador abrirá em instantes.")
    print("Para encerrar, feche esta janela.")
    from streamlit.web import bootstrap

    # No bundle PyInstaller, o Streamlit se acha "instalado de forma anormal"
    # (caminho sem site-packages) e liga developmentMode — o que desativa as
    # rotas estáticas (página 404) e troca a porta. Forçar False é essencial.
    # bootstrap.run NÃO aplica flag_options sozinho; load_config_options sim.
    flags = {
        "global_developmentMode": False,
        "browser_gatherUsageStats": False,
        "server_headless": False,  # abre o navegador automaticamente
    }
    bootstrap.load_config_options(flags)
    bootstrap.run(str(app), False, [], flags)


if __name__ == "__main__":
    main()
