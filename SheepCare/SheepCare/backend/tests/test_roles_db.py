"""Roles en el Edge, capa de base de datos: granjas ocultas y registros apartados.

    python -m unittest backend.tests.test_roles_db -v

Una granja que la persona ya no ve en la nube se OCULTA (no se borra): no sale en ninguna
consulta de la interfaz ni se envía. Un registro que la nube rechaza por falta de permiso se
APARTA (`sync_blocked`): no se vuelve a enviar. Si la granja recupera el acceso, se reactiva
y se libera lo apartado.
"""
import os
import tempfile
import unittest

from backend.data_access.db_manager import DatabaseManager
from backend.tests.test_milk_sync import _nuevo_gestor

ISO = "2026-03-10T08:00:00+00:00"

# nombre en la nube -> consulta de pendientes que debe respetarlo
PENDIENTES = {
    "farms": "get_unsynced_farms_to_cloud",
    "animals": "get_unsynced_animals_to_cloud",
    "uploads": "get_unsynced_uploads_to_cloud",
    "animal_readings": "get_unsynced_readings_to_cloud",
    "detection_results": "get_unsynced_results",
    "milk_quality_uploads": "get_unsynced_milk_uploads_to_cloud",
    "milk_quality_results": "get_unsynced_milk_results_to_cloud",
}


class BaseRoles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.ruta = os.path.join(self.dir.name, "t.db")
        self.db = _nuevo_gestor(self.ruta)

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def granja_completa(self, nombre):
        """Una granja con un animal, una lectura, una subida de celo con su resultado y una de leche."""
        farm = self.db.add_farm(nombre)
        animal = self.db.add_animal(farm, f"{nombre}-1")
        lectura = self.db.save_animal_reading(animal, ISO, 1.5)
        subida = self.db.create_upload(farm, f"{nombre}.xlsx")
        self.db.finalize_upload(subida, 1, 1, 0)
        resultado = self.db.save_detection_result(animal, subida, "Celo", 0.9, 0.9)
        leche = self.db.create_milk_quality_upload(farm, f"{nombre}-leche.xlsx")
        muestra = self.db.save_milk_quality_result("M1", leche, "Lower")
        self.db.finalize_milk_quality_upload(leche, 1, 1, 0)
        return {
            "farm": farm, "animal": animal, "lectura": lectura, "subida": subida,
            "resultado": resultado, "leche": leche, "muestra": muestra,
        }

    def ids_pendientes(self, tabla):
        return {r["id"] for r in getattr(self.db, PENDIENTES[tabla])()}


class EsquemaTest(BaseRoles):
    def test_las_columnas_nuevas_existen_y_las_granjas_empiezan_visibles(self):
        farm = self.db.add_farm("A")
        fila = self.db.get_farm(farm)
        self.assertEqual(fila["hidden"], 0)
        self.assertIsNone(fila["cloud_access"])

    def test_abrir_otra_vez_la_misma_base_no_falla_ni_pierde_nada(self):
        farm = self.db.add_farm("A")
        self.db.hide_farms_by_cloud_id([])
        self.db.block_record("farms", farm, "x")
        self.db = _nuevo_gestor(self.ruta)  # reabre: repite las migraciones
        self.assertEqual(self.db.get_farm(farm)["name"], "A")
        self.assertEqual(self.db.count_blocked(), 1)

    def test_una_base_anterior_sin_las_columnas_se_actualiza(self):
        import sqlite3
        self._cerrar()
        antigua = os.path.join(self.dir.name, "vieja.db")
        con = sqlite3.connect(antigua)
        con.executescript(
            "CREATE TABLE farms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,"
            " location TEXT NOT NULL DEFAULT '', created_at DATETIME NOT NULL DEFAULT (datetime('now')));"
            "INSERT INTO farms (name) VALUES ('Antigua');"
        )
        con.commit()
        con.close()
        self.db = _nuevo_gestor(antigua)
        (granja,) = self.db.list_farms()
        self.assertEqual((granja["name"], granja["hidden"]), ("Antigua", 0))


class OcultarGranjasTest(BaseRoles):
    def setUp(self):
        super().setUp()
        self.visible = self.granja_completa("Visible")
        self.oculta = self.granja_completa("Oculta")
        self.db.connection.execute("UPDATE farms SET cloud_id = 77, origin = 'cloud' WHERE id = ?", (self.oculta["farm"],))
        self.db.connection.commit()
        self.assertEqual(self.db.hide_farms_by_cloud_id([77]), 1)

    def test_la_granja_oculta_no_sale_salvo_que_se_pida(self):
        self.assertEqual([f["name"] for f in self.db.list_farms()], ["Visible"])
        self.assertIsNone(self.db.get_farm(self.oculta["farm"]))
        self.assertEqual(self.db.get_farm(self.oculta["farm"], include_hidden=True)["name"], "Oculta")
        self.assertEqual({f["name"] for f in self.db.list_farms(include_hidden=True)}, {"Visible", "Oculta"})

    def test_sus_datos_tampoco_salen_en_la_interfaz(self):
        db, o = self.db, self.oculta
        self.assertEqual({a["id"] for a in db.list_animals()}, {self.visible["animal"]})
        self.assertIsNone(db.get_animal(o["animal"]))
        self.assertEqual({u["id"] for u in db.list_uploads()}, {self.visible["subida"]})
        self.assertIsNone(db.get_upload(o["subida"]))
        self.assertEqual({r["id"] for r in db.get_results()}, {self.visible["resultado"]})
        self.assertEqual(db.get_latest_result()["id"], self.visible["resultado"])
        self.assertEqual(db.get_animal_results(o["animal"]), [])
        self.assertEqual({u["id"] for u in db.list_milk_quality_uploads()}, {self.visible["leche"]})
        self.assertIsNone(db.get_milk_quality_upload(o["leche"]))
        self.assertEqual({r["id"] for r in db.get_milk_quality_results()}, {self.visible["muestra"]})

    def test_nada_de_lo_oculto_se_envia_a_la_nube(self):
        for tabla, clave in (("farms", "farm"), ("animals", "animal"), ("uploads", "subida"),
                             ("animal_readings", "lectura"), ("detection_results", "resultado"),
                             ("milk_quality_uploads", "leche"), ("milk_quality_results", "muestra")):
            with self.subTest(tabla=tabla):
                pendientes = self.ids_pendientes(tabla)
                self.assertIn(self.visible[clave], pendientes)
                self.assertNotIn(self.oculta[clave], pendientes)

    def test_los_datos_siguen_en_la_base(self):
        n = self.db.connection.execute(
            "SELECT COUNT(*) FROM animals WHERE farm_id = ?", (self.oculta["farm"],)
        ).fetchone()[0]
        self.assertEqual(n, 1)

    def test_una_id_desconocida_se_ignora(self):
        self.assertEqual(self.db.hide_farms_by_cloud_id([999]), 0)


class ApartarRegistrosTest(BaseRoles):
    def setUp(self):
        super().setUp()
        self.a = self.granja_completa("A")
        self.b = self.granja_completa("B")
        self.clave = {"farms": "farm", "animals": "animal", "uploads": "subida",
                      "animal_readings": "lectura", "detection_results": "resultado",
                      "milk_quality_uploads": "leche", "milk_quality_results": "muestra"}

    def test_cada_tabla_aparta_solo_su_registro(self):
        for tabla, clave in self.clave.items():
            with self.subTest(tabla=tabla):
                self.assertTrue(self.db.block_record(tabla, self.a[clave], "sin permiso sobre la granja"))
                self.assertNotIn(self.a[clave], self.ids_pendientes(tabla))
                self.assertIn(self.b[clave], self.ids_pendientes(tabla))

    def test_apartar_dos_veces_no_duplica(self):
        self.db.block_record("farms", self.a["farm"], "uno")
        self.db.block_record("farms", self.a["farm"], "dos")
        self.assertEqual(self.db.count_blocked(), 1)
        self.assertEqual(self.db.list_blocked()[0]["reason"], "dos")

    def test_una_tabla_desconocida_no_se_aparta(self):
        self.assertFalse(self.db.block_record("settings", 1, "x"))
        self.assertFalse(self.db.block_record("farms; DROP TABLE farms", 1, "x"))
        self.assertEqual(self.db.count_blocked(), 0)

    def test_apartar_no_borra_el_dato(self):
        self.db.block_record("animals", self.a["animal"], "x")
        self.assertIsNotNone(self.db.get_animal(self.a["animal"]))

    def test_unblock_libera_solo_lo_de_esa_granja(self):
        for tabla, clave in self.clave.items():
            self.db.block_record(tabla, self.a[clave], "x")
            self.db.block_record(tabla, self.b[clave], "x")
        self.assertEqual(self.db.count_blocked(), 14)
        self.assertEqual(self.db.unblock_farm_data(self.a["farm"]), 7)
        for tabla, clave in self.clave.items():
            with self.subTest(tabla=tabla):
                self.assertIn(self.a[clave], self.ids_pendientes(tabla))
                self.assertNotIn(self.b[clave], self.ids_pendientes(tabla))
        self.assertEqual({r["origin_id"] for r in self.db.list_blocked()},
                         {self.b[c] for c in self.clave.values()})


class DesdeLaNubeTest(BaseRoles):
    def test_una_granja_nueva_guarda_su_acceso(self):
        fid = self.db.upsert_farm_from_cloud(5, "Compartida", "Soria", ISO, access="shared")
        fila = self.db.get_farm(fid)
        self.assertEqual((fila["cloud_access"], fila["origin"], fila["cloud_id"], fila["hidden"]),
                         ("shared", "cloud", 5, 0))

    def test_sin_acceso_en_el_pull_queda_nulo(self):
        fid = self.db.upsert_farm_from_cloud(5, "Antigua", "", ISO)
        self.assertIsNone(self.db.get_farm(fid)["cloud_access"])

    def test_actualizar_conserva_el_acceso_si_la_nube_no_lo_manda(self):
        fid = self.db.upsert_farm_from_cloud(5, "X", "", ISO, access="shared")
        self.db.upsert_farm_from_cloud(5, "X2", "", ISO)
        fila = self.db.get_farm(fid)
        self.assertEqual((fila["name"], fila["cloud_access"]), ("X2", "shared"))

    def test_volver_a_compartir_reactiva_la_granja_y_libera_lo_apartado(self):
        fid = self.db.upsert_farm_from_cloud(5, "X", "", ISO, access="shared")
        animal = self.db.add_animal(fid, "T1")
        self.db.block_record("animals", animal, "sin permiso")
        self.assertEqual(self.db.hide_farms_by_cloud_id([5]), 1)
        self.assertIsNone(self.db.get_farm(fid))

        mismo = self.db.upsert_farm_from_cloud(5, "X", "", ISO, access="owner")
        self.assertEqual(mismo, fid, "no se duplica la granja")
        fila = self.db.get_farm(fid)
        self.assertEqual((fila["hidden"], fila["cloud_access"]), (0, "owner"))
        self.assertEqual(self.db.count_blocked(), 0)
        self.assertEqual(len(self.db.list_farms()), 1)

    def test_set_farm_access_actualiza_una_granja_enlazada(self):
        fid = self.db.add_farm("Propia")
        self.db.connection.execute("UPDATE farms SET cloud_id = 9 WHERE id = ?", (fid,))
        self.db.connection.commit()
        self.db.set_farm_access(9, "owner")
        self.assertEqual(self.db.get_farm(fid)["cloud_access"], "owner")
        self.db.set_farm_access(9, None)  # sin valor no pisa
        self.assertEqual(self.db.get_farm(fid)["cloud_access"], "owner")


if __name__ == "__main__":
    unittest.main()
