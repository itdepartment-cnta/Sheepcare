"""Entry point para PyInstaller — arranca el backend FastAPI con uvicorn."""
import os
import sys
import traceback

# Directorio de datos de usuario
_APPDATA = os.path.join(os.environ.get("APPDATA", ""), "SheepCare")
_LOG     = os.path.join(_APPDATA, "backend-startup.log")


def _log(msg: str) -> None:
    os.makedirs(_APPDATA, exist_ok=True)
    with open(_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


try:
    # En bundle PyInstaller, cambiar al directorio del exe para que
    # los imports relativos encuentren _internal/
    if getattr(sys, "frozen", False):
        _exe_dir = os.path.dirname(sys.executable)
        os.chdir(_exe_dir)
        # Asegurar que _internal/ esté en sys.path
        _internal = os.path.join(_exe_dir, "_internal")
        if _internal not in sys.path:
            sys.path.insert(0, _internal)

    _log(f"Python: {sys.executable}")
    _log(f"sys.path: {sys.path[:5]}")

    # Con console=False en PyInstaller, sys.stdout/stderr son None.
    # Uvicorn llama a .isatty() en el stream al configurar su logger,
    # lo que provoca AttributeError. Redirigimos a un fichero de log.
    if sys.stdout is None or sys.stderr is None:
        _uvicorn_log = open(
            os.path.join(_APPDATA, "backend.log"), "a", encoding="utf-8", buffering=1
        )
        sys.stdout = _uvicorn_log
        sys.stderr = _uvicorn_log

    import uvicorn
    _log(f"uvicorn OK: {uvicorn.__version__}")

    if __name__ == "__main__":
        port = int(os.environ.get("BACKEND_PORT", "8000"))
        db_path = os.environ.get(
            "SHEEPCARE_DB_PATH",
            os.path.join(_APPDATA, "sheepcare.db"),
        )
        os.environ.setdefault("SHEEPCARE_DB_PATH", db_path)
        _log(f"Arrancando en puerto {port}, DB: {db_path}")
        uvicorn.run("backend.main:app", host="0.0.0.0", port=port, log_level="warning")

except Exception:
    _log(traceback.format_exc())
    raise
