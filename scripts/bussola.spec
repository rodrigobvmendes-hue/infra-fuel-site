# -*- mode: python ; coding: utf-8 -*-
# Build:  pyinstaller scripts/bussola.spec --noconfirm
# Gera dist/Bussola (Linux/mac) ou dist/Bussola.exe (Windows) — arquivo único.

import os
from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = os.path.dirname(SPECPATH)  # raiz do repositório

datas, binaries, hiddenimports = [], [], []
# streamlit: estáticos + metadata; pulp: binários do CBC (todas as plataformas)
for pkg in ("streamlit", "pulp"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
for pkg in ("pandas", "openpyxl", "pyarrow"):
    datas += copy_metadata(pkg)
    hiddenimports.append(pkg)

# o app em si vai como dado: o launcher o executa via streamlit bootstrap
datas.append((os.path.join(ROOT, "src", "bussola"), "bussola"))

a = Analysis(
    [os.path.join(ROOT, "scripts", "run_app.py")],
    pathex=[os.path.join(ROOT, "src")],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "jedi"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Bussola",
    console=True,  # janela de console visível: mostra a URL e eventuais erros
    upx=False,
)
