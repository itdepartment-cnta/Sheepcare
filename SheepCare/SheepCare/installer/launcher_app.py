"""
SheepCare Launcher — arranca PostgreSQL, FarmCalendar y el Backend,
luego abre el navegador. Compilado con PyInstaller como app GUI sin consola.
"""

import os
import sys
import secrets
import subprocess
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
           else os.path.dirname(os.path.abspath(__file__))

APPDATA  = os.path.join(os.environ.get("APPDATA", ""), "SheepCare")
PGDATA   = os.path.join(APPDATA, "pgdata")
DB_PATH  = os.path.join(APPDATA, "sheepcare.db")
LOG_DIR  = os.path.join(APPDATA, "logs")

# Secretos generados una sola vez y persistidos fuera de {app} (que Inno Setup
# borra al desinstalar), para que sobrevivan a reinstalaciones/actualizaciones.
JWT_SECRET_FILE       = os.path.join(APPDATA, "jwt_secret.key")
GK_DJANGO_SECRET_FILE = os.path.join(APPDATA, "gatekeeper_django_secret.key")
GK_ADMIN_FILE         = os.path.join(APPDATA, "gatekeeper_admin.key")

PGSQL_BIN      = os.path.join(BASE_DIR, "pgsql", "bin")
PG_CTL         = os.path.join(PGSQL_BIN, "pg_ctl.exe")
INITDB         = os.path.join(PGSQL_BIN, "initdb.exe")
PSQL           = os.path.join(PGSQL_BIN, "psql.exe")
BACKEND_EXE    = os.path.join(BASE_DIR, "backend",  "sheepcare-backend.exe")
CALENDAR_EXE   = os.path.join(BASE_DIR, "calendar", "sheepcare-calendar.exe")
GATEKEEPER_DIR = os.path.join(BASE_DIR, "gatekeeper")
GATEKEEPER_EXE = os.path.join(GATEKEEPER_DIR, "sheepcare-gatekeeper.exe")
GATEKEEPER_MANAGE_EXE = os.path.join(GATEKEEPER_DIR, "sheepcare-gatekeeper-manage.exe")

APP_URL      = "http://localhost:8000"
PG_PORT      = 5433
PG_SUPERUSER = "postgres"
PG_USER      = "farmcalendar"
PG_PASS      = "farmcalendar_pass"
PG_DB        = "farm_calendar"
GK_USER      = "gatekeeper"
GK_PASS      = "gatekeeper_pass"
GK_DB        = "gatekeeper"
GK_PORT      = 8001

NO_WINDOW    = 0x08000000   # CREATE_NO_WINDOW
DETACHED     = 0x00000008   # DETACHED_PROCESS
NEW_GROUP    = 0x00000200   # CREATE_NEW_PROCESS_GROUP

# ── UI ────────────────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("SheepCare")
root.resizable(False, False)
root.geometry("420x145")
root.configure(bg="#1a1a2e")
try:
    ico = os.path.join(BASE_DIR, "assets", "sheepcare.ico")
    if os.path.exists(ico):
        root.iconbitmap(ico)
except Exception:
    pass

tk.Label(root, text="SHEEP", font=("Segoe UI", 16, "bold"),
         fg="#b5cc18", bg="#1a1a2e").place(x=20, y=16)
tk.Label(root, text="CARE", font=("Segoe UI", 16, "bold italic"),
         fg="#b5cc18", bg="#1a1a2e").place(x=94, y=16)

lbl = tk.Label(root, text="Iniciando...", font=("Segoe UI", 9),
               fg="#aaaaaa", bg="#1a1a2e", anchor="w", width=50)
lbl.place(x=20, y=58)

bar = ttk.Progressbar(root, mode="indeterminate", length=378)
bar.place(x=20, y=88)
bar.start(15)

lbl_sub = tk.Label(root, text="", font=("Segoe UI", 7),
                   fg="#666666", bg="#1a1a2e", anchor="w", width=55)
lbl_sub.place(x=20, y=116)

root.update()


def ui_status(msg: str, sub: str = "") -> None:
    """Actualizar la UI desde cualquier hilo de forma segura."""
    def _update():
        lbl.config(text=msg)
        lbl_sub.config(text=sub)
    root.after(0, _update)


def ui_fatal(msg: str) -> None:
    def _show():
        bar.stop()
        messagebox.showerror("SheepCare — Error", msg)
        root.destroy()
    root.after(0, _show)


def ui_done() -> None:
    root.after(0, root.destroy)


# ── Subprocess helpers ────────────────────────────────────────────────────────
def run_cmd(*cmd, timeout=120, env=None, cwd=None) -> int:
    """Ejecutar un comando oculto y devolver el código de retorno.
    Usa DEVNULL para evitar deadlocks por buffer lleno."""
    try:
        r = subprocess.run(
            list(cmd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
            timeout=timeout,
            env=env,
            cwd=cwd,
        )
        return r.returncode
    except subprocess.TimeoutExpired:
        return -1
    except FileNotFoundError:
        return -2


def run_cmd_output(*cmd, timeout=30) -> tuple:
    """Igual que run_cmd pero captura stdout para leer resultados."""
    try:
        r = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=NO_WINDOW,
            timeout=timeout,
        )
        return r.returncode, r.stdout.decode(errors="replace")
    except Exception as e:
        return -1, str(e)


def start_detached(*cmd, env=None, cwd=None) -> None:
    """Arrancar proceso desacoplado (sigue vivo al cerrar el launcher)."""
    subprocess.Popen(
        list(cmd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=DETACHED | NEW_GROUP,
        env=env,
        cwd=cwd,
    )


# ── Secretos persistidos ──────────────────────────────────────────────────────
def get_or_create_secret(path: str, length: int = 48) -> str:
    """Lee un secreto generado previamente o lo crea la primera vez.
    Vive fuera de {app} para sobrevivir a reinstalaciones."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip()
        if value:
            return value
    value = secrets.token_urlsafe(length)
    with open(path, "w", encoding="utf-8") as f:
        f.write(value)
    return value


def get_or_create_gatekeeper_admin() -> dict:
    """Credenciales del superusuario Django de GateKeeper (panel /admin/),
    generadas una sola vez — nunca hardcodeadas."""
    if os.path.exists(GK_ADMIN_FILE):
        creds = {}
        with open(GK_ADMIN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    creds[k] = v
        if {"USERNAME", "EMAIL", "PASSWORD"} <= creds.keys():
            return creds
    creds = {
        "USERNAME": "sheepcare-admin",
        "EMAIL": "sheepcare-admin@localhost",
        "PASSWORD": secrets.token_urlsafe(24),
    }
    with open(GK_ADMIN_FILE, "w", encoding="utf-8") as f:
        for k, v in creds.items():
            f.write(f"{k}={v}\n")
    return creds


# ── Lógica de arranque (hilo background) ─────────────────────────────────────
def launch():
    os.makedirs(APPDATA, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 1. Comprobar si ya está corriendo
    import urllib.request
    import urllib.error
    try:
        urllib.request.urlopen(APP_URL, timeout=2)
        ui_status("SheepCare ya está activo — abriendo navegador...")
        time.sleep(0.5)
        webbrowser.open(APP_URL)
        ui_done()
        return
    except Exception:
        pass

    # 2. Verificar binarios necesarios
    for exe, nombre in [(PG_CTL, "pg_ctl"), (BACKEND_EXE, "backend"), (CALENDAR_EXE, "calendar"),
                        (GATEKEEPER_EXE, "gatekeeper"), (GATEKEEPER_MANAGE_EXE, "gatekeeper-manage")]:
        if not os.path.exists(exe):
            ui_fatal(f"No se encontró el archivo:\n{exe}\n\nReinicia la instalación.")
            return

    # 3. Inicializar PostgreSQL (solo la primera vez — puede tardar 1 min)
    if not os.path.isdir(PGDATA):
        ui_status("Configurando la base de datos...",
                  "Solo ocurre la primera vez. Por favor espera (puede tardar hasta 1 minuto).")
        pg_log = os.path.join(LOG_DIR, "postgres-init.log")
        rc = run_cmd(INITDB, "-D", PGDATA, "-U", PG_SUPERUSER,
                     "--encoding=UTF8", "--locale=C",
                     timeout=300)
        if rc != 0:
            ui_fatal("No se pudo inicializar la base de datos.\n"
                     f"Revisa el log en:\n{pg_log}")
            return

        # Permitir conexiones locales sin contraseña
        hba = os.path.join(PGDATA, "pg_hba.conf")
        try:
            with open(hba, "a") as f:
                f.write("\nhost all all 127.0.0.1/32 trust\n")
                f.write("host all all ::1/128 trust\n")
        except Exception as e:
            ui_fatal(f"Error configurando PostgreSQL:\n{e}")
            return

    # 4. Arrancar PostgreSQL
    ui_status("Iniciando base de datos...", f"Puerto {PG_PORT}")
    pg_log = os.path.join(LOG_DIR, "postgres.log")
    run_cmd(PG_CTL, "start", "-D", PGDATA, "-l", pg_log,
            "-o", f"-p {PG_PORT}", timeout=30)

    # 5. Esperar a que PostgreSQL esté listo (max 60 s)
    ui_status("Esperando base de datos...", "")
    ready = False
    for i in range(30):
        rc, _ = run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                                "-c", "SELECT 1", "postgres")
        if rc == 0:
            ready = True
            break
        time.sleep(2)
        ui_status("Esperando base de datos...", f"Intento {i+1}/30")

    if not ready:
        ui_fatal("PostgreSQL no respondió a tiempo.\n"
                 f"Revisa el log en:\n{pg_log}")
        return

    # 6. Crear usuarios y bases de datos (idempotente)
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE USER {PG_USER} WITH PASSWORD '{PG_PASS}';",
                   "postgres")
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE DATABASE {PG_DB} OWNER {PG_USER};",
                   "postgres")
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE USER {GK_USER} WITH PASSWORD '{GK_PASS}';",
                   "postgres")
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE DATABASE {GK_DB} OWNER {GK_USER};",
                   "postgres")

    # 7. Variables de entorno para los servicios
    base_env = os.environ.copy()
    base_env.update({
        "POSTGRES_HOST":     "127.0.0.1",
        "POSTGRES_PORT":     str(PG_PORT),
        "POSTGRES_DB":       PG_DB,
        "POSTGRES_USER":     PG_USER,
        "POSTGRES_PASSWORD": PG_PASS,
    })

    # 7.5 Secreto JWT compartido — sustituye al literal hardcodeado que antes
    # llevaba el propio backend. Se genera una sola vez y lo comparten
    # GateKeeper (emisor), FarmCalendar y el backend de SheepCare.
    jwt_secret = get_or_create_secret(JWT_SECRET_FILE)

    # 8. Arrancar GateKeeper (servicio central de autenticacion). No es una
    # dependencia dura: si falla, FarmCalendar y el backend deben seguir
    # funcionando exactamente igual que antes de esta integracion.
    ui_status("Iniciando servicio de autenticación...", "")
    try:
        os.makedirs(os.path.join(GATEKEEPER_DIR, "logs"), exist_ok=True)
        gk_django_secret = get_or_create_secret(GK_DJANGO_SECRET_FILE)
        gk_admin = get_or_create_gatekeeper_admin()

        gk_env = os.environ.copy()
        gk_env.update({
            "DATABASE_URL": f"postgres://{GK_USER}:{GK_PASS}@127.0.0.1:{PG_PORT}/{GK_DB}",
            "JWT_SIGNING_KEY": jwt_secret,
            "JWT_ALG": "HS256",
            "DJANGO_SECRET_KEY": gk_django_secret,
            "DJANGO_DEBUG": "False",
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(GK_PORT),
            "FARM_CALENDAR_API": "http://127.0.0.1:8002/api/",
            "SUPERUSER_USERNAME": gk_admin["USERNAME"],
            "SUPERUSER_EMAIL": gk_admin["EMAIL"],
            "SUPERUSER_PASSWORD": gk_admin["PASSWORD"],
            "DJANGO_SUPERUSER_USERNAME": gk_admin["USERNAME"],
            "DJANGO_SUPERUSER_EMAIL": gk_admin["EMAIL"],
            "DJANGO_SUPERUSER_PASSWORD": gk_admin["PASSWORD"],
        })

        run_cmd(GATEKEEPER_MANAGE_EXE, "migrate", "--noinput",
                env=gk_env, cwd=GATEKEEPER_DIR, timeout=120)
        # Falla de forma idempotente en arranques posteriores (el usuario ya
        # existe) — no es un error real, solo se intenta una vez con éxito.
        run_cmd(GATEKEEPER_MANAGE_EXE, "createsuperuser", "--noinput",
                env=gk_env, cwd=GATEKEEPER_DIR, timeout=30)

        start_detached(GATEKEEPER_EXE, env=gk_env, cwd=GATEKEEPER_DIR)

        # Healthcheck informativo (no bloqueante): el endpoint /healthz de
        # GateKeeper redirige con 301 antes de resolver la ruta (bug conocido
        # de su propio ForceAppendSlashMiddleware), así que cualquier
        # respuesta HTTP —incluida una redirección o 404— ya confirma que el
        # proceso está vivo y sirviendo peticiones; solo un fallo de conexión
        # cuenta como "no listo".
        for _ in range(10):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{GK_PORT}/healthz", timeout=2)
                break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(2)
    except Exception:
        pass  # GateKeeper es opcional para el arranque de SheepCare.

    # 9. Arrancar FarmCalendar
    ui_status("Iniciando módulo de calendario...", "")
    cal_env = base_env.copy()
    cal_env["APP_PORT"] = "8002"
    cal_env["JWT_SIGNING_KEY"] = jwt_secret
    start_detached(CALENDAR_EXE, env=cal_env)

    # 10. Arrancar Backend
    ui_status("Iniciando SheepCare...", "")
    bk_env = base_env.copy()
    bk_env["SHEEPCARE_DB_PATH"]        = DB_PATH
    bk_env["FARMCALENDAR_API_URL"]     = "http://127.0.0.1:8002/api/v1/"
    bk_env["BACKEND_PORT"]             = "8000"
    bk_env["FARMCALENDAR_JWT_SECRET"]  = jwt_secret
    start_detached(BACKEND_EXE, env=bk_env)

    # 11. Esperar al backend (max 120 s)
    ui_status("Esperando que SheepCare esté listo...", "")
    for i in range(60):
        try:
            urllib.request.urlopen(APP_URL + "/api/health", timeout=2)
            break
        except Exception:
            time.sleep(2)
            ui_status("Esperando que SheepCare esté listo...", f"{(i+1)*2}s")

    # 12. Abrir navegador y cerrar launcher
    ui_status("¡Listo! Abriendo SheepCare...", "")
    time.sleep(0.6)
    webbrowser.open(APP_URL)
    ui_done()


# Lanzar en hilo background para que tkinter siga procesando eventos
t = threading.Thread(target=launch, daemon=True)
t.start()
root.mainloop()
