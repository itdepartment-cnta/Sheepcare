"""El resultado del pull cuenta: un fallo al recibir ya no pasa por una sincronización correcta.

    python -m unittest backend.tests.test_sync_now -v

Antes, `sync/now` y la sincronización automática llamaban a `pull_from_cloud()` y descartaban lo
que devolvía: un login rechazado, un corte de red o un 500 de la nube al recibir se veían como
«Sincronización completada». Hay que mirar el resultado de los dos.
"""
import atexit
import os
import shutil
import tempfile
import unittest
from unittest import mock

_TMP = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)
os.environ.setdefault("SHEEPCARE_DB_PATH", os.path.join(_TMP, "import.db"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import settings  # noqa: E402


class ServicioFalso:
    """Sustituye a SyncService: devuelve lo que la prueba le indique."""

    push = {"success": True, "synced_count": 0}
    pull = {"success": True, "pulled_count": 0, "removed_count": 0}
    llamadas = []

    def __init__(self, *a, **kw):
        pass

    def sync_to_cloud(self):
        ServicioFalso.llamadas.append("push")
        if isinstance(ServicioFalso.push, Exception):
            raise ServicioFalso.push
        return ServicioFalso.push

    def pull_from_cloud(self):
        ServicioFalso.llamadas.append("pull")
        return ServicioFalso.pull


class SyncNowTest(unittest.TestCase):
    def setUp(self):
        ServicioFalso.llamadas = []
        ServicioFalso.push = {"success": True, "synced_count": 0}
        ServicioFalso.pull = {"success": True, "pulled_count": 0, "removed_count": 0}
        p = mock.patch.object(settings, "SyncService", ServicioFalso)
        p.start()
        self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(settings.router, prefix="/api/settings")
        self.client = TestClient(app)

    def ahora(self):
        return self.client.post("/api/settings/sync/now").json()

    def test_todo_bien_devuelve_lo_enviado_y_lo_recibido(self):
        ServicioFalso.push = {"success": True, "synced_count": 3, "blocked_count": 2}
        ServicioFalso.pull = {"success": True, "pulled_count": 40, "removed_count": 1}
        r = self.ahora()
        self.assertEqual(
            (r["success"], r["synced_count"], r["pulled_count"], r["removed_count"], r["blocked_count"], r["error"]),
            (True, 3, 40, 1, 2, None),
        )
        self.assertEqual(ServicioFalso.llamadas, ["push", "pull"])

    def test_un_pull_que_falla_no_es_una_sincronizacion_correcta(self):
        ServicioFalso.push = {"success": True, "synced_count": 5}
        ServicioFalso.pull = {"success": False, "pulled_count": 0, "error": "Authentication failed"}
        r = self.ahora()
        self.assertFalse(r["success"])
        self.assertEqual(r["error"], "Authentication failed")
        self.assertEqual(r["synced_count"], 5, "lo enviado se sigue contando")

    def test_un_pull_que_falla_sin_mensaje_da_uno_generico(self):
        ServicioFalso.pull = {"success": False}
        r = self.ahora()
        self.assertFalse(r["success"])
        self.assertTrue(r["error"])

    def test_si_el_push_falla_no_se_intenta_el_pull(self):
        ServicioFalso.push = {"success": False, "synced_count": 0, "error": "No internet"}
        r = self.ahora()
        self.assertEqual((r["success"], r["error"]), (False, "No internet"))
        self.assertEqual(ServicioFalso.llamadas, ["push"])

    def test_el_error_del_push_manda_sobre_el_del_pull(self):
        ServicioFalso.push = {"success": False, "error": "primero"}
        ServicioFalso.pull = {"success": False, "error": "segundo"}
        self.assertEqual(self.ahora()["error"], "primero")

    def test_una_excepcion_se_convierte_en_error(self):
        ServicioFalso.push = RuntimeError("boom")
        r = self.ahora()
        self.assertEqual((r["success"], r["error"]), (False, "boom"))


class SyncAutomaticaTest(unittest.TestCase):
    """`_run_auto_sync` vive en backend.main, que tarda unos 20 s en importarse (carga el modelo)."""

    def setUp(self):
        from backend import main
        self.main = main
        ServicioFalso.llamadas = []
        ServicioFalso.is_configured = True
        ServicioFalso.check_cloud_connectivity = lambda self, *a, **k: True
        ServicioFalso.push = {"success": True, "synced_count": 1}
        ServicioFalso.pull = {"success": True, "pulled_count": 2, "removed_count": 0}
        p = mock.patch("backend.data_access.sync_manager.SyncService", ServicioFalso)
        p.start()
        self.addCleanup(p.stop)

    def test_un_pull_que_falla_deja_un_aviso(self):
        ServicioFalso.pull = {"success": False, "error": "Cloud API error: 500"}
        with self.assertLogs("backend.main", level="WARNING") as registro:
            self.main._run_auto_sync()
        self.assertTrue(any("el pull falló" in linea and "500" in linea for linea in registro.output))

    def test_un_pull_correcto_no_avisa(self):
        with self.assertNoLogs("backend.main", level="WARNING"):
            self.main._run_auto_sync()
        self.assertEqual(ServicioFalso.llamadas, ["push", "pull"])

    def test_sin_push_no_hay_pull_ni_aviso(self):
        ServicioFalso.push = {"success": False, "error": "No internet"}
        with self.assertNoLogs("backend.main", level="WARNING"):
            self.main._run_auto_sync()
        self.assertEqual(ServicioFalso.llamadas, ["push"])


if __name__ == "__main__":
    unittest.main()
