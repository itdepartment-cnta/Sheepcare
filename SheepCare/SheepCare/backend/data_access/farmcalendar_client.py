"""
FarmCalendarClient - REST client for OpenAgri Farm Calendar API.
Posts detection results as Observations visible in the calendar.

The Farm Calendar URL can be configured via the FARMCALENDAR_API_URL
environment variable, or defaults to http://localhost:8002/api/v1/.
"""

import os
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime


class FarmCalendarClient:
    """
    Client for the OpenAgri Digital Farm Calendar REST API.

    The Farm Calendar is a Django service (deployed via Docker) at:
    - Web UI: http://localhost:8002/
    - REST API: http://localhost:8002/api/v1/

    Uses JSON-LD format as specified in:
    https://github.com/agstack/OpenAgri-FarmCalendar
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        jwt_signing_key: Optional[str] = None,
    ) -> None:
        self.api_url = (
            api_url
            or os.environ.get(
                "FARMCALENDAR_API_URL",
                "http://localhost:8002/api/v1/",
            )
        ).rstrip("/") + "/"
        self._session = requests.Session()
        self._authenticated = False
        # Secreto compartido con Farm Calendar, generado y distribuido por el
        # launcher (ver installer/launcher_app.py) — antes emitido por
        # GateKeeper como fuente unica de verdad. El fallback solo cubre
        # desarrollo local sin el launcher (docker-compose, `uvicorn --reload`).
        self._jwt_signing_key = jwt_signing_key or os.environ.get(
            "FARMCALENDAR_JWT_SECRET", "dev-only-insecure-secret"
        )

    # ------------------------------------------------------------------
    # JWT Authentication (Farm Calendar uses JWT, not session login)
    # ------------------------------------------------------------------
    def _ensure_auth(self) -> None:
        """Set JWT Bearer token on the session if not already done."""
        if self._authenticated:
            return
        try:
            import jwt as pyjwt
            from uuid import uuid4
            from datetime import datetime, timedelta, timezone

            payload = {
                "user_id": "sheepcare",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "token_type": "access",
                "jti": str(uuid4()),
            }
            token = pyjwt.encode(payload, self._jwt_signing_key, algorithm="HS256")
            self._session.headers.update({"Authorization": f"Bearer {token}"})
            self._authenticated = True
        except ImportError:
            pass

    @property
    def auth_cookies(self) -> dict:
        """Get session cookies for the iframe embed."""
        return self._session.cookies.get_dict()

    # ------------------------------------------------------------------
    # Activity Types
    # ------------------------------------------------------------------
    ESTRUS_ACTIVITY_TYPE = {
        "name": "Estrus Detection",
        "description": "Automated estrus detection from resistance measurements",
        "background_color": "#E28474",
        "border_color": "#C0503A",
        "text_color": "#FFFFFF",
    }

    MILK_QUALITY_ACTIVITY_TYPE = {
        "name": "Milk Quality",
        "description": "Automated milk quality (SCC) classification from spectral readings",
        "background_color": "#8ECAE6",
        "border_color": "#2E7D9A",
        "text_color": "#FFFFFF",
    }

    def _get_or_create_activity_type(self, activity_type_def: Dict[str, Any]) -> Optional[str]:
        """
        Get or create an activity type by its 'name'.
        Returns the @id URN of the activity type, or None on failure.
        """
        self._ensure_auth()
        try:
            # List existing
            resp = self._session.get(
                f"{self.api_url}FarmCalendarActivityTypes/",
                params={"format": "json"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                activities = data.get("@graph", []) if "@graph" in data else data
                for activity in activities:
                    if activity.get("name") == activity_type_def["name"]:
                        return activity.get("@id")

            # Not found, create it
            create_resp = self._session.post(
                f"{self.api_url}FarmCalendarActivityTypes/",
                json=activity_type_def,
                params={"format": "json"},
                timeout=10,
            )
            if create_resp.status_code in (200, 201):
                created = create_resp.json()
                return created.get("@id")
        except requests.RequestException:
            pass
        return None

    def get_or_create_activity_type(self) -> Optional[str]:
        """
        Get or create the 'Estrus Detection' activity type.
        Returns the @id URN of the activity type, or None on failure.
        """
        return self._get_or_create_activity_type(self.ESTRUS_ACTIVITY_TYPE)

    def get_or_create_milk_quality_activity_type(self) -> Optional[str]:
        """
        Get or create the 'Milk Quality' activity type.
        Returns the @id URN of the activity type, or None on failure.
        """
        return self._get_or_create_activity_type(self.MILK_QUALITY_ACTIVITY_TYPE)

    # ------------------------------------------------------------------
    # Post Observation (Estrus Detection Event)
    # ------------------------------------------------------------------
    def post_estrus_detection(
        self,
        farm_name: str,
        celo_count: int,
        no_celo_count: int,
        filename: str,
        upload_date: Optional[str] = None,
        details_text: Optional[str] = None,
        animal_details: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Post an estrus detection event as an Observation in the Farm Calendar.

        This creates a calendar entry visible in the OpenAgri web UI on the
        upload date, showing the summary of detected animals.

        Args:
            farm_name: Name of the farm
            celo_count: Number of animals in estrus
            no_celo_count: Number of animals not in estrus
            filename: Original uploaded file name
            upload_date: ISO datetime string (defaults to now)
            details_text: Optional detailed description
            animal_details: Optional list of dicts with animal_id, result, confidence

        Returns:
            True if successfully posted
        """
        self._ensure_auth()
        if not upload_date:
            upload_date = datetime.now().isoformat()

        if not details_text:
            summary_parts = []
            if celo_count > 0:
                summary_parts.append(f"🟢 Celo: {celo_count}")
            if no_celo_count > 0:
                summary_parts.append(f"🔴 No celo: {no_celo_count}")

            # Build per-animal list
            if animal_details:
                celo_animals = [a for a in animal_details if a.get("result") == "Celo"]
                no_celo_animals = [
                    a for a in animal_details if a.get("result") == "No celo"
                ]
                lines = [f"Archivo: {filename}"]
                lines.extend(summary_parts)
                lines.append("")
                if celo_animals:
                    lines.append("🟢 CELO:")
                    for a in celo_animals:
                        lines.append(
                            f"  {a['animal_id']} "
                            f"(confianza: {a.get('confidence', 0)*100:.0f}%)"
                        )
                if no_celo_animals:
                    lines.append("🔴 NO CELO:")
                    for a in no_celo_animals:
                        lines.append(
                            f"  {a['animal_id']} "
                            f"(confianza: {a.get('confidence', 0)*100:.0f}%)"
                        )
                details_text = "\n".join(lines)
            else:
                details_text = f"Archivo: {filename} | {' | '.join(summary_parts)}"

        # Get or create the activity type
        activity_type_id = self.get_or_create_activity_type()

        payload: Dict[str, Any] = {
            "@type": "Observation",
            "title": f"Detección de celo — {farm_name}",
            "details": details_text,
            "phenomenonTime": upload_date,
            "observedProperty": "estrus_detection",
            "hasResult": {
                "@type": "QuantityValue",
                "unit": "count",
                "hasValue": f"Celo: {celo_count}, No celo: {no_celo_count}",
            },
            "madeBySensor": {
                "@type": "Sensor",
                "name": "SHEEPCARE Detection Engine",
            },
        }
        if activity_type_id:
            payload["activityType"] = activity_type_id

        try:
            resp = self._session.post(
                f"{self.api_url}Observations/",
                json=payload,
                params={"format": "json"},
                timeout=15,
            )
            return resp.status_code in (200, 201)
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # Post Observation (Milk Quality Event)
    # ------------------------------------------------------------------
    def post_milk_quality_detection(
        self,
        farm_name: str,
        buena_count: int,
        mala_count: int,
        filename: str,
        upload_date: Optional[str] = None,
        details_text: Optional[str] = None,
        sample_details: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        Post a milk quality (SCC) detection event as an Observation in the
        Farm Calendar, mirroring post_estrus_detection().

        Args:
            farm_name: Name of the farm
            buena_count: Number of samples classified as good quality (Lower)
            mala_count: Number of samples classified as poor quality (Upper)
            filename: Original uploaded file name
            upload_date: ISO datetime string (defaults to now)
            details_text: Optional detailed description
            sample_details: Optional list of dicts with animal_id, result
                (result is the raw "Lower"/"Upper" value stored in the DB)

        Returns:
            True if successfully posted
        """
        self._ensure_auth()
        if not upload_date:
            upload_date = datetime.now().isoformat()

        if not details_text:
            summary_parts = []
            if buena_count > 0:
                summary_parts.append(f"🟢 Buena: {buena_count}")
            if mala_count > 0:
                summary_parts.append(f"🔴 Mala: {mala_count}")

            # Build per-sample list
            if sample_details:
                buena_samples = [s for s in sample_details if s.get("result") == "Lower"]
                mala_samples = [s for s in sample_details if s.get("result") == "Upper"]
                lines = [f"Archivo: {filename}"]
                lines.extend(summary_parts)
                lines.append("")
                if buena_samples:
                    lines.append("🟢 BUENA:")
                    for s in buena_samples:
                        lines.append(f"  {s['animal_id']}")
                if mala_samples:
                    lines.append("🔴 MALA:")
                    for s in mala_samples:
                        lines.append(f"  {s['animal_id']}")
                details_text = "\n".join(lines)
            else:
                details_text = f"Archivo: {filename} | {' | '.join(summary_parts)}"

        # Get or create the activity type
        activity_type_id = self.get_or_create_milk_quality_activity_type()

        payload: Dict[str, Any] = {
            "@type": "Observation",
            "title": f"Calidad de leche — {farm_name}",
            "details": details_text,
            "phenomenonTime": upload_date,
            "observedProperty": "milk_quality_scc",
            "hasResult": {
                "@type": "QuantityValue",
                "unit": "count",
                "hasValue": f"Buena: {buena_count}, Mala: {mala_count}",
            },
            "madeBySensor": {
                "@type": "Sensor",
                "name": "SHEEPCARE Milk Quality Engine",
            },
        }
        if activity_type_id:
            payload["activityType"] = activity_type_id

        try:
            resp = self._session.post(
                f"{self.api_url}Observations/",
                json=payload,
                params={"format": "json"},
                timeout=15,
            )
            return resp.status_code in (200, 201)
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------
    # Sync Farms
    # ------------------------------------------------------------------
    def sync_farm(self, name: str, location: str = "") -> Optional[str]:
        """Create or update a Farm in FC. Returns FC @id URI or None."""
        self._ensure_auth()
        try:
            # Search by name to avoid duplicates
            resp = self._session.get(
                f"{self.api_url}Farm/?format=json",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                farms_list = (
                    data.get("@graph", [])
                    if "@graph" in data
                    else (data if isinstance(data, list) else [])
                )
                for f in farms_list:
                    if f.get("name") == name:
                        return f.get("@id")

            # Not found, create with all required fields
            payload: Dict[str, Any] = {
                "name": name,
                "description": location or f"Granja {name}",
                "administrator": "SHEEPCARE",
                "telephone": "000000000",
                "vatID": "N/A",
                "contactPerson": {
                    "firstname": "SHEEPCARE",
                    "lastname": "System",
                },
                "address": {
                    "adminUnitL1": "N/A",
                    "adminUnitL2": "N/A",
                    "addressArea": "N/A",
                    "municipality": "N/A",
                    "community": "N/A",
                    "locatorName": "N/A",
                },
            }
            resp = self._session.post(
                f"{self.api_url}Farm/?format=json",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                created = resp.json()
                return created.get("@id")
        except requests.RequestException:
            pass
        return None

    # ------------------------------------------------------------------
    # Sync FarmParcel (default parcel per farm)
    # ------------------------------------------------------------------
    def sync_parcel(self, farm_fc_uuid: str, identifier: str) -> Optional[str]:
        """Create or update a default FarmParcel. Returns FC @id URI or None."""
        self._ensure_auth()
        try:
            # Search by identifier
            resp = self._session.get(
                f"{self.api_url}FarmParcels/?format=json",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                parcels_list = (
                    data.get("@graph", [])
                    if "@graph" in data
                    else (data if isinstance(data, list) else [])
                )
                for p in parcels_list:
                    if p.get("identifier") == identifier:
                        return p.get("@id")

            # Create default parcel with all required fields
            payload: Dict[str, Any] = {
                "identifier": identifier,
                "farm": {"@type": "Farm", "@id": farm_fc_uuid},
                "parcel_type": "livestock",
                "description": "Parcela por defecto SHEEPCARE",
                "category": "livestock",
                "area": 0,
                "validFrom": "2024-01-01T00:00:00Z",
                "validTo": "2030-12-31T00:00:00Z",
                "inRegion": "N/A",
                "hasToponym": "N/A",
                "isNitroArea": False,
                "isNatura2000Area": False,
                "isPdopgArea": False,
                "isIrrigated": False,
                "isCultivatedInLevels": False,
                "isGroundSlope": False,
                "hasIrrigationFlow": 0,
                "hasGeometry": {
                    "asWKT": f"POINT({hash(identifier) % 180} {hash(identifier) % 90})"
                },
                "location": {
                    "lat": hash(identifier) % 90,
                    "long": hash(identifier) % 180,
                },
            }
            resp = self._session.post(
                f"{self.api_url}FarmParcels/?format=json",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                created = resp.json()
                return created.get("@id")
        except requests.RequestException:
            pass
        return None

    # ------------------------------------------------------------------
    # Sync Animals
    # ------------------------------------------------------------------
    def sync_animal(
        self,
        parcel_fc_uuid: str,
        external_tag: str,
        name: str = "",
    ) -> Optional[str]:
        """Create or update an animal in FC. Returns FC @id URI or None."""
        self._ensure_auth()
        try:
            # Search by nationalID (external_tag) to avoid duplicates
            resp = self._session.get(
                f"{self.api_url}FarmAnimals/?format=json",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                animals_list = (
                    data.get("@graph", [])
                    if "@graph" in data
                    else (data if isinstance(data, list) else [])
                )
                for a in animals_list:
                    if a.get("nationalID") == external_tag:
                        return a.get("@id")

            # Create with defaults: Oveja, Female, now as birthdate
            payload: Dict[str, Any] = {
                "national_id": external_tag,
                "name": name or external_tag,
                "species": "Oveja",
                "breed": "",
                "birthdate": datetime.now().isoformat(),
                "sex": 1,  # Female
                "castrated": False,
                "hasAgriParcel": {"@type": "FarmParcel", "@id": parcel_fc_uuid},
            }
            resp = self._session.post(
                f"{self.api_url}FarmAnimals/?format=json",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                created = resp.json()
                return created.get("@id")
        except requests.RequestException:
            pass
        return None

        # ------------------------------------------------------------------
        # Health check
        """Check if the Farm Calendar service is reachable."""
        try:
            resp = self._session.get(
                f"{self.api_url}FarmCalendarActivityTypes/",
                params={"format": "json"},
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
