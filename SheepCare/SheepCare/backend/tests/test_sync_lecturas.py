"""Lecturas al sincronizar: la etiqueta de una columna («date_1») no es una fecha.

    python -m unittest backend.tests.test_sync_lecturas -v
"""
import os
import tempfile
import unittest
from unittest import mock

from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService, _fecha_o_none
from backend.tests.test_milk_sync import FakeCloud


class FechaDeLectura(unittest.TestCase):
    def test_fechas_validas_se_conservan(self):
        for f in ("2026-05-18", "2026-05-18T00:00:00+00:00", "2026-05-18 10:30:00"):
            self.assertEqual(_fecha_o_none(f), f)

    def test_etiquetas_de_columna_y_basura_pasan_a_none(self):
        for f in ("date_1", "date_2", "col_3", "dia 1", "", "2026-13-45", None):
            self.assertIsNone(_fecha_o_none(f))


class PushDeLecturas(unittest.TestCase):
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

    def test_un_excel_de_dia_1_dia_2_viaja_sin_fecha_y_el_resto_igual(self):
        farm = self.db.add_farm("G")
        animal = self.db.add_animal(farm, "A-1", name="A-1")
        self.db.save_animal_reading(animal, "date_1", 300.0, "t.xlsx")     # lo que guarda el parser
        self.db.save_animal_reading(animal, "date_2", 250.0, "t.xlsx")
        self.db.save_animal_reading(animal, "2026-05-18", 200.0, "t.xlsx")  # una con fecha real
        self.svc.sync_to_cloud()
        lecturas = self.nube.pushes[0]["readings"]
        self.assertEqual([(x["reading_date"], x["value"]) for x in lecturas],
                         [(None, 300.0), (None, 250.0), ("2026-05-18", 200.0)])
        # Nada se ha tocado en la base local: solo cambia lo que se envía
        guardadas = [r[0] for r in self.db.connection.execute("SELECT reading_date FROM animal_readings ORDER BY id")]
        self.assertEqual(guardadas, ["date_1", "date_2", "2026-05-18"])


if __name__ == "__main__":
    unittest.main()
