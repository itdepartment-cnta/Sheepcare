"""Lecturas sin fecha: bajan de la nube, se guardan con su orden y su subida, y no se inventa nada.

    python -m unittest backend.tests.test_sync_lecturas_sin_fecha -v
"""
import io
import os
import tempfile
import unittest
from unittest import mock

import openpyxl

from backend.core.excel_parser import ExcelParser
from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService
from backend.tests.test_milk_sync import FakeCloud, simular_calendario

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
        simular_calendario(self)
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


def _pull_como_pre():
    """Lo que devolvió `pre`: lecturas sin fecha, con orden y subida, de 2 animales."""
    return {
        "farms": [{"id": 21, "name": "Andalucía", "location": "", "created_at": FECHA}],
        "animals": [
            {"id": 915, "farm_id": 21, "external_tag": "OV-1", "name": "", "created_at": FECHA},
            {"id": 916, "farm_id": 21, "external_tag": "OV-2", "name": "", "created_at": FECHA},
        ],
        "uploads": [{"id": 36, "farm_id": 21, "filename": "prueba.xlsx", "upload_date": "2026-09-21T10:00:00+00:00",
                     "total_animals": 2, "celo_count": 1, "no_celo_count": 1}],
        "readings": [
            # Desordenadas a propósito
            {"id": 2832, "animal_id": 915, "reading_date": None, "value": 470.0, "source_file": "prueba.xlsx", "reading_order": 2, "upload_id": 36},
            {"id": 2831, "animal_id": 915, "reading_date": None, "value": 480.0, "source_file": "prueba.xlsx", "reading_order": 1, "upload_id": 36},
            {"id": 2833, "animal_id": 916, "reading_date": None, "value": 300.0, "source_file": "prueba.xlsx", "reading_order": 1, "upload_id": 36},
        ],
    }


class PullDeLecturasSinFecha(Base):
    def test_se_guardan_sin_fecha_con_su_orden_y_su_subida_y_se_confirman(self):
        self.nube.pull_data = _pull_como_pre()
        r = self.svc.pull_from_cloud()
        self.assertTrue(r["success"])
        filas = [tuple(x) for x in self.db.connection.execute(
            "SELECT cloud_id, reading_date, reading_order, value, origin FROM animal_readings ORDER BY cloud_id")]
        self.assertEqual(filas, [(2831, None, 1, 480.0, "cloud"), (2832, None, 2, 470.0, "cloud"), (2833, None, 1, 300.0, "cloud")])
        # Cuelgan de la subida local que corresponde a la 36 de la nube
        subida_local = self.db.connection.execute("SELECT id FROM uploads WHERE cloud_id = 36").fetchone()["id"]
        self.assertEqual(
            {x[0] for x in self.db.connection.execute("SELECT upload_id FROM animal_readings")}, {subida_local})
        # Y se confirman: la nube deja de repetirlas (y de reenviar sus animales padre)
        self.assertEqual(sorted(dict(self.nube.confirms)["animal_readings"]), [2831, 2832, 2833])

    def test_es_idempotente(self):
        self.nube.pull_data = _pull_como_pre()
        self.svc.pull_from_cloud()
        self.svc.pull_from_cloud()
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM animal_readings").fetchone()[0], 3)

    def test_el_historial_del_animal_sale_en_orden_aunque_no_haya_fechas(self):
        self.nube.pull_data = _pull_como_pre()
        self.svc.pull_from_cloud()
        animal = self.db.connection.execute("SELECT id FROM animals WHERE cloud_id = 915").fetchone()["id"]
        lecturas = self.db.get_animal_readings(animal)
        self.assertEqual([(x["reading_order"], x["value"], x["reading_date"]) for x in lecturas],
                         [(1, 480.0, None), (2, 470.0, None)])

    def test_una_lectura_con_fecha_sigue_funcionando(self):
        d = _pull_como_pre()
        d["readings"] = [{"id": 1, "animal_id": 915, "reading_date": "2026-05-18T00:00:00+00:00", "value": 330.0,
                          "source_file": "a.xlsx", "reading_order": None, "upload_id": None}]
        self.nube.pull_data = d
        self.svc.pull_from_cloud()
        fila = self.db.connection.execute("SELECT reading_date, reading_order, upload_id FROM animal_readings").fetchone()
        self.assertEqual(tuple(fila), ("2026-05-18T00:00:00+00:00", None, None))

    def test_lo_bajado_de_la_nube_no_se_reenvia_en_el_push(self):
        self.nube.pull_data = _pull_como_pre()
        self.svc.pull_from_cloud()
        self.svc.sync_to_cloud()
        enviado = {k for p in self.nube.pushes for k in p}
        self.assertNotIn("readings", enviado)


class DelExcelALaNube(Base):
    def test_un_excel_de_dia_1_dia_2_viaja_sin_fecha_ni_etiquetas_inventadas(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["animal", "dia 1", "dia 2"])
        ws.append(["A-1", 300, 250])
        buf = io.BytesIO()
        wb.save(buf)
        animales = ExcelParser.parse_content(buf.getvalue(), "t.xlsx")

        # Lo mismo que hace api/uploads.py al guardar
        farm = self.db.add_farm("G")
        subida = self.db.create_upload(farm, "t.xlsx")
        animal = self.db.add_animal(farm, "A-1")
        for lectura in animales[0]["readings"]:
            self.db.save_animal_reading(animal, lectura["date"], lectura["value"], source_file="t.xlsx",
                                        reading_order=lectura.get("order"), upload_id=subida)
        guardadas = [tuple(x) for x in self.db.connection.execute(
            "SELECT reading_date, reading_order, upload_id FROM animal_readings ORDER BY id")]
        self.assertEqual(guardadas, [(None, 1, subida), (None, 2, subida)])      # nada de «date_1»

        self.svc.sync_to_cloud()
        enviadas = self.nube.pushes[0]["readings"]
        self.assertEqual([(x["reading_date"], x["value"]) for x in enviadas], [(None, 300.0), (None, 250.0)])


if __name__ == "__main__":
    unittest.main()
