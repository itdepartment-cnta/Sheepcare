"""Identificación de la instalación y ids de la nube de los padres, en el push.

    python -m unittest backend.tests.test_sync_ids -v
"""
import os
import re
import tempfile
import unittest
from unittest import mock

from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService
from backend.tests.test_milk_sync import FakeCloud, simular_calendario

# Lo que acepta la nube (`X-Installation-Id`): 8-64 caracteres, letras, números, - y _
FORMATO_NUBE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def _abrir(ruta):
    if DatabaseManager._instance is not None:
        DatabaseManager._instance.close()
    DatabaseManager._instance = None
    DatabaseManager._initialized = False
    return DatabaseManager(ruta)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.ruta = os.path.join(self.dir.name, "t.db")
        self.db = _abrir(self.ruta)
        self.nube = FakeCloud()
        simular_calendario(self)
        for nombre in ("get", "post"):
            p = mock.patch.object(sync_manager.requests, nombre, getattr(self.nube, nombre))
            p.start()
            self.addCleanup(p.stop)

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def svc(self, email="ana@x.es"):
        return SyncService(self.db, "https://nube.test", email, "pw")


class InstalacionId(Base):
    def test_se_genera_una_vez_con_formato_valido_y_se_conserva(self):
        a = self.db.get_installation_id("ana@x.es")
        self.assertRegex(a, FORMATO_NUBE)
        self.assertEqual(self.db.get_installation_id("ana@x.es"), a)
        self.assertEqual(self.db.get_installation_id("  ANA@x.es "), a)   # el correo no distingue mayúsculas
        # Sobrevive a cerrar y reabrir la base (reinicio de la aplicación)
        self.assertEqual(_abrir(self.ruta).get_installation_id("ana@x.es"), a)

    def test_cada_persona_tiene_el_suyo(self):
        self.assertNotEqual(self.db.get_installation_id("ana@x.es"), self.db.get_installation_id("beto@x.es"))

    def test_viaja_en_push_pull_y_confirmacion(self):
        farm = self.db.add_farm("G")
        s = self.svc()
        s.sync_to_cloud()
        self.nube.pull_data = {"farms": [{"id": 9, "name": "W", "location": "", "created_at": "2026-01-01T00:00:00"}]}
        s.pull_from_cloud()
        operaciones = {op for op, _ in self.nube.headers}
        self.assertEqual(operaciones, {"push", "pull", "confirm"})
        ids = {h.get("X-Installation-Id") for _, h in self.nube.headers}
        self.assertEqual(ids, {self.db.get_installation_id("ana@x.es")})

    def test_el_pull_con_otra_persona_usa_otra_instalacion(self):
        self.db.add_farm("G")                      # algo que enviar, para que haya push
        self.svc("ana@x.es").sync_to_cloud()
        self.svc("beto@x.es").pull_from_cloud()
        por_operacion = {op: h["X-Installation-Id"] for op, h in self.nube.headers}
        self.assertEqual(por_operacion["push"], self.db.get_installation_id("ana@x.es"))
        self.assertEqual(por_operacion["pull"], self.db.get_installation_id("beto@x.es"))
        self.assertNotEqual(por_operacion["push"], por_operacion["pull"])


class IdsDeLaNubeDeLosPadres(Base):
    def test_cada_hijo_lleva_el_cloud_id_de_su_padre_si_lo_tiene(self):
        # Granja y animal que BAJARON de la nube (origen cloud, con su id allí)
        farm = self.db.upsert_farm_from_cloud(77, "De la nube", "", "2026-01-01T00:00:00")
        animal_nube = self.db.upsert_animal_from_cloud(farm, 500, "NUBE-1", "", "2026-01-01T00:00:00")
        # Lo que se crea AQUÍ sobre ello
        animal = self.db.add_animal(farm, "LOCAL-1")
        lectura_a = self.db.save_animal_reading(animal_nube, "2026-05-18", 1.0)        # de un animal de la nube
        lectura_b = self.db.save_animal_reading(animal, "2026-05-18", 2.0)             # de un animal nuevo
        subida = self.db.create_upload(farm, "celo.xlsx")
        self.db.save_detection_result(animal_nube, subida, "Celo", 0.9, 0.9)
        self.db.save_detection_result(animal, subida, "No celo", 0.8, 0.2)
        self.svc().sync_to_cloud()
        p = self.nube.pushes[0]

        self.assertEqual([(x["external_tag"], x.get("farm_cloud_id")) for x in p["animals"]], [("LOCAL-1", 77)])
        self.assertEqual([x.get("farm_cloud_id") for x in p["uploads"]], [77])
        por_animal = {x["animal_origin_id"]: x.get("animal_cloud_id") for x in p["readings"]}
        self.assertEqual(por_animal, {animal_nube: 500, animal: None})   # el animal nuevo aún no existe en la nube
        for r in p["results"]:
            self.assertNotIn("upload_cloud_id", r)                        # la subida es nueva
        res = {x["animal_origin_id"]: x.get("animal_cloud_id") for x in p["results"]}
        self.assertEqual(res, {animal_nube: 500, animal: None})
        # Los ids vacíos no viajan como null
        for lista in p.values():
            for item in lista:
                self.assertFalse([k for k, v in item.items() if k.endswith("_cloud_id") and v is None])

    def test_una_subida_ya_sincronizada_aporta_su_cloud_id_a_sus_resultados(self):
        farm = self.db.add_farm("G")
        animal = self.db.add_animal(farm, "A")
        subida = self.db.create_upload(farm, "celo.xlsx")
        self.db.mark_farm_synced(farm, 10)
        self.db.mark_animal_synced(animal, 20)
        self.db.mark_upload_synced(subida, 30)
        self.db.save_detection_result(animal, subida, "Celo", 0.9, 0.9)
        self.svc().sync_to_cloud()
        r = self.nube.pushes[0]["results"][0]
        self.assertEqual((r["animal_cloud_id"], r["upload_cloud_id"]), (20, 30))


if __name__ == "__main__":
    unittest.main()
