"""Migración de la leche: de «un animal por muestra» a `sample_id`.

    python -m unittest backend.tests.test_milk_migration -v
"""
import glob
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from backend.data_access import milk_migration
from backend.data_access.db_manager import DatabaseManager

# Esquema anterior a la migración (tal como lo creaba la versión local).
ESQUEMA_ANTIGUO = """
CREATE TABLE farms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '', created_at DATETIME NOT NULL DEFAULT (datetime('now')));
CREATE TABLE animals (id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id INTEGER NOT NULL,
    external_tag TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE, UNIQUE(farm_id, external_tag));
CREATE TABLE animal_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, animal_id INTEGER NOT NULL,
    reading_date DATE NOT NULL, value FLOAT NOT NULL, source_file TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE);
CREATE TABLE uploads (id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id INTEGER NOT NULL,
    filename TEXT NOT NULL, upload_date DATETIME NOT NULL DEFAULT (datetime('now')),
    processed_at DATETIME, total_animals INTEGER DEFAULT 0, celo_count INTEGER DEFAULT 0,
    no_celo_count INTEGER DEFAULT 0, FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE);
CREATE TABLE detection_results (id INTEGER PRIMARY KEY AUTOINCREMENT, animal_id INTEGER NOT NULL,
    upload_id INTEGER NOT NULL, result TEXT NOT NULL CHECK (result IN ('Celo', 'No celo')),
    confidence FLOAT NOT NULL DEFAULT 0.0, probability FLOAT NOT NULL DEFAULT 0.0,
    created_at DATETIME NOT NULL DEFAULT (datetime('now')), is_synced INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE);
CREATE TABLE milk_quality_uploads (id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id INTEGER NOT NULL,
    filename TEXT NOT NULL, upload_date DATETIME NOT NULL DEFAULT (datetime('now')),
    processed_at DATETIME, total_samples INTEGER DEFAULT 0, lower_count INTEGER DEFAULT 0,
    upper_count INTEGER DEFAULT 0, FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE);
CREATE TABLE milk_quality_results (id INTEGER PRIMARY KEY AUTOINCREMENT, animal_id INTEGER NOT NULL,
    upload_id INTEGER NOT NULL, result TEXT NOT NULL CHECK (result IN ('Lower', 'Upper')),
    created_at DATETIME NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE,
    FOREIGN KEY (upload_id) REFERENCES milk_quality_uploads(id) ON DELETE CASCADE);
CREATE TABLE farmcalendar_sync (id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('farm', 'parcel', 'animal')),
    local_id INTEGER NOT NULL, fc_uuid TEXT NOT NULL,
    synced_at DATETIME NOT NULL DEFAULT (datetime('now')), UNIQUE(entity_type, local_id));
"""


def _nuevo_gestor(ruta: str) -> DatabaseManager:
    # DatabaseManager es un singleton: se reinicia para abrir otra base.
    if DatabaseManager._instance is not None:
        DatabaseManager._instance.close()
    DatabaseManager._instance = None
    DatabaseManager._initialized = False
    return DatabaseManager(ruta)


class MigracionLeche(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.dir.name, "sheepcare.db")
        self.addCleanup(self.dir.cleanup)   # se ejecuta el último (LIFO)
        self.addCleanup(self._cerrar_gestor)

    def _cerrar_gestor(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def _base_antigua(self):
        """Granja 1 con: 2 muestras solo-leche, 1 animal de celo, 1 con leche+lecturas,
        1 con leche+celo, una muestra que se repite en dos subidas, y la misma etiqueta
        'M-1' en otra granja."""
        c = sqlite3.connect(self.ruta)
        c.executescript(ESQUEMA_ANTIGUO)
        c.execute("INSERT INTO farms (name) VALUES ('A'), ('B')")
        c.executemany("INSERT INTO animals (id, farm_id, external_tag, name) VALUES (?,?,?,?)", [
            (1, 1, "M-1", "M-1"), (2, 1, "M-2", "M-2"),       # solo leche
            (3, 1, "CELO", ""),                                # solo celo
            (4, 1, "LEC", ""),                                 # leche + lecturas
            (5, 1, "AMBOS", ""),                               # leche + celo
            (6, 2, "M-1", "M-1"),                              # misma etiqueta, otra granja
        ])
        c.execute("INSERT INTO uploads (id, farm_id, filename) VALUES (1, 1, 'celo.xlsx')")
        c.executemany("INSERT INTO detection_results (animal_id, upload_id, result) VALUES (?,1,'Celo')", [(3,), (5,)])
        c.execute("INSERT INTO animal_readings (animal_id, reading_date, value) VALUES (4, '2026-01-01', 1.0)")
        c.executemany("INSERT INTO milk_quality_uploads (id, farm_id, filename) VALUES (?,?,?)",
                      [(1, 1, "l1.xlsx"), (2, 1, "l2.xlsx"), (3, 2, "l3.xlsx")])
        c.executemany("INSERT INTO milk_quality_results (id, animal_id, upload_id, result) VALUES (?,?,?,?)", [
            (1, 1, 1, "Lower"), (2, 2, 1, "Upper"), (3, 4, 1, "Lower"), (4, 5, 1, "Upper"),
            (5, 1, 2, "Upper"),                                # M-1 vuelve a subirse
            (6, 6, 3, "Lower"),
        ])
        c.execute("INSERT INTO farmcalendar_sync (entity_type, local_id, fc_uuid) VALUES ('animal', 1, 'x')")
        c.execute("INSERT INTO farmcalendar_sync (entity_type, local_id, fc_uuid) VALUES ('animal', 3, 'y')")
        c.commit()
        c.close()

    def test_migra_sin_perder_resultados_ni_animales_reales(self):
        self._base_antigua()
        db = _nuevo_gestor(self.ruta)          # la migración corre al abrir
        con = db.connection
        res = [tuple(r) for r in con.execute(
            "SELECT id, sample_id, upload_id, result FROM milk_quality_results ORDER BY id")]
        self.assertEqual(res, [
            (1, "M-1", 1, "Lower"), (2, "M-2", 1, "Upper"), (3, "LEC", 1, "Lower"),
            (4, "AMBOS", 1, "Upper"), (5, "M-1", 2, "Upper"), (6, "M-1", 3, "Lower"),
        ])
        # Solo desaparecen los animales que existían por la leche (1, 2 y 6)
        animales = {r[0] for r in con.execute("SELECT id FROM animals")}
        self.assertEqual(animales, {3, 4, 5})
        # Celo y lecturas intactos
        self.assertEqual(con.execute("SELECT COUNT(*) FROM detection_results").fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM animal_readings").fetchone()[0], 1)
        # Se limpia el mapeo de Farm Calendar de los animales borrados, no el de los demás
        fc = [r[0] for r in con.execute("SELECT local_id FROM farmcalendar_sync WHERE entity_type='animal'")]
        self.assertEqual(fc, [3])
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_hace_copia_de_seguridad_con_los_datos_antiguos(self):
        self._base_antigua()
        _nuevo_gestor(self.ruta)
        copias = glob.glob(self.ruta + ".antes-leche-*.bak")
        self.assertEqual(len(copias), 1)
        c = sqlite3.connect(copias[0])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM animals").fetchone()[0], 6)
        self.assertIn("animal_id", [r[1] for r in c.execute("PRAGMA table_info(milk_quality_results)")])
        c.close()

    def test_es_idempotente(self):
        self._base_antigua()
        _nuevo_gestor(self.ruta)
        db = _nuevo_gestor(self.ruta)          # segunda apertura: nada que migrar
        self.assertEqual(len(glob.glob(self.ruta + ".antes-leche-*.bak")), 1)
        self.assertEqual(db.connection.execute("SELECT COUNT(*) FROM milk_quality_results").fetchone()[0], 6)

    def test_la_api_de_leche_ya_no_crea_animales(self):
        self._base_antigua()
        db = _nuevo_gestor(self.ruta)
        antes = db.connection.execute("SELECT COUNT(*) FROM animals").fetchone()[0]
        subida = db.create_milk_quality_upload(1, "nueva.xlsx")
        db.save_milk_quality_result("M-99", subida, "Lower")
        self.assertEqual(db.connection.execute("SELECT COUNT(*) FROM animals").fetchone()[0], antes)
        fila = db.get_milk_quality_results(upload_id=subida)[0]
        self.assertEqual((fila["sample_id"], fila["animal_tag"], fila["animal_name"]), ("M-99", "M-99", ""))
        self.assertEqual(fila["origin"], "edge")
        self.assertEqual(fila["is_synced"], 0)

    def test_instalacion_nueva_usa_el_esquema_nuevo_sin_copia(self):
        db = _nuevo_gestor(self.ruta)
        cols = [r[1] for r in db.connection.execute("PRAGMA table_info(milk_quality_results)")]
        self.assertIn("sample_id", cols)
        self.assertNotIn("animal_id", cols)
        up = [r[1] for r in db.connection.execute("PRAGMA table_info(milk_quality_uploads)")]
        self.assertTrue({"origin", "cloud_id", "synced_at"} <= set(up))
        self.assertEqual(glob.glob(self.ruta + ".antes-leche-*.bak"), [])

    def test_si_algo_falla_se_revierte_y_la_base_queda_igual(self):
        self._base_antigua()
        con = sqlite3.connect(self.ruta)
        self.addCleanup(con.close)
        con.execute("PRAGMA foreign_keys=ON")
        real = milk_migration.analyze(con)
        falso = dict(real, resultados_leche=real["resultados_leche"] + 1)  # fuerza el fallo de la comprobación
        with mock.patch.object(milk_migration, "analyze", return_value=falso):
            with self.assertRaises(RuntimeError):
                milk_migration.migrate(con, self.ruta)
        # Sigue el esquema antiguo, con todos sus animales y resultados
        self.assertTrue(milk_migration.needs_migration(con))
        self.assertEqual(con.execute("SELECT COUNT(*) FROM animals").fetchone()[0], 6)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM milk_quality_results").fetchone()[0], 6)
        self.assertEqual(
            con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='milk_quality_results_new'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
