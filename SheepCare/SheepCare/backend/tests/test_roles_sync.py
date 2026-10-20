"""Roles en el Edge, sincronización: `access`, `removed` y el rechazo «sin permiso».

    python -m unittest backend.tests.test_roles_sync -v

La nube simulada sigue el contrato (docs/CONTRATO_SYNC_EDGE_ROLES.md de Sheepcare_cloud):
`access` en cada granja del pull, `removed` con las granjas que la persona ya no ve (se repite
hasta confirmarlo con `confirm-sync?table=removed`) y, en el push, un `error` con «sin permiso
sobre la granja» para lo que no puede escribir.
"""
import os
import tempfile
import unittest
from unittest import mock

from backend.data_access import sync_manager
from backend.data_access.db_manager import DatabaseManager
from backend.data_access.sync_manager import SyncService
from backend.tests.test_milk_sync import FakeCloud, _nuevo_gestor, simular_calendario

ISO = "2026-03-10T08:00:00+00:00"
SIN_PERMISO = "sin permiso sobre la granja"


class NubeConRoles(FakeCloud):
    def __init__(self):
        super().__init__()
        self.sin_permiso = set()   # (tabla, origin_id) que la nube rechaza por falta de permiso

    def post(self, url, json=None, headers=None, params=None, timeout=None, **kw):
        resp = super().post(url, json=json, headers=headers, params=params, timeout=timeout, **kw)
        if url.endswith("/api/sync/push") and resp.status_code == 200:
            for e in resp._body.get("errors", []):
                if (e["table"], e["origin_id"]) in self.sin_permiso:
                    e["detail"] = SIN_PERMISO + ": ya no eres su propietaria"
        return resp


def granja_nube(cloud_id, nombre="Compartida", access="shared", **extra):
    f = {"id": cloud_id, "name": nombre, "location": "Soria", "created_at": ISO,
         "origin": "cloud", "origin_id": 0, "access": access}
    f.update(extra)
    return f


class BaseRolesSync(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.addCleanup(self._cerrar)
        self.db = _nuevo_gestor(os.path.join(self.dir.name, "t.db"))
        self.nube = NubeConRoles()
        simular_calendario(self)
        for nombre in ("get", "post"):
            p = mock.patch.object(sync_manager.requests, nombre, getattr(self.nube, nombre))
            p.start()
            self.addCleanup(p.stop)
        self.svc = SyncService(self.db, "https://nube.test", "isaac@x.es", "pw")

    def _cerrar(self):
        if DatabaseManager._instance is not None:
            DatabaseManager._instance.close()
        DatabaseManager._instance = None
        DatabaseManager._initialized = False

    def pull(self, **datos):
        self.nube.pull_data = datos
        self.nube.confirms.clear()
        return self.svc.pull_from_cloud()

    def farm_por_nube(self, cloud_id):
        fila = self.db.connection.execute("SELECT * FROM farms WHERE cloud_id = ?", (cloud_id,)).fetchone()
        return dict(fila) if fila else None


class PullAccessTest(BaseRolesSync):
    def test_guarda_el_access_de_cada_granja(self):
        self.pull(farms=[granja_nube(5, "Mia", "owner"), granja_nube(6, "Ajena", "shared"),
                         granja_nube(7, "Todas", "admin")])
        self.assertEqual({f["name"]: f["cloud_access"] for f in self.db.list_farms()},
                         {"Mia": "owner", "Ajena": "shared", "Todas": "admin"})

    def test_una_granja_propia_que_vuelve_como_padre_guarda_su_access(self):
        farm = self.db.add_farm("Creada aqui")
        self.db.connection.execute("UPDATE farms SET cloud_id = NULL WHERE id = ?", (farm,))
        self.db.connection.commit()
        self.pull(farms=[granja_nube(9, "Creada aqui", "owner", origin="edge", origin_id=farm)])
        fila = self.db.get_farm(farm)
        # Se reconoce como propia, se enlaza con su id de la nube y guarda el acceso en el mismo pull.
        self.assertEqual((fila["cloud_id"], fila["cloud_access"]), (9, "owner"))
        self.assertEqual(len(self.db.list_farms()), 1, "no se duplica")


class PullRemovedTest(BaseRolesSync):
    def setUp(self):
        super().setUp()
        self.pull(farms=[granja_nube(5, "Compartida"), granja_nube(6, "Otra")])
        self.local = self.farm_por_nube(5)["id"]
        self.db.add_animal(self.local, "OV-1")

    def test_oculta_la_granja_sin_borrar_nada(self):
        r = self.pull(removed=[{"table": "farms", "cloud_id": 5}])
        self.assertTrue(r["success"])
        self.assertEqual(r["removed_count"], 1)
        self.assertEqual([f["name"] for f in self.db.list_farms()], ["Otra"])
        self.assertEqual(self.farm_por_nube(5)["hidden"], 1)
        n = self.db.connection.execute("SELECT COUNT(*) FROM animals WHERE farm_id = ?", (self.local,)).fetchone()[0]
        self.assertEqual(n, 1, "los datos siguen en la base")

    def test_se_confirma_en_la_nube(self):
        self.pull(removed=[{"table": "farms", "cloud_id": 5}])
        self.assertIn(("removed", [5]), self.nube.confirms)

    def test_una_granja_desconocida_tambien_se_confirma_y_no_rompe(self):
        r = self.pull(removed=[{"table": "farms", "cloud_id": 999}])
        self.assertTrue(r["success"])
        self.assertIn(("removed", [999]), self.nube.confirms)
        self.assertEqual(len(self.db.list_farms()), 2)

    def test_solo_se_tratan_las_granjas(self):
        self.pull(removed=[{"table": "animals", "cloud_id": 5}])
        self.assertEqual(len(self.db.list_farms()), 2)
        self.assertNotIn("removed", [t for t, _ in self.nube.confirms])

    def test_sin_removed_no_cambia_nada(self):
        r = self.pull()
        self.assertEqual((r["success"], r["removed_count"]), (True, 0))
        self.assertEqual(len(self.db.list_farms()), 2)

    def test_lo_oculto_no_se_envia(self):
        self.db.connection.execute("UPDATE animals SET origin = 'edge', cloud_id = NULL")
        self.db.connection.commit()
        self.pull(removed=[{"table": "farms", "cloud_id": 5}])
        self.assertEqual(self.db.get_unsynced_animals_to_cloud(), [])

    def test_si_vuelve_a_compartirse_se_reactiva_sin_duplicar(self):
        self.pull(removed=[{"table": "farms", "cloud_id": 5}])
        self.pull(farms=[granja_nube(5, "Compartida", "owner")])
        self.assertEqual(len(self.db.list_farms()), 2)
        fila = self.farm_por_nube(5)
        self.assertEqual((fila["hidden"], fila["cloud_access"], fila["id"]), (0, "owner", self.local))

    def test_una_granja_propia_oculta_se_reactiva_al_volver_como_padre(self):
        propia = self.db.add_farm("Mia")
        self.db.connection.execute("UPDATE farms SET cloud_id = 20 WHERE id = ?", (propia,))
        self.db.connection.commit()
        self.pull(removed=[{"table": "farms", "cloud_id": 20}])
        self.assertIsNone(self.db.get_farm(propia))
        self.pull(farms=[granja_nube(20, "Mia", "owner", origin="edge", origin_id=propia)])
        fila = self.db.get_farm(propia)
        self.assertEqual((fila["hidden"], fila["cloud_access"]), (0, "owner"))


class PushSinPermisoTest(BaseRolesSync):
    def _granja_pendiente(self, nombre="Propia"):
        return self.db.add_farm(nombre)

    def test_lo_rechazado_por_falta_de_permiso_se_aparta_y_no_se_reintenta(self):
        a, b = self._granja_pendiente("A"), self._granja_pendiente("B")
        self.nube.sin_permiso = {("farms", a)}
        self.nube.omit = {("farms", a)}
        r = self.svc.sync_to_cloud()
        self.assertTrue(r["success"])
        self.assertEqual(r["blocked_count"], 1)
        self.assertNotIn("errors", r)
        self.assertEqual([x["table_name"] for x in self.db.list_blocked()], ["farms"])
        self.assertEqual(self.db.list_blocked()[0]["origin_id"], a)
        self.assertIn(SIN_PERMISO, self.db.list_blocked()[0]["reason"])

        self.nube.pushes.clear()
        self.nube.omit = set()
        r2 = self.svc.sync_to_cloud()
        self.assertTrue(r2["success"])
        self.assertEqual(self.nube.pushes, [], "A está apartada y B ya se envió: no queda nada")
        self.assertIsNotNone(self.db.get_farm(a), "el dato local no se toca")
        self.assertIsNotNone(self.db.get_farm(b))

    def test_otros_errores_se_siguen_reintentando(self):
        a = self._granja_pendiente()
        self.nube.omit = {("farms", a)}     # la nube dice «no encontrado», sin «sin permiso»
        r = self.svc.sync_to_cloud()
        self.assertEqual(len(r["errors"]), 1)
        self.assertNotIn("blocked_count", r)
        self.assertEqual(self.db.count_blocked(), 0)
        self.nube.omit = set()
        self.nube.pushes.clear()
        self.svc.sync_to_cloud()
        self.assertEqual(len(self.nube.pushes), 1, "se reintenta y esta vez se acepta")

    def test_una_tabla_desconocida_con_sin_permiso_no_se_aparta(self):
        error = {"table": "otra_cosa", "origin_id": 1, "detail": SIN_PERMISO}
        self.assertFalse(self.svc._apartar_si_sin_permiso(error))
        self.assertEqual(self.db.count_blocked(), 0)

    def test_el_motivo_se_reconoce_sin_importar_mayusculas_y_el_resto_del_texto(self):
        a = self._granja_pendiente()
        for detalle in ("Sin permiso sobre la granja", SIN_PERMISO + ": ya no eres su propietaria"):
            self.db.connection.execute("DELETE FROM sync_blocked")
            self.assertTrue(self.svc._apartar_si_sin_permiso({"table": "farms", "origin_id": a, "detail": detalle}))

    def test_un_error_sin_origin_id_o_sin_detalle_no_rompe(self):
        for error in ({"table": "farms", "detail": SIN_PERMISO}, {"table": "farms", "origin_id": 1},
                      {}, {"detail": None}):
            self.assertFalse(self.svc._apartar_si_sin_permiso(error))

    def test_se_libera_si_la_granja_recupera_el_acceso(self):
        self.pull_inicial = self.svc.pull_from_cloud  # el pull usa la nube simulada
        self.nube.pull_data = {"farms": [granja_nube(5, "Compartida")]}
        self.svc.pull_from_cloud()
        local = self.farm_por_nube(5)["id"]
        animal = self.db.add_animal(local, "OV-1")
        self.db.block_record("animals", animal, SIN_PERMISO)
        self.nube.pull_data = {"removed": [{"table": "farms", "cloud_id": 5}]}
        self.svc.pull_from_cloud()
        self.assertEqual(self.db.count_blocked(), 1)
        self.nube.pull_data = {"farms": [granja_nube(5, "Compartida", "owner")]}
        self.svc.pull_from_cloud()
        self.assertEqual(self.db.count_blocked(), 0)


if __name__ == "__main__":
    unittest.main()
