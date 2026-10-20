"""Roles en el Edge, API local: una granja compartida no se edita ni se borra.

    python -m unittest backend.tests.test_roles_api -v

El 403 se aplica en el backend y no solo en la interfaz: si no, el cambio local no se enviaría
nunca (la nube lo rechaza) y el equipo mostraría algo que la nube no tiene.
"""
import atexit
import os
import shutil
import tempfile
import unittest
from unittest import mock

# Los routers crean un DatabaseManager al importarse: que no toque la base real.
_TMP = tempfile.mkdtemp()
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)
os.environ.setdefault("SHEEPCARE_DB_PATH", os.path.join(_TMP, "import.db"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.api import farms, settings  # noqa: E402
from backend.data_access.db_manager import DatabaseManager  # noqa: E402
from backend.tests.test_milk_sync import _nuevo_gestor  # noqa: E402


class BaseApi(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.db = _nuevo_gestor(os.path.join(self.dir.name, "t.db"))
        for modulo in (farms, settings):
            p = mock.patch.object(modulo, "db", self.db)
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(farms.router, prefix="/api/farms")
        app.include_router(settings.router, prefix="/api/settings")
        self.client = TestClient(app)

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def granja(self, nombre, access=None):
        farm = self.db.add_farm(nombre, "Soria")
        if access:
            self.db.connection.execute("UPDATE farms SET cloud_access = ? WHERE id = ?", (access, farm))
            self.db.connection.commit()
        return farm


class GranjaCompartidaTest(BaseApi):
    def test_el_listado_trae_el_access(self):
        self.granja("Local")
        self.granja("Mia", "owner")
        self.granja("Ajena", "shared")
        self.granja("Todas", "admin")
        accesos = {f["name"]: f["access"] for f in self.client.get("/api/farms/").json()}
        self.assertEqual(accesos, {"Local": None, "Mia": "owner", "Ajena": "shared", "Todas": "admin"})

    def test_una_compartida_no_se_edita(self):
        farm = self.granja("Ajena", "shared")
        r = self.client.put(f"/api/farms/{farm}", json={"name": "Cambiada", "location": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.db.get_farm(farm)["name"], "Ajena")

    def test_una_compartida_no_se_borra_ni_se_pierden_sus_datos(self):
        farm = self.granja("Ajena", "shared")
        self.db.add_animal(farm, "OV-1")
        r = self.client.delete(f"/api/farms/{farm}")
        self.assertEqual(r.status_code, 403)
        self.assertIsNotNone(self.db.get_farm(farm))
        self.assertEqual(len(self.db.list_animals(farm)), 1)

    def test_una_compartida_si_se_consulta(self):
        farm = self.granja("Ajena", "shared")
        r = self.client.get(f"/api/farms/{farm}")
        self.assertEqual((r.status_code, r.json()["access"]), (200, "shared"))

    def test_propias_administradas_y_locales_se_editan_y_borran(self):
        for access in ("owner", "admin", None):
            with self.subTest(access=access):
                farm = self.granja(f"G-{access}", access)
                self.assertEqual(
                    self.client.put(f"/api/farms/{farm}", json={"name": "Nueva", "location": "y"}).status_code, 200)
                self.assertEqual(self.client.delete(f"/api/farms/{farm}").status_code, 204)

    def test_una_granja_que_no_existe_sigue_dando_404(self):
        self.assertEqual(self.client.put("/api/farms/999", json={"name": "x", "location": ""}).status_code, 404)
        self.assertEqual(self.client.delete("/api/farms/999").status_code, 404)

    def test_una_granja_oculta_no_existe_para_la_api(self):
        farm = self.granja("Oculta", "shared")
        self.db.connection.execute("UPDATE farms SET hidden = 1 WHERE id = ?", (farm,))
        self.db.connection.commit()
        self.assertEqual(self.client.get("/api/farms/").json(), [])
        self.assertEqual(self.client.get(f"/api/farms/{farm}").status_code, 404)
        self.assertEqual(self.client.put(f"/api/farms/{farm}", json={"name": "x", "location": ""}).status_code, 404)
        self.assertEqual(self.client.delete(f"/api/farms/{farm}").status_code, 404)


class EstadoDeLoApartadoTest(BaseApi):
    def test_sin_nada_apartado(self):
        r = self.client.get("/api/settings/sync/status").json()
        self.assertEqual(r["blocked_count"], 0)
        self.assertEqual(self.client.get("/api/settings/sync/blocked").json(), [])

    def test_el_estado_cuenta_lo_apartado_con_o_sin_sincronizacion_previa(self):
        farm = self.granja("A")
        self.db.block_record("farms", farm, "sin permiso sobre la granja")
        self.assertEqual(self.client.get("/api/settings/sync/status").json()["blocked_count"], 1)
        self.db.log_sync("success")
        self.db.update_cloud_sync_time()
        r = self.client.get("/api/settings/sync/status").json()
        self.assertEqual(r["blocked_count"], 1)

    def test_el_listado_dice_que_y_por_que(self):
        farm = self.granja("A")
        self.db.block_record("farms", farm, "sin permiso sobre la granja: ya no eres su propietaria")
        (item,) = self.client.get("/api/settings/sync/blocked").json()
        self.assertEqual((item["table_name"], item["origin_id"]), ("farms", farm))
        self.assertIn("sin permiso", item["reason"])
        self.assertTrue(item["blocked_at"])


if __name__ == "__main__":
    unittest.main()
