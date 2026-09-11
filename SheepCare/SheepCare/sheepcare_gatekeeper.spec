# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — GateKeeper (Django + Waitress + PostgreSQL client)
#
# GateKeeper es el servicio central de autenticacion/autorizacion de OpenAgri
# (https://github.com/agstack/OpenAgri-GateKeeper). Se clona en build-time via
# setup_gatekeeper.ps1 (mismo patron que FarmCalendar).
#
# Se generan DOS ejecutables porque el launcher necesita correr comandos
# puntuales de Django (migrate, createsuperuser) antes de arrancar el
# servidor Waitress de larga duracion — igual que initdb/CREATE DATABASE se
# ejecutan antes de "pg_ctl start" para PostgreSQL:
#   - sheepcare-gatekeeper.exe          -> run_waitress.py (servidor, detached)
#   - sheepcare-gatekeeper-manage.exe   -> manage.py (comandos puntuales)

import os
ROOT   = os.path.abspath('.')
GK_DIR = os.path.join(ROOT, 'gatekeeper')

from PyInstaller.utils.hooks import collect_all
crispy_datas, crispy_binaries, crispy_hiddenimports = collect_all('crispy_forms')
crispy_b4_datas, crispy_b4_binaries, crispy_b4_hiddenimports = collect_all('crispy_bootstrap4')
yasg_datas, yasg_binaries, yasg_hiddenimports = collect_all('drf_yasg')

COMMON_BINARIES = crispy_binaries + crispy_b4_binaries + yasg_binaries

COMMON_DATAS = [
    # Toda la aplicacion Django (modelos, migraciones, templates propios...)
    (os.path.join(GK_DIR, 'aegis'),      'aegis'),
    (os.path.join(GK_DIR, 'gatekeeper'), 'gatekeeper'),
    (os.path.join(GK_DIR, 'templates'),  'templates'),
    (os.path.join(GK_DIR, 'static'),     'static'),
    (os.path.join(GK_DIR, '.env'),       '.'),
] + crispy_datas + crispy_b4_datas + yasg_datas

COMMON_HIDDENIMPORTS = [
    # Django core
    'django', 'django.core', 'django.core.management',
    'django.core.management.commands.migrate',
    'django.core.management.commands.createsuperuser',
    'django.contrib.admin', 'django.contrib.admin.apps',
    'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages',
    'django.contrib.staticfiles', 'django.contrib.sites',
    'django.template.backends.django', 'django.template.loaders.app_directories',
    'django.db.backends.postgresql',
    # Terceros
    'psycopg2', 'psycopg2._psycopg',
    'dj_database_url',
    'rest_framework', 'rest_framework.apps',
    'rest_framework_simplejwt', 'rest_framework_simplejwt.apps',
    'rest_framework_simplejwt.token_blacklist',
    'rest_framework_simplejwt.token_blacklist.apps',
    'rest_framework_simplejwt.views',
] + yasg_hiddenimports + [
    'corsheaders', 'corsheaders.middleware',
    'crispy_forms', 'crispy_bootstrap4',
] + crispy_hiddenimports + crispy_b4_hiddenimports + [
    'waitress', 'whitenoise', 'whitenoise.middleware',
    # Utilidades
    'dotenv', 'jwt', 'jwcrypto', 'requests',
    # App local
    'aegis', 'aegis.apps',
]

COMMON_KWARGS = dict(
    pathex=[ROOT, GK_DIR],
    binaries=COMMON_BINARIES,
    datas=COMMON_DATAS,
    hiddenimports=COMMON_HIDDENIMPORTS,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'PIL'],
    noarchive=False,
    optimize=1,
)

# ── Servidor (Waitress, arrancado detached por el launcher) ──────────────────
a_server = Analysis([os.path.join(GK_DIR, 'run_waitress.py')], **COMMON_KWARGS)
pyz_server = PYZ(a_server.pure)
exe_server = EXE(
    pyz_server,
    a_server.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-gatekeeper',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='installer/assets/sheepcare.ico',
)

# ── manage.py (comandos puntuales: migrate, createsuperuser) ─────────────────
a_manage = Analysis([os.path.join(GK_DIR, 'manage.py')], **COMMON_KWARGS)
pyz_manage = PYZ(a_manage.pure)
exe_manage = EXE(
    pyz_manage,
    a_manage.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-gatekeeper-manage',
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe_server,
    a_server.binaries,
    a_server.datas,
    exe_manage,
    a_manage.binaries,
    a_manage.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='gatekeeper',        # -> dist/gatekeeper/
)
