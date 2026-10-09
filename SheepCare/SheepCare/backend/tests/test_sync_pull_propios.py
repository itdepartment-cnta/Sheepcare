"""Pull: lo que creó esta instalación y vuelve como padre, y los registros que chocan.

    python -m unittest backend.tests.test_sync_pull_propios -v

Caso real: B pone una lectura en un animal de A; la nube se lo devuelve a A como
padre con `origin: "edge"` y su `origin_id`. Si A no lo reconoce lo vuelve a
insertar: duplica la granja y rompe el pull con un UNIQUE en el animal.
"""
import os
import tempfile
import unittest
from unittest import mock

from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService
from backend.tests.test_milk_sync import FakeCloud

FECHA = "2026-02-01T00:00:00+00:00"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False
        self.db = DatabaseManager(os.path.join(self.dir.name, "t.db"))
        self.nube = FakeCloud()
        for nombre in ("get", "post"):
            p = mock.patch.object(sync_manager.requests, nombre, getattr(self.nube, nombre))
            p.start()
            self.addCleanup(p.stop)
        self.svc = SyncService(self.db, "https://nube.test", "ana@x.es", "pw")

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def n(self, sql, *args):
        return self.db.connection.execute(sql, args).fetchone()[0]


class PadresPropios(Base):
    def _mi_granja_y_animal(self, con_cloud_id=True):
        farm = self.db.add_farm("Mía")
        animal = self.db.add_animal(farm, "A-1")
        if con_cloud_id:
            self.db.mark_farm_synced(farm, 40)
            self.db.mark_animal_synced(animal, 50)
        return farm, animal

    def test_la_granja_propia_que_vuelve_no_se_duplica_y_se_confirma(self):
        farm, _ = self._mi_granja_y_animal()
        self.nube.pull_data = {
            "farms": [{"id": 40, "name": "Mía", "location": "", "created_at": FECHA, "origin": "edge", "origin_id": farm}],
            # Algo nuevo que la web colgó de ella
            "animals": [{"id": 60, "farm_id": 40, "external_tag": "WEB-1", "name": "", "created_at": FECHA, "origin": "cloud", "origin_id": 0}],
        }
        r = self.svc.pull_from_cloud()
        self.assertTrue(r["success"])
        self.assertEqual(self.n("SELECT COUNT(*) FROM farms"), 1)                       # no se duplicó
        self.assertEqual(self.n("SELECT COUNT(*) FROM animals WHERE farm_id = ?", farm), 2)  # el nuevo cuelga de la suya
        self.assertIn(("farms", [40]), self.nube.confirms)                              # se confirma para no repetirlo
        self.assertEqual(r["pulled_count"], 1)                                          # solo cuenta lo nuevo (el animal)

    def test_el_animal_propio_que_vuelve_no_rompe_el_pull_y_recibe_la_lectura(self):
        farm, animal = self._mi_granja_y_animal()
        self.nube.pull_data = {
            "farms": [{"id": 40, "name": "Mía", "location": "", "created_at": FECHA, "origin": "edge", "origin_id": farm}],
            "animals": [{"id": 50, "farm_id": 40, "external_tag": "A-1", "name": "", "created_at": FECHA, "origin": "edge", "origin_id": animal}],
            "readings": [{"id": 70, "animal_id": 50, "reading_date": "2026-05-18T00:00:00+00:00", "value": 321.0, "source_file": "b.xlsx"}],
        }
        r = self.svc.pull_from_cloud()
        self.assertTrue(r["success"])
        self.assertEqual(self.n("SELECT COUNT(*) FROM animals"), 1)                     # sigue siendo uno
        lectura = self.db.connection.execute("SELECT animal_id, value, origin FROM animal_readings").fetchone()
        self.assertEqual((lectura["animal_id"], lectura["value"], lectura["origin"]), (animal, 321.0, "cloud"))
        confirmado = dict(self.nube.confirms)
        self.assertEqual(confirmado["animals"], [50])
        self.assertEqual(confirmado["animal_readings"], [70])

    def test_si_aun_no_tenia_el_id_de_la_nube_se_enlaza(self):
        farm, animal = self._mi_granja_y_animal(con_cloud_id=False)
        self.nube.pull_data = {
            "farms": [{"id": 40, "name": "Mía", "location": "", "created_at": FECHA, "origin": "edge", "origin_id": farm}],
            "animals": [{"id": 50, "farm_id": 40, "external_tag": "A-1", "name": "", "created_at": FECHA, "origin": "edge", "origin_id": animal}],
        }
        self.svc.pull_from_cloud()
        self.assertEqual(self.n("SELECT cloud_id FROM farms WHERE id = ?", farm), 40)
        self.assertEqual(self.n("SELECT cloud_id FROM animals WHERE id = ?", animal), 50)

    def test_si_el_origin_id_ya_no_existe_se_trata_como_nuevo(self):
        self.nube.pull_data = {
            "farms": [{"id": 40, "name": "Recuperada", "location": "", "created_at": FECHA, "origin": "edge", "origin_id": 999}],
        }
        self.svc.pull_from_cloud()
        fila = self.db.connection.execute("SELECT name, origin, cloud_id FROM farms").fetchone()
        self.assertEqual((fila["name"], fila["origin"], fila["cloud_id"]), ("Recuperada", "cloud", 40))


class RegistroQueChoca(Base):
    def test_un_animal_que_choca_no_tumba_el_pull_ni_se_confirma(self):
        farm = self.db.upsert_farm_from_cloud(40, "De la nube", "", FECHA)
        self.db.add_animal(farm, "REPETIDA")        # ya hay uno local con esa etiqueta, sin id de la nube
        self.nube.pull_data = {
            "animals": [
                {"id": 61, "farm_id": 40, "external_tag": "REPETIDA", "name": "", "created_at": FECHA, "origin": "cloud", "origin_id": 0},
                {"id": 62, "farm_id": 40, "external_tag": "OTRA", "name": "", "created_at": FECHA, "origin": "cloud", "origin_id": 0},
            ],
        }
        r = self.svc.pull_from_cloud()
        self.assertTrue(r["success"])                                                    # no revienta
        etiquetas = sorted(x[0] for x in self.db.connection.execute("SELECT external_tag FROM animals"))
        self.assertEqual(etiquetas, ["OTRA", "REPETIDA"])                                # el otro sí se guardó
        self.assertEqual(dict(self.nube.confirms)["animals"], [62])                      # el que chocó no se confirma


if __name__ == "__main__":
    unittest.main()
