"""Migración de las lecturas: la fecha pasa a ser opcional y las etiquetas de columna dejan de ser «fechas».

    python -m unittest backend.tests.test_readings_migration -v
"""
import glob
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from backend.data_access import readings_migration
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.readings_migration import fecha_y_orden
from backend.tests.test_milk_migration import ESQUEMA_ANTIGUO


def _abrir(ruta):
    if DatabaseManager._instance is not None:
        DatabaseManager._instance.close()
    DatabaseManager._instance = None
    DatabaseManager._initialized = False
    return DatabaseManager(ruta)


class FechaYOrden(unittest.TestCase):
    def test_las_fechas_reales_se_conservan_sin_orden(self):
        for f in ("2026-05-18", "2026-05-18T00:00:00+00:00", " 2026-05-18 10:30:00 "):
            self.assertEqual(fecha_y_orden(f), (f.strip(), None))

    def test_una_etiqueta_pierde_la_fecha_y_su_numero_final_es_el_orden(self):
        casos = {"date_1": 1, "date_2": 2, "dia 1": 1, "Día 12": 12, "col_3": 3, "dia 2 ": 2}
        for etiqueta, orden in casos.items():
            self.assertEqual(fecha_y_orden(etiqueta), (None, orden), etiqueta)

    def test_sin_numero_o_vacio_no_hay_orden(self):
        for f in ("basura", "", None):
            self.assertEqual(fecha_y_orden(f), (None, None))


class Migracion(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.ruta = os.path.join(self.dir.name, "sheepcare.db")

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def _base_antigua(self):
        c = sqlite3.connect(self.ruta)
        c.executescript(ESQUEMA_ANTIGUO)
        c.execute("INSERT INTO farms (name) VALUES ('A')")
        c.execute("INSERT INTO animals (id, farm_id, external_tag) VALUES (1, 1, 'A-1'), (2, 1, 'A-2')")
        c.executemany(
            "INSERT INTO animal_readings (id, animal_id, reading_date, value, source_file) VALUES (?,?,?,?,?)",
            [
                (1, 1, "2026-05-18", 330.0, "f1.xlsx"),                  # real
                (2, 1, "2026-05-19T00:00:00+00:00", 230.0, "f1.xlsx"),   # real, con hora (como la nube)
                (3, 2, "date_1", 480.0, "f2.xlsx"),                      # etiqueta del parser de Excel
                (4, 2, "date_2", 470.0, "f2.xlsx"),
                (5, 2, "dia 1", 100.0, "f3.csv"),                        # etiqueta del parser de CSV
                (6, 2, "col_3", 90.0, "f3.csv"),
                (7, 2, "basura", 80.0, "f3.csv"),                        # sin número: sin orden
            ],
        )
        # Las columnas de sincronización las añade DatabaseManager al abrir (como en una base real)
        c.commit()
        c.close()

    def test_migra_corrige_las_etiquetas_y_conserva_todo_lo_demas(self):
        self._base_antigua()
        c = sqlite3.connect(self.ruta)
        c.execute("ALTER TABLE animal_readings ADD COLUMN origin TEXT DEFAULT 'edge'")
        c.execute("ALTER TABLE animal_readings ADD COLUMN cloud_id INTEGER")
        c.execute("ALTER TABLE animal_readings ADD COLUMN synced_at DATETIME")
        c.execute("UPDATE animal_readings SET origin='cloud', cloud_id=2596 WHERE id=2")
        c.commit()
        c.close()

        db = _abrir(self.ruta)
        filas = [tuple(r) for r in db.connection.execute(
            "SELECT id, animal_id, reading_date, value, reading_order, upload_id, origin, cloud_id "
            "FROM animal_readings ORDER BY id")]
        self.assertEqual(filas, [
            (1, 1, "2026-05-18", 330.0, None, None, "edge", None),
            (2, 1, "2026-05-19T00:00:00+00:00", 230.0, None, None, "cloud", 2596),   # origen y id de la nube intactos
            (3, 2, None, 480.0, 1, None, "edge", None),
            (4, 2, None, 470.0, 2, None, "edge", None),
            (5, 2, None, 100.0, 1, None, "edge", None),
            (6, 2, None, 90.0, 3, None, "edge", None),
            (7, 2, None, 80.0, None, None, "edge", None),
        ])
        info = {r[1]: r for r in db.connection.execute("PRAGMA table_info(animal_readings)")}
        self.assertEqual(info["reading_date"][3], 0)                 # ya no es obligatoria
        self.assertEqual(db.connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(db.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_hace_copia_de_seguridad_con_los_datos_antiguos(self):
        self._base_antigua()
        _abrir(self.ruta)
        copias = glob.glob(self.ruta + ".antes-lecturas-*.bak")
        self.assertEqual(len(copias), 1)
        c = sqlite3.connect(copias[0])
        self.assertEqual(c.execute("SELECT reading_date FROM animal_readings WHERE id=3").fetchone()[0], "date_1")
        c.close()

    def test_es_idempotente(self):
        self._base_antigua()
        _abrir(self.ruta)
        db = _abrir(self.ruta)
        self.assertEqual(len(glob.glob(self.ruta + ".antes-lecturas-*.bak")), 1)
        self.assertEqual(db.connection.execute("SELECT COUNT(*) FROM animal_readings").fetchone()[0], 7)

    def test_instalacion_nueva_tiene_el_esquema_nuevo_sin_copia(self):
        db = _abrir(self.ruta)
        cols = {r[1]: r for r in db.connection.execute("PRAGMA table_info(animal_readings)")}
        self.assertEqual(cols["reading_date"][3], 0)
        self.assertTrue({"reading_order", "upload_id", "origin", "cloud_id", "synced_at"} <= set(cols))
        self.assertEqual(glob.glob(self.ruta + ".antes-lecturas-*.bak"), [])

    def test_se_pueden_guardar_lecturas_sin_fecha_y_se_ordenan_como_en_la_nube(self):
        db = _abrir(self.ruta)
        farm = db.add_farm("G")
        animal = db.add_animal(farm, "A-1")
        u1 = db.create_upload(farm, "u1.xlsx")
        u2 = db.create_upload(farm, "u2.xlsx")
        db.connection.execute("UPDATE uploads SET upload_date='2026-03-01 10:00:00' WHERE id=?", (u1,))
        db.connection.execute("UPDATE uploads SET upload_date='2026-03-02 10:00:00' WHERE id=?", (u2,))
        db.connection.commit()
        # Insertadas desordenadas a propósito
        db.save_animal_reading(animal, None, 2.0, "u2.xlsx", reading_order=2, upload_id=u2)
        db.save_animal_reading(animal, None, 1.0, "u1.xlsx", reading_order=1, upload_id=u1)
        db.save_animal_reading(animal, None, 2.5, "u1.xlsx", reading_order=2, upload_id=u1)
        db.save_animal_reading(animal, None, 1.5, "u2.xlsx", reading_order=1, upload_id=u2)
        self.assertEqual([r["value"] for r in db.get_animal_readings(animal)], [1.0, 2.5, 1.5, 2.0])

    def test_si_algo_falla_se_revierte_y_la_base_queda_igual(self):
        self._base_antigua()
        con = sqlite3.connect(self.ruta)
        self.addCleanup(con.close)
        con.execute("PRAGMA foreign_keys=ON")
        real = readings_migration.analyze(con)
        falso = dict(real, lecturas=real["lecturas"] + 1)
        with mock.patch.object(readings_migration, "analyze", return_value=falso):
            with self.assertRaises(RuntimeError):
                readings_migration.migrate(con, self.ruta)
        self.assertTrue(readings_migration.needs_migration(con))
        self.assertEqual(con.execute("SELECT reading_date FROM animal_readings WHERE id=3").fetchone()[0], "date_1")
        self.assertEqual(
            con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='animal_readings_new'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
