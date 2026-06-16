"""
SheepCare Launcher — arranca PostgreSQL, FarmCalendar y el Backend,
luego abre el navegador. Compilado con PyInstaller como app GUI sin consola.
"""

import os
import sys
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

PGSQL_BIN    = os.path.join(BASE_DIR, "pgsql", "bin")
PG_CTL       = os.path.join(PGSQL_BIN, "pg_ctl.exe")
INITDB       = os.path.join(PGSQL_BIN, "initdb.exe")
PSQL         = os.path.join(PGSQL_BIN, "psql.exe")
BACKEND_EXE  = os.path.join(BASE_DIR, "backend",  "sheepcare-backend.exe")
CALENDAR_EXE = os.path.join(BASE_DIR, "calendar", "sheepcare-calendar.exe")

APP_URL      = "http://localhost:8000"
PG_PORT      = 5433
PG_SUPERUSER = "postgres"
PG_USER      = "farmcalendar"
PG_PASS      = "farmcalendar_pass"
PG_DB        = "farm_calendar"

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
def run_cmd(*cmd, timeout=120) -> int:
    """Ejecutar un comando oculto y devolver el código de retorno.
    Usa DEVNULL para evitar deadlocks por buffer lleno."""
    try:
        r = subprocess.run(
            list(cmd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
            timeout=timeout,
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


def start_detached(*cmd, env=None) -> None:
    """Arrancar proceso desacoplado (sigue vivo al cerrar el launcher)."""
    subprocess.Popen(
        list(cmd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=DETACHED | NEW_GROUP,
        env=env,
    )


# ── Lógica de arranque (hilo background) ─────────────────────────────────────
def launch():
    os.makedirs(APPDATA, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)

    # 1. Comprobar si ya está corriendo
    import urllib.request
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
    for exe, nombre in [(PG_CTL, "pg_ctl"), (BACKEND_EXE, "backend"), (CALENDAR_EXE, "calendar")]:
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

    # 6. Crear usuario y base de datos (idempotente)
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE USER {PG_USER} WITH PASSWORD '{PG_PASS}';",
                   "postgres")
    run_cmd_output(PSQL, "-U", PG_SUPERUSER, "-p", str(PG_PORT),
                   "-c", f"CREATE DATABASE {PG_DB} OWNER {PG_USER};",
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

    # 8. Arrancar FarmCalendar
    ui_status("Iniciando módulo de calendario...", "")
    cal_env = base_env.copy()
    cal_env["APP_PORT"] = "8002"
    start_detached(CALENDAR_EXE, env=cal_env)

    # 9. Arrancar Backend
    ui_status("Iniciando SheepCare...", "")
    bk_env = base_env.copy()
    bk_env["SHEEPCARE_DB_PATH"]    = DB_PATH
    bk_env["FARMCALENDAR_API_URL"] = "http://127.0.0.1:8002/api/v1/"
    bk_env["BACKEND_PORT"]         = "8000"
    start_detached(BACKEND_EXE, env=bk_env)

    # 10. Esperar al backend (max 120 s)
    ui_status("Esperando que SheepCare esté listo...", "")
    for i in range(60):
        try:
            urllib.request.urlopen(APP_URL + "/api/health", timeout=2)
            break
        except Exception:
            time.sleep(2)
            ui_status("Esperando que SheepCare esté listo...", f"{(i+1)*2}s")

    # 11. Abrir navegador y cerrar launcher
    ui_status("¡Listo! Abriendo SheepCare...", "")
    time.sleep(0.6)
    webbrowser.open(APP_URL)
    ui_done()


# Lanzar en hilo background para que tkinter siga procesando eventos
t = threading.Thread(target=launch, daemon=True)
t.start()
root.mainloop()
