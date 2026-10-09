"""Sincronización de la leche con la nube (push y pull), contra una nube simulada.

    python -m unittest backend.tests.test_milk_sync -v

La nube simulada sigue el contrato real de `/api/sync/push|pull|confirm-sync`:
asigna ids, omite con `errors` lo que no puede guardar y no devuelve mapeo para eso.
"""
import os
import tempfile
import unittest
from unittest import mock

from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService


class Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = str(self._body)

    def json(self):
        return self._body


class FakeCloud:
    def __init__(self):
        self.pushes = []          # payloads recibidos, en orden
        self.headers = []         # (operación, cabeceras) de las llamadas de sync
        self.confirms = []        # (tabla, ids)
        self.pull_data = {}
        self.omit = set()         # (tabla, origin_id) que la nube se niega a guardar
        self.fail_push_call = None  # nº de petición push (1,2,...) que responde 500
        self.unauthorized_once = False
        self._next = 1000

    def get(self, url, headers=None, timeout=None, **kw):
        if url.endswith("/api/health"):
            return Resp(200)
        if url.endswith("/api/auth/me"):
            return Resp(200, {"id": 1})
        if url.endswith("/api/sync/pull"):
            self.headers.append(("pull", dict(headers or {})))
            return Resp(200, self.pull_data)
        return Resp(404)

    def post(self, url, json=None, headers=None, params=None, timeout=None, **kw):
        if url.endswith("/gatekeeper/api/login/"):
            return Resp(200, {"access": "tok"})
        if url.endswith("/api/sync/confirm-sync"):
            self.headers.append(("confirm", dict(headers or {})))
            self.confirms.append((params["table"], json["record_ids"]))
            return Resp(200, {"success": True})
        if url.endswith("/api/sync/push"):
            self.headers.append(("push", dict(headers or {})))
            self.pushes.append(json)
            if self.unauthorized_once:
                self.unauthorized_once = False
                self.pushes.pop()
                return Resp(401)
            if self.fail_push_call == len(self.pushes):
                return Resp(500, {"detail": "boom"})
            mappings, errors = [], []
            for tabla, clave in (("farms", "farms"), ("milk_quality_uploads", "milk_uploads"),
                                 ("milk_quality_results", "milk_results")):
                for rec in json.get(clave, []):
                    if (tabla, rec["origin_id"]) in self.omit:
                        errors.append({"table": tabla, "origin_id": rec["origin_id"], "detail": "no encontrado"})
                        continue
                    self._next += 1
                    mappings.append({"table": tabla, "origin_id": rec["origin_id"], "cloud_id": self._next})
            return Resp(200, {"success": True, "mappings": mappings, "errors": errors, "publish": []})
        return Resp(404)


def _nuevo_gestor(ruta):
    if DatabaseManager._instance is not None:
        DatabaseManager._instance.close()
    DatabaseManager._instance = None
    DatabaseManager._initialized = False
    return DatabaseManager(ruta)


class SyncLeche(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.db = _nuevo_gestor(os.path.join(self.dir.name, "t.db"))
        self.nube = FakeCloud()
        for objetivo, nombre in ((sync_manager.requests, "get"), (sync_manager.requests, "post")):
            p = mock.patch.object(objetivo, nombre, getattr(self.nube, nombre))
            p.start()
            self.addCleanup(p.stop)
        self.svc = SyncService(self.db, "https://nube.test", "ana@x.es", "pw")

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    # ── ayudas ──
    def _subida_leche(self, farm_id, muestras, finalizada=True, nombre="l.xlsx"):
        up = self.db.create_milk_quality_upload(farm_id, nombre)
        for i, (sid, res) in enumerate(muestras):
            self.db.save_milk_quality_result(sid, up, res)
        if finalizada:
            self.db.finalize_milk_quality_upload(
                up, len(muestras), sum(1 for _, r in muestras if r == "Lower"),
                sum(1 for _, r in muestras if r == "Upper"))
        return up

    def _fila(self, tabla, id_):
        return dict(self.db.connection.execute(f"SELECT * FROM {tabla} WHERE id = ?", (id_,)).fetchone())

    # ── push ──
    def test_push_envia_subidas_y_luego_resultados_y_marca_lo_guardado(self):
        farm = self.db.add_farm("Granja")
        up = self._subida_leche(farm, [("A1", "Lower"), ("A2", "Upper"), ("A1", "Upper")])
        r = self.svc.sync_to_cloud()
        self.assertTrue(r["success"])
        self.assertEqual(len(self.nube.pushes), 2)
        primero, segundo = self.nube.pushes
        self.assertEqual([k for k in primero], ["farms", "milk_uploads"])
        self.assertNotIn("farm_cloud_id", primero["milk_uploads"][0])   # granja nueva: se resuelve en la petición
        self.assertEqual(list(segundo), ["milk_results"])
        self.assertEqual([m["sample_id"] for m in segundo["milk_results"]], ["A1", "A2", "A1"])
        self.assertNotIn("upload_cloud_id", segundo["milk_results"][0])  # aún no tenía id en la nube
        self.assertEqual(r["synced_count"], 1 + 1 + 3)
        # Marcado local
        u = self._fila("milk_quality_uploads", up)
        self.assertIsNotNone(u["cloud_id"])
        self.assertIsNotNone(u["synced_at"])
        res = self.db.connection.execute("SELECT cloud_id, is_synced, origin FROM milk_quality_results").fetchall()
        self.assertTrue(all(x["cloud_id"] and x["is_synced"] == 1 and x["origin"] == "edge" for x in res))

    def test_segunda_sincronizacion_no_reenvia_nada(self):
        farm = self.db.add_farm("Granja")
        self._subida_leche(farm, [("A1", "Lower")])
        self.svc.sync_to_cloud()
        antes = len(self.nube.pushes)
        r = self.svc.sync_to_cloud()
        self.assertEqual((r["success"], r["synced_count"]), (True, 0))
        self.assertEqual(len(self.nube.pushes), antes)

    def test_una_subida_sin_finalizar_no_se_envia(self):
        farm = self.db.add_farm("Granja")
        self._subida_leche(farm, [("A1", "Lower")], finalizada=False)
        self.svc.sync_to_cloud()
        # Solo viaja la granja: ni la subida ni sus resultados
        enviado = {k for p in self.nube.pushes for k in p}
        self.assertEqual(enviado, {"farms"})
        # Al finalizar, en la siguiente vuelta sí
        up = self.db.connection.execute("SELECT id FROM milk_quality_uploads").fetchone()["id"]
        self.db.finalize_milk_quality_upload(up, 1, 1, 0)
        self.svc.sync_to_cloud()
        enviado = {k for p in self.nube.pushes for k in p}
        self.assertEqual(enviado, {"farms", "milk_uploads", "milk_results"})

    def test_los_resultados_van_por_lotes(self):
        farm = self.db.add_farm("Granja")
        self._subida_leche(farm, [(f"S{i}", "Lower") for i in range(1200)])
        self.svc.sync_to_cloud()
        lotes = [len(p["milk_results"]) for p in self.nube.pushes if "milk_results" in p]
        self.assertEqual(lotes, [500, 500, 200])
        self.assertEqual(
            self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_results WHERE cloud_id IS NOT NULL").fetchone()[0],
            1200)

    def test_granja_y_subida_de_la_nube_viajan_con_su_cloud_id(self):
        farm = self.db.upsert_farm_from_cloud(77, "De la nube", "", "2026-01-01T00:00:00")
        up = self._subida_leche(farm, [("A1", "Lower")])
        # La subida ya estuvo en la nube pero faltan resultados por enviar
        self.db.mark_milk_upload_synced(up, 555)
        self.db.connection.execute("UPDATE milk_quality_uploads SET synced_at = NULL WHERE id = ?", (up,))
        self.db.connection.commit()
        self.svc.sync_to_cloud()
        self.assertEqual(self.nube.pushes[0]["milk_uploads"][0]["farm_cloud_id"], 77)
        self.assertEqual(self.nube.pushes[1]["milk_results"][0]["upload_cloud_id"], 555)

    def test_lo_que_la_nube_omite_no_se_marca_y_se_informa(self):
        farm = self.db.add_farm("Granja")
        self._subida_leche(farm, [("A1", "Lower"), ("A2", "Lower")])
        rid = self.db.connection.execute("SELECT id FROM milk_quality_results ORDER BY id").fetchall()[1]["id"]
        self.nube.omit = {("milk_quality_results", rid)}
        r = self.svc.sync_to_cloud()
        self.assertTrue(r["success"])
        self.assertEqual([e["origin_id"] for e in r["errors"]], [rid])
        self.assertIsNone(self._fila("milk_quality_results", rid)["cloud_id"])
        # Reintento: ahora sí, y solo viaja lo pendiente
        self.nube.omit = set()
        self.svc.sync_to_cloud()
        self.assertEqual([x["origin_id"] for x in self.nube.pushes[-1]["milk_results"]], [rid])
        self.assertIsNotNone(self._fila("milk_quality_results", rid)["cloud_id"])

    def test_si_un_lote_falla_se_conserva_lo_anterior_y_se_continua_despues(self):
        farm = self.db.add_farm("Granja")
        self.svc.MILK_RESULTS_PER_PUSH = 2
        self._subida_leche(farm, [(f"S{i}", "Lower") for i in range(5)])
        self.nube.fail_push_call = 3          # petición 1: base, 2: lote 1, 3: lote 2 -> 500
        r = self.svc.sync_to_cloud()
        self.assertFalse(r["success"])
        self.assertIn("500", r["error"])
        hechos = self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_results WHERE cloud_id IS NOT NULL").fetchone()[0]
        self.assertEqual(hechos, 2)           # el primer lote quedó guardado
        self.nube.fail_push_call = None
        r = self.svc.sync_to_cloud()
        self.assertTrue(r["success"])
        self.assertEqual(sum(len(p.get("milk_results", [])) for p in self.nube.pushes[3:]), 3)   # solo los 3 pendientes
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_results WHERE cloud_id IS NULL").fetchone()[0], 0)

    def test_un_401_renueva_el_token_una_vez(self):
        farm = self.db.add_farm("Granja")
        self._subida_leche(farm, [("A1", "Lower")])
        self.nube.unauthorized_once = True
        r = self.svc.sync_to_cloud()
        self.assertTrue(r["success"])

    # ── pull ──
    def _datos_pull(self):
        return {
            "farms": [{"id": 5, "name": "Web", "location": "", "created_at": "2026-02-01T00:00:00",
                       "origin": "cloud", "origin_id": 0, "access": "owner"}],
            "milk_uploads": [{"id": 9, "farm_id": 5, "filename": "web.xlsx", "upload_date": "2026-02-02T10:00:00+00:00",
                              "total_samples": 2, "lower_count": 1, "upper_count": 1, "origin": "cloud"}],
            "milk_results": [
                {"id": 100, "upload_id": 9, "sample_id": "W1", "result": "Lower", "created_at": "2026-02-02T10:00:01+00:00"},
                {"id": 101, "upload_id": 9, "sample_id": "W2", "result": "Upper", "created_at": "2026-02-02T10:00:02+00:00"},
                {"id": 102, "upload_id": 999, "sample_id": "HUERFANA", "result": "Lower", "created_at": "2026-02-02T10:00:03+00:00"},
            ],
        }

    def test_pull_guarda_leche_de_la_nube_sin_crear_animales_y_confirma(self):
        self.nube.pull_data = self._datos_pull()
        r = self.svc.pull_from_cloud()
        self.assertTrue(r["success"])
        c = self.db.connection
        up = dict(c.execute("SELECT * FROM milk_quality_uploads").fetchone())
        self.assertEqual((up["origin"], up["cloud_id"], up["total_samples"], up["lower_count"], up["upper_count"]),
                         ("cloud", 9, 2, 1, 1))
        self.assertIsNotNone(up["processed_at"])
        filas = [tuple(x) for x in c.execute("SELECT sample_id, result, origin, cloud_id FROM milk_quality_results ORDER BY id")]
        self.assertEqual(filas, [("W1", "Lower", "cloud", 100), ("W2", "Upper", "cloud", 101)])
        self.assertEqual(c.execute("SELECT COUNT(*) FROM animals").fetchone()[0], 0)
        # Se confirma lo guardado y NO lo que no se pudo (subida desconocida)
        confirmado = dict(self.nube.confirms)
        self.assertEqual(confirmado["milk_quality_uploads"], [9])
        self.assertEqual(sorted(confirmado["milk_quality_results"]), [100, 101])

    def test_pull_es_idempotente_y_lo_bajado_no_vuelve_a_subir(self):
        self.nube.pull_data = self._datos_pull()
        self.svc.pull_from_cloud()
        self.svc.pull_from_cloud()
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_results").fetchone()[0], 2)
        self.assertEqual(self.db.connection.execute("SELECT COUNT(*) FROM milk_quality_uploads").fetchone()[0], 1)
        # Lo que bajó de la nube no se reenvía en el push
        self.svc.sync_to_cloud()
        enviado = {k for p in self.nube.pushes for k in p}
        self.assertFalse(enviado & {"milk_uploads", "milk_results"})


if __name__ == "__main__":
    unittest.main()
