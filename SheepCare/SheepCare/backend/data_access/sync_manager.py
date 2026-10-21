"""
SyncService - Bidirectional Edge-Cloud synchronization.

Flow:
  1. Edge pushes local (origin='edge') data TO Cloud (POST /api/sync/push)
  2. Edge pulls Cloud-originated data FROM Cloud (GET /api/sync/pull)
  3. Edge confirms receipt of pulled data (POST /api/sync/confirm-sync)

Edge stores cloud credentials (email + password) in local cloud_config table.
Cloud returns JWT tokens for authentication.
"""

import requests
import logging
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List
from ..data_access.db_manager import DatabaseManager
from ..data_access import calendar_publisher

logger = logging.getLogger(__name__)


def _fecha_o_none(valor: Optional[str]) -> Optional[str]:
    """La fecha de una lectura, o None si lo que hay guardado no es una fecha.

    Con un Excel cuyas cabeceras son «dia 1», «dia 2», el parser guarda la
    etiqueta de la columna («date_1», «date_2») en lugar de una fecha. La nube
    rechazaba eso con un 500 y la sincronización quedaba atascada. Se envía
    vacía: una lectura sin fecha es válida, el modelo de celo solo usa el orden.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    try:
        datetime.fromisoformat(texto)
    except ValueError:
        return None
    return texto


def _sin_ids_vacios(item: Dict[str, Any]) -> Dict[str, Any]:
    """Quita los `*_cloud_id` que no existen: la nube los trata como «no indicado»."""
    return {k: v for k, v in item.items() if not (k.endswith("_cloud_id") and v is None)}


# Fragmento del motivo con el que la nube omite lo que la persona no puede escribir
# (api/sync.py del backend privado: «sin permiso sobre la granja…»).
_SIN_PERMISO = "sin permiso"


class SyncService:
    """
    Handles bidirectional sync between the local Edge database
    and the remote SHEEPCARE Cloud database.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        cloud_url: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        self._db = db_manager or DatabaseManager()
        self._token: Optional[str] = None

        # Load cloud config from local DB
        config = self._db.get_cloud_config()
        self.cloud_url = cloud_url or (config["cloud_url"] if config else "")
        self.email = email or (config["email"] if config else "")
        self.password = password or (config["password"] if config else "")
        self.client_id = config["client_id"] if config else 0

        self._online: Optional[bool] = None

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------
    @property
    def is_online(self) -> bool:
        if self._online is None:
            self._online = self.check_cloud_connectivity()
        return self._online

    @property
    def is_configured(self) -> bool:
        """Returns True if cloud credentials are configured."""
        return bool(self.cloud_url and self.email and self.password)

    def check_cloud_connectivity(self, timeout: int = 5) -> bool:
        """Check if the configured cloud URL is reachable (pings /api/health)."""
        if not self.cloud_url:
            return False
        try:
            url = f"{self.cloud_url.rstrip('/')}/api/health"
            resp = requests.get(url, timeout=timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def _ensure_token(self) -> Optional[str]:
        """Get or refresh JWT token from cloud."""
        if self._token:
            return self._token
        return self._login()

    def _login(self) -> Optional[str]:
        """Authenticate with cloud and get JWT token."""
        if not self.is_configured:
            return None
        base = self.cloud_url.rstrip("/")
        try:
            # 1. Login contra el GateKeeper de la nube (email como username)
            resp = requests.post(
                f"{base}/gatekeeper/api/login/",
                json={"username": self.email, "password": self.password},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"GateKeeper login failed: {resp.status_code}")
                return None
            access = resp.json().get("access")
            if not access:
                logger.warning("GateKeeper login: respuesta sin 'access'")
                return None

            # 2. El client_id de sync es el id del usuario en SheepCare Cloud
            me = requests.get(
                f"{base}/api/auth/me",
                headers={"Authorization": f"Bearer {access}"},
                timeout=10,
            )
            if me.status_code != 200:
                logger.warning(
                    f"Usuario sin alta en SheepCare Cloud (/api/auth/me {me.status_code})"
                )
                return None
            self.client_id = me.json()["id"]
            self._token = access
            return self._token
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.error(f"Cloud login error: {e}")
            return None

    def _headers(self) -> dict:
        token = self._ensure_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if self.email:
            # Distingue esta instalación: dos equipos de la misma persona, o una
            # reinstalación, empiezan los dos en «granja 1, animal 1…» y sin esto
            # se pisarían en la nube.
            headers["X-Installation-Id"] = self._db.get_installation_id(self.email)
        return headers

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def configure(self, cloud_url: str, email: str, password: str) -> None:
        """Save cloud credentials locally and attempt login."""
        self.cloud_url = cloud_url
        self.email = email
        self.password = password
        self._token = None  # Force re-login
        self._db.save_cloud_config(email, password, cloud_url)

    def clear_config(self) -> None:
        """Remove cloud credentials."""
        self.cloud_url = ""
        self.email = ""
        self.password = ""
        self._token = None
        self.client_id = 0
        self._db.clear_cloud_config()

    # ------------------------------------------------------------------
    # Push: Edge → Cloud
    # ------------------------------------------------------------------
    # Resultados de leche por petición. La nube guarda cada muestra con su propia
    # consulta: enviar miles de golpe agotaría el tiempo de espera (30 s), y como
    # lo ya guardado se confirma por lotes, un fallo a medias no pierde nada.
    MILK_RESULTS_PER_PUSH = 500

    def sync_to_cloud(self) -> Dict[str, Any]:
        """
        Push unsynced local data to the cloud.
        Returns dict with success, synced_count, and optional error.
        """
        if not self.is_configured:
            return {
                "success": False,
                "synced_count": 0,
                "error": "Cloud not configured",
            }
        if not self.check_cloud_connectivity():
            self._online = False
            return {"success": False, "synced_count": 0, "error": "No internet"}

        token = self._ensure_token()
        if not token:
            return {
                "success": False,
                "synced_count": 0,
                "error": "Authentication failed",
            }

        # Gather unsynced data
        farms = self._db.get_unsynced_farms_to_cloud()
        animals = self._db.get_unsynced_animals_to_cloud()
        readings = self._db.get_unsynced_readings_to_cloud()
        uploads = self._db.get_unsynced_uploads_to_cloud()
        results = self._db.get_unsynced_results()
        milk_uploads = self._db.get_unsynced_milk_uploads_to_cloud()
        milk_results = self._db.get_unsynced_milk_results_to_cloud()

        if not any([farms, animals, readings, uploads, results, milk_uploads, milk_results]):
            self._db.update_cloud_sync_time()
            self._db.log_sync("success")
            return {"success": True, "synced_count": 0}

        # Build payload
        payload = {
            "farms": [
                {
                    "origin_id": f["id"],
                    "name": f["name"],
                    "location": f["location"],
                    "created_at": f["created_at"],
                }
                for f in farms
            ],
            "animals": [
                {
                    "origin_id": a["id"],
                    "farm_origin_id": a["farm_id"],
                    "farm_cloud_id": a["farm_cloud_id"],
                    "external_tag": a["external_tag"],
                    "name": a["name"],
                    "created_at": a["created_at"],
                }
                for a in animals
            ],
            "readings": [
                {
                    "origin_id": r["id"],
                    "animal_origin_id": r["animal_id"],
                    "animal_cloud_id": r["animal_cloud_id"],
                    "reading_date": _fecha_o_none(r["reading_date"]),
                    "value": r["value"],
                    "source_file": r.get("source_file", ""),
                }
                for r in readings
            ],
            "uploads": [
                {
                    "origin_id": u["id"],
                    "farm_origin_id": u["farm_id"],
                    "farm_cloud_id": u["farm_cloud_id"],
                    "filename": u["filename"],
                    "upload_date": u["upload_date"],
                    "total_animals": u["total_animals"],
                    "celo_count": u["celo_count"],
                    "no_celo_count": u["no_celo_count"],
                }
                for u in uploads
            ],
            "results": [
                {
                    "origin_id": r["id"],
                    "animal_origin_id": r["animal_id"],
                    "animal_cloud_id": r["animal_cloud_id"],
                    "upload_origin_id": r["upload_id"],
                    "upload_cloud_id": r["upload_cloud_id"],
                    "result": r["result"],
                    "confidence": r["confidence"],
                    "probability": r["probability"],
                    "created_at": r["created_at"],
                }
                for r in results
            ],
            "milk_uploads": [
                {
                    "origin_id": u["id"],
                    "farm_origin_id": u["farm_id"],
                    # Una granja que vino de la nube se identifica por su id allí
                    "farm_cloud_id": u["farm_cloud_id"],
                    "filename": u["filename"],
                    "upload_date": u["upload_date"],
                    "total_samples": u["total_samples"],
                    "lower_count": u["lower_count"],
                    "upper_count": u["upper_count"],
                }
                for u in milk_uploads
            ],
        }

        # Remove empty lists. Un `*_cloud_id` solo viaja si el padre ya existe en la
        # nube; si es nuevo, la nube lo resuelve con el mapeo de esta misma petición.
        payload = {k: [_sin_ids_vacios(x) for x in v] for k, v in payload.items() if v}

        # Primero todo salvo los resultados de leche, y después estos por lotes: sus
        # subidas ya existen en la nube (o se omiten con su motivo).
        lotes = [payload] if payload else []
        n = self.MILK_RESULTS_PER_PUSH
        for i in range(0, len(milk_results), n):
            lotes.append({"milk_results": [self._milk_result_payload(r) for r in milk_results[i:i + n]]})

        synced_count = 0
        omitidos: List[dict] = []
        apartados = 0
        for lote in lotes:
            res = self._post_push(lote)
            if not res["ok"]:
                self._db.log_sync("error", res["error"])
                return {"success": False, "synced_count": synced_count, "error": res["error"]}
            synced_count += self._apply_mappings(res["mappings"])
            for error in res["errors"]:
                if self._apartar_si_sin_permiso(error):
                    apartados += 1
                else:
                    omitidos.append(error)

        self._db.update_cloud_sync_time()
        self._db.log_sync("success")
        out: Dict[str, Any] = {"success": True, "synced_count": synced_count}
        if omitidos:
            # No se marcan como sincronizados: se reintentan en la próxima vuelta
            out["errors"] = omitidos
        if apartados:
            # Rechazados por falta de permiso: no se reintentan (ver sync_blocked)
            out["blocked_count"] = apartados
        return out

    def _apartar_si_sin_permiso(self, error: Dict[str, Any]) -> bool:
        """Aparta un registro que la nube rechazó por falta de permiso.

        Reintentarlo no lo arregla: o la persona perdió la granja (y entonces llega
        en `removed`) o no tiene derecho a escribir en ella. Se guarda en
        `sync_blocked` y deja de enviarse; el dato local no se toca. Los demás
        errores se siguen reintentando. Devuelve si lo apartó.
        """
        detalle = str(error.get("detail") or "")
        if _SIN_PERMISO not in detalle.lower():
            return False
        tabla, origin_id = error.get("table"), error.get("origin_id")
        if not tabla or origin_id is None:
            return False
        return self._db.block_record(tabla, origin_id, detalle)

    @staticmethod
    def _milk_result_payload(r: Dict[str, Any]) -> Dict[str, Any]:
        return _sin_ids_vacios({
            "origin_id": r["id"],
            "upload_origin_id": r["upload_id"],
            "upload_cloud_id": r.get("upload_cloud_id"),
            "sample_id": r["sample_id"],
            "result": r["result"],
            "created_at": r["created_at"],
        })

    def _post_push(self, payload: dict) -> Dict[str, Any]:
        """POST /api/sync/push. Un 401 renueva el token UNA vez y repite."""
        url = f"{self.cloud_url.rstrip('/')}/api/sync/push"
        resp = None
        for intento in (1, 2):
            try:
                resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)
            except requests.RequestException as e:
                return {"ok": False, "error": str(e)}
            if resp.status_code == 401 and intento == 1:
                self._token = None
                continue
            break
        if resp.status_code != 200:
            return {
                "ok": False,
                "error": f"Cloud API error: {resp.status_code} - {resp.text[:200]}",
            }
        data = resp.json()
        errors = data.get("errors", [])
        for e in errors:
            logger.warning(
                "Sync push: la nube omite %s.origin_id=%s: %s",
                e.get("table"), e.get("origin_id"), e.get("detail"),
            )
        return {"ok": True, "mappings": data.get("mappings", []), "errors": errors}

    def _apply_mappings(self, mappings: List[dict]) -> int:
        """Guarda en la base local el id de la nube de cada registro aceptado."""
        synced = 0
        for mapping in mappings:
            table = mapping["table"]
            origin_id = mapping["origin_id"]
            cloud_id = mapping["cloud_id"]

            if table == "farms":
                self._db.mark_farm_synced(origin_id, cloud_id)
            elif table == "animals":
                self._db.mark_animal_synced(origin_id, cloud_id)
            elif table == "uploads":
                self._db.mark_upload_synced(origin_id, cloud_id)
            elif table == "animal_readings":
                self._db.mark_reading_synced(origin_id, cloud_id)
            elif table == "detection_results":
                self._db.mark_result_synced(origin_id)
            elif table == "milk_quality_uploads":
                self._db.mark_milk_upload_synced(origin_id, cloud_id)
            elif table == "milk_quality_results":
                self._db.mark_milk_result_synced(origin_id, cloud_id)

            synced += 1
        return synced

    # ------------------------------------------------------------------
    # Pull: Cloud → Edge
    # ------------------------------------------------------------------
    def pull_from_cloud(self, _retried: bool = False) -> Dict[str, Any]:
        """
        Pull data created on Cloud (origin='cloud') that hasn't been synced yet.
        Returns dict with pulled_count and any error.
        """
        if not self.is_configured:
            return {
                "success": False,
                "pulled_count": 0,
                "error": "Cloud not configured",
            }
        if not self.check_cloud_connectivity():
            return {"success": False, "pulled_count": 0, "error": "No internet"}

        token = self._ensure_token()
        if not token:
            return {
                "success": False,
                "pulled_count": 0,
                "error": "Authentication failed",
            }

        try:
            url = f"{self.cloud_url.rstrip('/')}/api/sync/pull"
            resp = requests.get(url, headers=self._headers(), timeout=30)

            if resp.status_code == 401 and not _retried:
                self._token = None
                return self.pull_from_cloud(_retried=True)

            if resp.status_code != 200:
                return {
                    "success": False,
                    "pulled_count": 0,
                    "error": f"Cloud API error: {resp.status_code}",
                }

            data = resp.json()
            total_pulled = 0
            confirmed_ids = []  # (table, id) tuples to confirm
            nuevas_subidas = []  # ("estrus"|"milk", id local) de subidas insertadas ahora

            # Granjas que la persona ya no ve (se dejó de compartir, cambió la
            # propietaria o se borró). Se OCULTAN, no se borran: lo ya descargado no se
            # puede «des-entregar», y si vuelve a compartirse baja otra vez con su
            # historial. Se confirma también lo que aquí no existe: mientras no se
            # confirme, la nube lo repite en cada pull.
            quitadas = [
                r["cloud_id"] for r in data.get("removed", [])
                if r.get("table") == "farms" and r.get("cloud_id") is not None
            ]
            if quitadas:
                self._db.hide_farms_by_cloud_id(quitadas)
                confirmed_ids.extend(("removed", cid) for cid in quitadas)

            # Process farms
            for farm in data.get("farms", []):
                if self._reconocer_propio("farms", farm):
                    # Granja creada por este Edge que vuelve como padre: si estaba
                    # oculta y se ha vuelto a compartir, se reactiva.
                    self._db.mark_farm_visible(farm["id"], farm.get("access"))
                    confirmed_ids.append(("farms", farm["id"]))
                    continue
                new_id = self._guardar(
                    "farms", farm,
                    lambda: self._db.upsert_farm_from_cloud(
                        farm["id"],
                        farm["name"],
                        farm.get("location", ""),
                        farm["created_at"],
                        farm.get("latitude"),
                        farm.get("longitude"),
                        farm.get("access"),
                    ),
                )
                if new_id:
                    confirmed_ids.append(("farms", farm["id"]))
                    total_pulled += 1

            # Process animals
            for animal in data.get("animals", []):
                if self._reconocer_propio("animals", animal):
                    confirmed_ids.append(("animals", animal["id"]))
                    continue
                # Find the local farm_id matching the cloud farm's cloud_id
                farm_id = self._resolve_cloud_farm_id(animal["farm_id"])
                if farm_id:
                    new_id = self._guardar(
                        "animals", animal,
                        lambda: self._db.upsert_animal_from_cloud(
                            farm_id,
                            animal["id"],
                            animal["external_tag"],
                            animal["name"],
                            animal["created_at"],
                        ),
                    )
                    if new_id:
                        confirmed_ids.append(("animals", animal["id"]))
                        total_pulled += 1

            # Process uploads
            for upload in data.get("uploads", []):
                if self._reconocer_propio("uploads", upload):
                    confirmed_ids.append(("uploads", upload["id"]))
                    continue
                farm_id = self._resolve_cloud_farm_id(upload["farm_id"])
                if farm_id:
                    existia = self._existe_de_la_nube("uploads", upload["id"])
                    new_id = self._guardar(
                        "uploads", upload,
                        lambda: self._db.upsert_upload_from_cloud(
                            farm_id,
                            upload["id"],
                            upload["filename"],
                            upload["upload_date"],
                            upload["total_animals"],
                            upload["celo_count"],
                            upload["no_celo_count"],
                        ),
                    )
                    if new_id:
                        confirmed_ids.append(("uploads", upload["id"]))
                        total_pulled += 1
                        if not existia:
                            nuevas_subidas.append(("estrus", new_id))

            # Process readings
            for reading in data.get("readings", []):
                # Puede venir sin fecha (el Excel de celo ya no la trae): entonces la
                # sitúan su orden y su subida, que llega en este mismo pull.
                animal_id = self._resolve_cloud_animal_id(reading["animal_id"])
                if animal_id:
                    upload_local = (
                        self._resolve_cloud_upload_id(reading["upload_id"])
                        if reading.get("upload_id")
                        else None
                    )
                    new_id = self._db.upsert_reading_from_cloud(
                        animal_id,
                        reading["id"],
                        reading.get("reading_date"),
                        reading["value"],
                        reading.get("source_file", ""),
                        reading.get("reading_order"),
                        upload_local,
                    )
                    if new_id:
                        confirmed_ids.append(("animal_readings", reading["id"]))
                        total_pulled += 1

            # Process results
            for result in data.get("results", []):
                animal_id = self._resolve_cloud_animal_id(result["animal_id"])
                upload_id = self._resolve_cloud_upload_id(result["upload_id"])
                if animal_id and upload_id:
                    new_id = self._db.upsert_result_from_cloud(
                        animal_id,
                        upload_id,
                        result["id"],
                        result["result"],
                        result["confidence"],
                        result["probability"],
                        result["created_at"],
                    )
                    if new_id:
                        confirmed_ids.append(("detection_results", result["id"]))
                        total_pulled += 1

            # Process milk uploads (depend on farms)
            for mu in data.get("milk_uploads", []):
                if self._reconocer_propio("milk_quality_uploads", mu):
                    confirmed_ids.append(("milk_quality_uploads", mu["id"]))
                    continue
                farm_id = self._resolve_cloud_farm_id(mu["farm_id"])
                if farm_id:
                    existia = self._existe_de_la_nube("milk_quality_uploads", mu["id"])
                    new_id = self._guardar(
                        "milk_quality_uploads", mu,
                        lambda: self._db.upsert_milk_upload_from_cloud(
                            farm_id,
                            mu["id"],
                            mu["filename"],
                            mu["upload_date"],
                            mu.get("total_samples", 0),
                            mu.get("lower_count", 0),
                            mu.get("upper_count", 0),
                        ),
                    )
                    if new_id:
                        confirmed_ids.append(("milk_quality_uploads", mu["id"]))
                        total_pulled += 1
                        if not existia:
                            nuevas_subidas.append(("milk", new_id))

            # Process milk results (depend on milk uploads). Sin animales: la muestra
            # se identifica por su sample_id.
            for mr in data.get("milk_results", []):
                upload_id = self._resolve_cloud_milk_upload_id(mr["upload_id"])
                if upload_id:
                    new_id = self._db.upsert_milk_result_from_cloud(
                        upload_id,
                        mr["id"],
                        mr["sample_id"],
                        mr["result"],
                        mr["created_at"],
                    )
                    if new_id:
                        confirmed_ids.append(("milk_quality_results", mr["id"]))
                        total_pulled += 1

            # Confirm sync (tell cloud we received the data)
            if confirmed_ids:
                self._confirm_sync(confirmed_ids)

            self._db.update_cloud_sync_time()
            self._db.log_sync("success")

            # Lo recién bajado también va al Farm Calendar local, con su fecha
            # original. Después de guardar y confirmar, y sin poder afectarlos.
            publicadas = 0
            try:
                publicadas = calendar_publisher.publicar_nuevas(self._db, nuevas_subidas)
            except Exception:  # noqa: BLE001
                logger.exception("Pull: error publicando en el Farm Calendar local")
            return {
                "success": True,
                "pulled_count": total_pulled,
                "published_count": publicadas,
                "removed_count": len(quitadas),
            }

        except requests.RequestException as e:
            return {"success": False, "pulled_count": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _resolve_cloud_farm_id(self, cloud_farm_id: int) -> Optional[int]:
        """Find local farm id by cloud_id."""
        cursor = self._db.connection.cursor()
        cursor.execute("SELECT id FROM farms WHERE cloud_id = ?", (cloud_farm_id,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def _resolve_cloud_animal_id(self, cloud_animal_id: int) -> Optional[int]:
        cursor = self._db.connection.cursor()
        cursor.execute("SELECT id FROM animals WHERE cloud_id = ?", (cloud_animal_id,))
        row = cursor.fetchone()
        return row["id"] if row else None

    def _resolve_cloud_upload_id(self, cloud_upload_id: int) -> Optional[int]:
        cursor = self._db.connection.cursor()
        cursor.execute("SELECT id FROM uploads WHERE cloud_id = ?", (cloud_upload_id,))
        row = cursor.fetchone()
        return row["id"] if row else None

    # Tablas cuyas filas pueden volver al Edge que las creó, como padre de algo nuevo
    _TABLAS_PADRE = {"farms", "animals", "uploads", "milk_quality_uploads"}

    def _reconocer_propio(self, tabla: str, item: Dict[str, Any]) -> bool:
        """¿Es este registro algo que creó ESTA instalación y que vuelve como padre?

        La nube devuelve un padre cuando alguien (la web, otro equipo, otra
        persona con la granja compartida) le ha colgado algo nuevo. Si lo creó
        este Edge llega con `origin: "edge"` y su `origin_id` (el id local), para
        que lo reconozca en lugar de insertarlo otra vez: sin esto una granja se
        duplicaba y un animal rompía el pull con un UNIQUE.

        Si existe, se enlaza con su id de la nube (sin tocar nada más) y no se
        vuelve a crear. Si ya no existe en local, se trata como un registro nuevo.
        """
        if tabla not in self._TABLAS_PADRE:
            return False
        if item.get("origin") != "edge" or not item.get("origin_id"):
            return False
        cursor = self._db.connection.cursor()
        cursor.execute(f"SELECT id FROM {tabla} WHERE id = ?", (item["origin_id"],))
        if cursor.fetchone() is None:
            return False
        cursor.execute(
            f"UPDATE {tabla} SET cloud_id = COALESCE(cloud_id, ?), "
            "synced_at = COALESCE(synced_at, datetime('now')) WHERE id = ?",
            (item["id"], item["origin_id"]),
        )
        self._db.connection.commit()
        return True

    @staticmethod
    def _guardar(tabla: str, item: Dict[str, Any], accion) -> Optional[int]:
        """Guarda un registro de la nube; si choca con algo local, lo omite.

        Un registro que no se puede guardar (p. ej. un animal con la misma etiqueta
        que otro ya creado aquí) no debe tumbar el pull entero: se omite, no se
        confirma y se avisa. Antes la excepción cortaba el pull y, como la
        sincronización automática lo reintenta, se repetía para siempre.
        """
        try:
            return accion()
        except sqlite3.IntegrityError as e:
            logger.warning(
                "Pull: se omite %s %s de la nube, choca con un dato local: %s",
                tabla, item.get("id"), e,
            )
            return None

    def _existe_de_la_nube(self, tabla: str, cloud_id: int) -> bool:
        """¿Ya está guardado aquí este registro bajado de la nube?"""
        cursor = self._db.connection.cursor()
        cursor.execute(
            f"SELECT 1 FROM {tabla} WHERE cloud_id = ? AND origin = 'cloud'", (cloud_id,)
        )
        return cursor.fetchone() is not None

    def _resolve_cloud_milk_upload_id(self, cloud_upload_id: int) -> Optional[int]:
        cursor = self._db.connection.cursor()
        cursor.execute(
            "SELECT id FROM milk_quality_uploads WHERE cloud_id = ?", (cloud_upload_id,)
        )
        row = cursor.fetchone()
        return row["id"] if row else None

    def _confirm_sync(self, items: List[tuple]) -> None:
        """Tell cloud which records were successfully synced to Edge."""
        try:
            url = f"{self.cloud_url.rstrip('/')}/api/sync/confirm-sync"
            # Group by table
            from collections import defaultdict

            grouped = defaultdict(list)
            for table, record_id in items:
                grouped[table].append(record_id)

            for table, record_ids in grouped.items():
                resp = requests.post(
                    url,
                    params={"table": table},
                    json={"record_ids": record_ids},
                    headers=self._headers(),
                    timeout=10,
                )
                if resp.status_code != 200:
                    logger.warning(
                        f"confirm-sync {table} failed: {resp.status_code}"
                    )
        except requests.RequestException:
            pass  # Non-critical
