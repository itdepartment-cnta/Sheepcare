# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Reporting (OpenAgri Reporting Service: FastAPI + PostgreSQL + fpdf2)
#
# Fork CNTA, rama cnta-patches-local, clonado en build-time por
# setup_reporting.ps1. Se compila con Python 3.12 en su propio venv
# (requirements-windows.txt: sin geopandas, que el codigo no importa).
#
# Un solo ejecutable (run_reporting.py: migra con alembic y arranca uvicorn):
#   - sheepcare-reporting.exe   -> dist/reporting/

import os
ROOT = os.path.abspath('.')
REP_DIR = os.path.join(ROOT, 'reporting')
APP_DIR = os.path.join(REP_DIR, 'app')

from PyInstaller.utils.hooks import collect_all, collect_submodules

mpl_datas, mpl_binaries, mpl_hidden = collect_all('matplotlib')

# El codigo importa sus modulos como `core`, `api`, `crud`... (app/ en el path)
hidden = []
for pkg in ('api', 'core', 'crud', 'db', 'models', 'schemas', 'utils'):
    hidden += collect_submodules(pkg)
hidden += collect_submodules('uvicorn')
hidden += collect_submodules('alembic')
hidden += collect_submodules('sqlalchemy.dialects.postgresql')
hidden += mpl_hidden
hidden += [
    'psycopg2', 'psycopg2._psycopg',
    'passlib.handlers.argon2', 'argon2', 'argon2.low_level',   # passlib lo carga por nombre
    'multipart', 'jwt', 'pandas',
]

a = Analysis(
    [os.path.join(REP_DIR, 'run_reporting.py')],
    pathex=[ROOT, APP_DIR],
    binaries=mpl_binaries,
    datas=[
        (os.path.join(APP_DIR, 'assets'),      'assets'),        # logos del PDF (PROJECT_ROOT/assets)
        (os.path.join(APP_DIR, 'utils', 'fonts'), os.path.join('utils', 'fonts')),
        (os.path.join(REP_DIR, 'alembic'),     'alembic'),       # migraciones (se leen como ficheros)
        (os.path.join(REP_DIR, 'alembic.ini'), '.'),
    ] + mpl_datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'IPython', 'pytest', 'geopandas', 'shapely'],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-reporting',
    debug=False,
    strip=False,
    upx=False,
    console=False,           # sin consola: el launcher lo arranca desacoplado
    icon='installer/assets/sheepcare.ico',
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name='reporting',        # -> dist/reporting/
)
