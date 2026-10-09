"""Lo que baja de la nube con el pull se publica en el Farm Calendar local.

    python -m unittest backend.tests.test_calendar_publisher -v

El Farm Calendar está simulado: estas pruebas no tocan uno real.
"""
import os
import tempfile
import unittest
from unittest import mock

from backend.data_access import calendar_publisher, sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService
from backend.tests.test_milk_sync import FakeCloud, simular_calendario

F_CELO = "2026-03-10T08:30:00+00:00"
F_LECHE = "2026-03-11T09:00:00+00:00"


def _datos_pull(extra_celo=0):
    """Una granja de la nube con una subida de celo (2 animales) y una de leche (3 muestras)."""
    d = {
        "farms": [{"id": 5, "name": "Web", "location": "Soria", "created_at": F_CELO, "origin": "cloud", "origin_id": 0}],
        "animals": [
            {"id": 11, "farm_id": 5, "external_tag": "OV-1", "name": "", "created_at": F_CELO},
            {"id": 12, "farm_id": 5, "external_tag": "OV-2", "name": "", "created_at": F_CELO},
        ],
        "uploads": [{"id": 20, "farm_id": 5, "filename": "celo.xlsx", "upload_date": F_CELO,
                     "total_animals": 2, "celo_count": 1, "no_celo_count": 1}],
        "results": [
            {"id": 31, "animal_id": 11, "upload_id": 20, "result": "Celo", "confidence": 0.91, "probability": 0.9, "created_at": F_CELO},
            {"id": 32, "animal_id": 12, "upload_id": 20, "result": "No celo", "confidence": 0.8, "probability": 0.1, "created_at": F_CELO},
        ],
        "milk_uploads": [{"id": 40, "farm_id": 5, "filename": "leche.xlsx", "upload_date": F_LECHE,
                          "total_samples": 3, "lower_count": 2, "upper_count": 1}],
        "milk_results": [
            {"id": 51, "upload_id": 40, "sample_id": "M-1", "result": "Lower", "created_at": F_LECHE},
            {"id": 52, "upload_id": 40, "sample_id": "M-2", "result": "Upper", "created_at": F_LECHE},
            {"id": 53, "upload_id": 40, "sample_id": "M-3", "result": "Lower", "created_at": F_LECHE},
        ],
    }
    return d


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


class PublicaLoQueBaja(Base):
    def test_publica_celo_y_leche_con_su_fecha_original_y_sus_detalles(self):
        self.nube.pull_data = _datos_pull()
        r = self.svc.pull_from_cloud()
        self.assertEqual((r["success"], r["published_count"]), (True, 2))
        cal = self.calendario

        self.assertEqual(len(cal.estrus), 1)
        e = cal.estrus[0]
        self.assertEqual((e["farm_name"], e["celo_count"], e["no_celo_count"], e["filename"]), ("Web", 1, 1, "celo.xlsx"))
        self.assertEqual(e["upload_date"], F_CELO)                                   # la fecha de la subida, no la de hoy
        self.assertEqual([(a["animal_id"], a["result"], a["confidence"]) for a in e["animal_details"]],
                         [("OV-1", "Celo", 0.91), ("OV-2", "No celo", 0.8)])

        self.assertEqual(len(cal.milk), 1)
        m = cal.milk[0]
        self.assertEqual((m["farm_name"], m["buena_count"], m["mala_count"], m["filename"]), ("Web", 2, 1, "leche.xlsx"))
        self.assertEqual(m["upload_date"], F_LECHE)
        self.assertEqual([(s["animal_id"], s["result"]) for s in m["sample_details"]],
                         [("M-1", "Lower"), ("M-2", "Upper"), ("M-3", "Lower")])

    def test_crea_la_granja_en_el_calendario_una_sola_vez(self):
        self.nube.pull_data = _datos_pull()
        self.svc.pull_from_cloud()
        self.assertEqual(self.calendario.farms, [("Web", "Soria")])                  # celo y leche comparten granja
        self.assertEqual(len(self.calendario.parcels), 1)
        farm = self.db.connection.execute("SELECT id FROM farms WHERE name='Web'").fetchone()["id"]
        self.assertIsNotNone(self.db.get_fc_uuid("farm", farm))

    def test_repetir_el_pull_no_publica_de_nuevo(self):
        self.nube.pull_data = _datos_pull()
        self.svc.pull_from_cloud()
        r = self.svc.pull_from_cloud()
        self.assertEqual(r["published_count"], 0)
        self.assertEqual((len(self.calendario.estrus), len(self.calendario.milk)), (1, 1))

    def test_una_subida_nueva_en_un_pull_posterior_solo_publica_esa(self):
        self.nube.pull_data = _datos_pull()
        self.svc.pull_from_cloud()
        # Otro pull: lo anterior vuelve a llegar y se suma una subida de leche nueva
        d = _datos_pull()
        d["milk_uploads"].append({"id": 41, "farm_id": 5, "filename": "leche2.xlsx", "upload_date": "2026-03-12T10:00:00+00:00",
                                  "total_samples": 1, "lower_count": 0, "upper_count": 1})
        d["milk_results"].append({"id": 54, "upload_id": 41, "sample_id": "M-9", "result": "Upper", "created_at": F_LECHE})
        self.nube.pull_data = d
        r = self.svc.pull_from_cloud()
        self.assertEqual(r["published_count"], 1)
        self.assertEqual([x["filename"] for x in self.calendario.milk], ["leche.xlsx", "leche2.xlsx"])
        self.assertEqual(len(self.calendario.estrus), 1)

    def test_lo_que_creo_esta_instalacion_y_vuelve_como_padre_no_se_publica(self):
        farm = self.db.add_farm("Mía")
        subida = self.db.create_milk_quality_upload(farm, "mia.xlsx")
        self.db.finalize_milk_quality_upload(subida, 0, 0, 0)
        self.db.mark_farm_synced(farm, 5)
        self.db.mark_milk_upload_synced(subida, 40)
        self.nube.pull_data = {
            "farms": [{"id": 5, "name": "Mía", "location": "", "created_at": F_CELO, "origin": "edge", "origin_id": farm}],
            "milk_uploads": [{"id": 40, "farm_id": 5, "filename": "mia.xlsx", "upload_date": F_LECHE, "total_samples": 0,
                              "lower_count": 0, "upper_count": 0, "origin": "edge", "origin_id": subida}],
        }
        r = self.svc.pull_from_cloud()
        self.assertEqual((r["success"], r["published_count"]), (True, 0))
        self.assertEqual((self.calendario.estrus, self.calendario.milk), ([], []))


class SiElCalendarioFalla(Base):
    def _comprobar_que_el_pull_no_se_resiente(self, r):
        self.assertTrue(r["success"])
        # Lo importante: el dato está guardado y confirmado
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_results").fetchone()[0], 3)
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM detection_results").fetchone()[0], 2)
        confirmado = dict(self.nube.confirms)
        self.assertEqual(confirmado["uploads"], [20])
        self.assertEqual(confirmado["milk_quality_uploads"], [40])

    def test_si_responde_que_no_el_pull_sigue_igual(self):
        self.calendario.fallar = True
        self.nube.pull_data = _datos_pull()
        r = self.svc.pull_from_cloud()
        self._comprobar_que_el_pull_no_se_resiente(r)
        self.assertEqual(r["published_count"], 0)

    def test_si_lanza_una_excepcion_el_pull_sigue_igual(self):
        self.calendario.explotar = True
        self.nube.pull_data = _datos_pull()
        r = self.svc.pull_from_cloud()
        self._comprobar_que_el_pull_no_se_resiente(r)

    def test_tras_dos_fallos_seguidos_deja_de_intentarlo(self):
        self.calendario.fallar = True
        self.nube.pull_data = _datos_pull()
        # Cuatro subidas más de leche: seis en total, pero solo se intentan dos
        for i in range(4):
            self.nube.pull_data["milk_uploads"].append({
                "id": 60 + i, "farm_id": 5, "filename": f"l{i}.xlsx", "upload_date": F_LECHE,
                "total_samples": 0, "lower_count": 0, "upper_count": 0})
        self.svc.pull_from_cloud()
        intentos = len(self.calendario.estrus) + len(self.calendario.milk)
        self.assertEqual(intentos, calendar_publisher.MAX_FALLOS_SEGUIDOS)

    def test_un_fallo_suelto_no_impide_publicar_el_resto(self):
        d = _datos_pull()
        self.nube.pull_data = d
        original = self.calendario.post_estrus_detection
        self.calendario.post_estrus_detection = lambda **kw: (original(**kw), False)[1]   # solo falla el celo
        r = self.svc.pull_from_cloud()
        self.assertEqual(r["published_count"], 1)                       # la leche sí
        self.assertEqual(len(self.calendario.milk), 1)


if __name__ == "__main__":
    unittest.main()
