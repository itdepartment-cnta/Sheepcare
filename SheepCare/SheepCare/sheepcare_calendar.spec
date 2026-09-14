# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — FarmCalendar (Django + Waitress + PostgreSQL client)
#
# Se generan DOS ejecutables, igual que en sheepcare_gatekeeper.spec: el
# launcher necesita correr "manage.py migrate" antes de arrancar el servidor
# Waitress de larga duración.
#   - sheepcare-calendar.exe          -> run_waitress.py (servidor, detached)
#   - sheepcare-calendar-manage.exe   -> manage.py (comandos puntuales)

import os
ROOT   = os.path.abspath('.')
FC_DIR = os.path.join(ROOT, 'farmcalendar')

from PyInstaller.utils.hooks import collect_all
rfw_nested_datas, rfw_nested_binaries, rfw_nested_hiddenimports = collect_all('rest_framework_nested')
shapely_datas, shapely_binaries, shapely_hiddenimports = collect_all('shapely')
crispy_datas, crispy_binaries, crispy_hiddenimports = collect_all('crispy_forms')
crispy_b4_datas, crispy_b4_binaries, crispy_b4_hiddenimports = collect_all('crispy_bootstrap4')

COMMON_BINARIES = rfw_nested_binaries + shapely_binaries + crispy_binaries + crispy_b4_binaries

COMMON_DATAS = [
    # Toda la aplicación Django (templates, static, fixtures, migrations…)
    (os.path.join(FC_DIR, 'farm_calendar'),    'farm_calendar'),
    (os.path.join(FC_DIR, 'farm_management'),  'farm_management'),
    (os.path.join(FC_DIR, 'farm_activities'),  'farm_activities'),
    (os.path.join(FC_DIR, 'apis'),             'apis'),
    (os.path.join(FC_DIR, 'templates'),        'templates'),
    (os.path.join(FC_DIR, 'static'),           'static'),
    (os.path.join(FC_DIR, 'fixtures'),         'fixtures'),
    (os.path.join(FC_DIR, '.env'),             '.'),
] + rfw_nested_datas + shapely_datas + crispy_datas + crispy_b4_datas

COMMON_HIDDENIMPORTS = [
    # Django core
    'django', 'django.core', 'django.core.management',
    'django.core.management.commands.migrate',
    'django.contrib.admin', 'django.contrib.admin.apps',
    'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages',
    'django.contrib.staticfiles', 'django.contrib.sites',
    'django.template.backends.django', 'django.template.loaders.app_directories',
    'django.db.backends.postgresql',
    # Terceros
    'psycopg2', 'psycopg2._psycopg', 'psycopg2cffi',
    'rest_framework', 'rest_framework.apps',
    'rest_framework_nested', 'rest_framework_nested.routers',
] + rfw_nested_hiddenimports + [
    'drf_spectacular', 'drf_spectacular.apps',
    'django_filters', 'django_filters.apps',
    'simple_history', 'simple_history.apps',
    'crispy_forms', 'crispy_bootstrap4',
] + crispy_hiddenimports + crispy_b4_hiddenimports + [
    'dal', 'dal_select2',
    'waitress',
    # Shapely (submodulos via collect_all)
    'shapely', 'shapely.geometry', 'shapely.ops', 'shapely.wkt',
] + shapely_hiddenimports + [
    # Utilidades
    'decouple', 'dotenv', 'requests', 'jwt',
    'numpy',
    # Apps locales
    'farm_management', 'farm_management.apps',
    'farm_activities', 'farm_activities.apps',
    'apis', 'apis.apps',
]

COMMON_KWARGS = dict(
    pathex=[ROOT, FC_DIR],
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
a_server = Analysis([os.path.join(FC_DIR, 'run_waitress.py')], **COMMON_KWARGS)
pyz_server = PYZ(a_server.pure)
exe_server = EXE(
    pyz_server,
    a_server.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-calendar',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='installer/assets/sheepcare.ico',
)

# ── manage.py (comandos puntuales: migrate) ───────────────────────────────────
a_manage = Analysis([os.path.join(FC_DIR, 'manage.py')], **COMMON_KWARGS)
pyz_manage = PYZ(a_manage.pure)
exe_manage = EXE(
    pyz_manage,
    a_manage.scripts,
    [],
    exclude_binaries=True,
    name='sheepcare-calendar-manage',
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
    name='calendar',         # → dist/calendar/
)
