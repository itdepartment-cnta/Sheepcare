# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — SheepCare Launcher (GUI, sin consola)

import os
ROOT = os.path.abspath('.')

a = Analysis(
    [os.path.join('installer', 'launcher_app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=[
        ('installer/assets/sheepcare.ico', 'assets'),
    ],
    hiddenimports=['tkinter', 'tkinter.ttk', 'tkinter.messagebox'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'PIL', 'numpy', 'pandas'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='SheepCare',
    debug=False,
    strip=False,
    upx=False,
    console=False,           # Sin consola — app GUI
    icon='installer/assets/sheepcare.ico',
)
# Launcher como onefile (sin carpeta _internal) para que sea un único .exe
