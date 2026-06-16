# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec -- SheepCare Backend (FastAPI + React frontend)

import os
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = os.path.abspath('.')

# Recopilar onnxruntime ANTES del Analysis (PyInstaller 6.x requiere esto)
ort_datas, ort_binaries, ort_hidden = collect_all('onnxruntime')
sklearn_datas, sklearn_binaries, sklearn_hidden = collect_all('sklearn')

a = Analysis(
    ['run_backend.py'],
    pathex=[ROOT],
    binaries=ort_binaries + sklearn_binaries,
    datas=[
        ('models',               'models'),
        ('frontend/dist',        'frontend/dist'),
        ('frontend/public/logos','frontend/dist/logos'),
    ] + ort_datas + sklearn_datas,
    hiddenimports=[
        # uvicorn
        'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on',
        # starlette / fastapi
        'starlette.routing', 'starlette.staticfiles', 'starlette.responses',
        'fastapi', 'fastapi.responses', 'fastapi.staticfiles',
        # pydantic
        'pydantic', 'pydantic.deprecated.class_validators', 'pydantic_core',
        # ML (sklearn via collect_all)
        'joblib', 'joblib.externals.loky', 'joblib.externals.loky.backend',
        # onnxruntime (la mayoria la coge collect_all, pero por si acaso)
        'onnxruntime', 'onnxruntime.capi',
        'onnxruntime.capi.onnxruntime_inference_collection',
        # datos
        'numpy', 'pandas', 'openpyxl', 'dateutil', 'dateutil.parser',
        # auth / http
        'jwt', 'cryptography', 'httpx', 'requests', 'multipart',
        # sqlite
        'sqlite3',
        # backend
        'backend', 'backend.main', 'backend.api', 'backend.api.farms',
        'backend.api.uploads', 'backend.api.results', 'backend.api.animals',
        'backend.api.settings', 'backend.core', 'backend.core.models_loader',
        'backend.data_access', 'backend.data_access.db_manager',
        'backend.data_access.sync_manager', 'backend.utils', 'backend.utils.helpers',
    ] + ort_hidden + sklearn_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL', 'IPython'],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-backend',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='installer/assets/sheepcare.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='backend',
)
