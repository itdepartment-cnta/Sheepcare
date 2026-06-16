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
from typing import Optional, Dict, Any, List
from ..data_access.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


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
        try:
            url = f"{self.cloud_url.rstrip('/')}/api/auth/login"
            resp = requests.post(
                url,
                json={
                    "email": self.email,
                    "password": self.password,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._token = data["access_token"]
                self.client_id = data["client_id"]
                return self._token
            logger.warning(f"Cloud login failed: {resp.status_code}")
            return None
        except requests.RequestException as e:
            logger.error(f"Cloud login error: {e}")
            return None

    def _headers(self) -> dict:
        token = self._ensure_token()
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
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

        if not any([farms, animals, readings, uploads, results]):
            self._db.update_cloud_sync_time()
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
                    "reading_date": r["reading_date"],
                    "value": r["value"],
                    "source_file": r.get("source_file", ""),
                }
                for r in readings
            ],
            "uploads": [
                {
                    "origin_id": u["id"],
                    "farm_origin_id": u["farm_id"],
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
                    "upload_origin_id": r["upload_id"],
                    "result": r["result"],
                    "confidence": r["confidence"],
                    "probability": r["probability"],
                    "created_at": r["created_at"],
                }
                for r in results
            ],
        }

        # Remove empty lists
        payload = {k: v for k, v in payload.items() if v}

        try:
            url = f"{self.cloud_url.rstrip('/')}/api/sync/push"
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=30)

            if resp.status_code == 401:
                # Token expired, try re-login
                self._token = None
                return self.sync_to_cloud()

            if resp.status_code == 200:
                data = resp.json()
                mappings = data.get("mappings", [])

                # Update local records with cloud IDs
                synced_count = 0
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

                    synced_count += 1

                self._db.update_cloud_sync_time()
                self._db.log_sync("success")
                return {"success": True, "synced_count": synced_count}

            error_msg = f"Cloud API error: {resp.status_code} - {resp.text[:200]}"
            self._db.log_sync("error", error_msg)
            return {"success": False, "synced_count": 0, "error": error_msg}

        except requests.RequestException as e:
            self._db.log_sync("error", str(e))
            return {"success": False, "synced_count": 0, "error": str(e)}

    # ------------------------------------------------------------------
    # Pull: Cloud → Edge
    # ------------------------------------------------------------------
    def pull_from_cloud(self) -> Dict[str, Any]:
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

            if resp.status_code == 401:
                self._token = None
                return self.pull_from_cloud()

            if resp.status_code != 200:
                return {
                    "success": False,
                    "pulled_count": 0,
                    "error": f"Cloud API error: {resp.status_code}",
                }

            data = resp.json()
            total_pulled = 0
            confirmed_ids = []  # (table, id) tuples to confirm

            # Process farms
            for farm in data.get("farms", []):
                new_id = self._db.upsert_farm_from_cloud(
                    farm["id"],
                    farm["name"],
                    farm.get("location", ""),
                    farm["created_at"],
                )
                if new_id:
                    confirmed_ids.append(("farms", farm["id"]))
                    total_pulled += 1

            # Process animals
            for animal in data.get("animals", []):
                # Find the local farm_id matching the cloud farm's cloud_id
                farm_id = self._resolve_cloud_farm_id(animal["farm_id"])
                if farm_id:
                    new_id = self._db.upsert_animal_from_cloud(
                        farm_id,
                        animal["id"],
                        animal["external_tag"],
                        animal["name"],
                        animal["created_at"],
                    )
                    if new_id:
                        confirmed_ids.append(("animals", animal["id"]))
                        total_pulled += 1

            # Process uploads
            for upload in data.get("uploads", []):
                farm_id = self._resolve_cloud_farm_id(upload["farm_id"])
                if farm_id:
                    new_id = self._db.upsert_upload_from_cloud(
                        farm_id,
                        upload["id"],
                        upload["filename"],
                        upload["upload_date"],
                        upload["total_animals"],
                        upload["celo_count"],
                        upload["no_celo_count"],
                    )
                    if new_id:
                        confirmed_ids.append(("uploads", upload["id"]))
                        total_pulled += 1

            # Process readings
            for reading in data.get("readings", []):
                animal_id = self._resolve_cloud_animal_id(reading["animal_id"])
                if animal_id:
                    new_id = self._db.upsert_reading_from_cloud(
                        animal_id,
                        reading["id"],
                        reading["reading_date"],
                        reading["value"],
                        reading.get("source_file", ""),
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

            # Confirm sync (tell cloud we received the data)
            if confirmed_ids:
                self._confirm_sync(confirmed_ids)

            self._db.update_cloud_sync_time()
            return {"success": True, "pulled_count": total_pulled}

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
                requests.post(
                    url,
                    params={"table": table},
                    json={"record_ids": record_ids},
                    headers=self._headers(),
                    timeout=10,
                )
        except requests.RequestException:
            pass  # Non-critical
