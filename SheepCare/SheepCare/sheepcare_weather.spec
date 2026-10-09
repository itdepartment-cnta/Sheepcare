# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — Weather (OpenAgri Weather Service: FastAPI + MongoDB)
#
# Fork CNTA, rama cnta-patches-local, clonado en build-time por
# setup_weather.ps1 (mismo patron que GateKeeper/FarmCalendar). Se compila con
# Python 3.12 en su propio venv: sus dependencias estan fijadas y no conviven
# con las del backend de SheepCare.
#
# Un solo ejecutable (run_weather.py), arrancado desacoplado por el launcher:
#   - sheepcare-weather.exe   -> dist/weather/

import os
ROOT = os.path.abspath('.')
WEATHER_DIR = os.path.join(ROOT, 'weather')

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# APScheduler carga triggers, executors y jobstores por nombre (entry points)
aps_datas, aps_binaries, aps_hidden = collect_all('apscheduler')
beanie_datas, beanie_binaries, beanie_hidden = collect_all('beanie')

hidden = (
    collect_submodules('src')            # el codigo de Weather (app, rutas, modelos...)
    + collect_submodules('uvicorn')
    + collect_submodules('pymongo')
    + collect_submodules('motor')
    + collect_submodules('rdflib')       # plugins de rdflib por nombre
    + collect_submodules('passlib')      # passlib carga sus manejadores (bcrypt...) por nombre
    + aps_hidden + beanie_hidden
    + ['tzdata', 'tzlocal', 'multipart', 'email_validator', 'jwt']
)

a = Analysis(
    [os.path.join(WEATHER_DIR, 'run_weather.py')],
    pathex=[ROOT, WEATHER_DIR],
    binaries=aps_binaries + beanie_binaries,
    datas=aps_datas + beanie_datas
          + copy_metadata('apscheduler') + copy_metadata('rdflib') + copy_metadata('tzdata'),
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'IPython', 'pytest'],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-weather',
    debug=False,
    strip=False,
    upx=False,
    console=False,           # sin consola: el launcher lo arranca desacoplado
    icon='installer/assets/sheepcare.ico',
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name='weather',          # -> dist/weather/
)
