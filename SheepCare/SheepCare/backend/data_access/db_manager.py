"""
DatabaseManager - Singleton for SQLite operations.
Extended schema for SHEEPCARE v2: farms, uploads, animal_readings, detection_results.
"""

import sqlite3
import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from .milk_migration import migrate_if_needed as migrate_milk_if_needed
from .readings_migration import migrate_if_needed as migrate_readings_if_needed


class DatabaseManager:
    """Singleton that manages the SQLite database connection and operations."""

    _instance: Optional["DatabaseManager"] = None
    _initialized: bool = False

    def __new__(cls, db_path: Optional[str] = None) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: Optional[str] = None) -> None:
        if DatabaseManager._initialized:
            return
        DatabaseManager._initialized = True

        if db_path is None:
            db_path = os.environ.get("SHEEPCARE_DB_PATH")
        if not db_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "sheepcare.db")

        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._create_tables()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _create_tables(self) -> None:
        cursor = self.connection.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS farms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                location    TEXT    NOT NULL DEFAULT '',
                created_at  DATETIME NOT NULL DEFAULT (datetime('now'))
            );

            -- Registros que la nube rechazó por falta de permiso. No se vuelven a
            -- enviar (ver get_unsynced_*): reintentarlos no los arregla. `table_name`
            -- es el nombre que usa la nube en sus errores y mapeos.
            CREATE TABLE IF NOT EXISTS sync_blocked (
                table_name TEXT NOT NULL,
                origin_id  INTEGER NOT NULL,
                reason     TEXT NOT NULL DEFAULT '',
                blocked_at DATETIME NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (table_name, origin_id)
            );

            CREATE TABLE IF NOT EXISTS animals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id      INTEGER NOT NULL,
                external_tag TEXT    NOT NULL,
                name         TEXT    NOT NULL DEFAULT '',
                created_at   DATETIME NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
                UNIQUE(farm_id, external_tag)
            );

            -- La fecha es opcional: el Excel de celo ya no la trae y rotula las columnas
            -- «dia 1», «dia 2». Entonces lo que sitúa la lectura es `reading_order`
            -- dentro de su `upload_id`, como en la nube. Bases anteriores: se migran abajo.
            CREATE TABLE IF NOT EXISTS animal_readings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id     INTEGER NOT NULL,
                reading_date  DATE,
                value         FLOAT   NOT NULL,
                source_file   TEXT    NOT NULL DEFAULT '',
                reading_order INTEGER,
                upload_id     INTEGER,
                origin        TEXT    DEFAULT 'edge',
                cloud_id      INTEGER,
                synced_at     DATETIME,
                FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE,
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS uploads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id      INTEGER NOT NULL,
                filename     TEXT    NOT NULL,
                upload_date  DATETIME NOT NULL DEFAULT (datetime('now')),
                processed_at DATETIME,
                total_animals INTEGER DEFAULT 0,
                celo_count   INTEGER DEFAULT 0,
                no_celo_count INTEGER DEFAULT 0,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS detection_results (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id    INTEGER NOT NULL,
                upload_id    INTEGER NOT NULL,
                result       TEXT    NOT NULL CHECK (result IN ('Celo', 'No celo')),
                confidence   FLOAT   NOT NULL DEFAULT 0.0,
                probability  FLOAT   NOT NULL DEFAULT 0.0,
                created_at   DATETIME NOT NULL DEFAULT (datetime('now')),
                is_synced    INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE,
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS milk_quality_uploads (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id       INTEGER NOT NULL,
                filename      TEXT    NOT NULL,
                upload_date   DATETIME NOT NULL DEFAULT (datetime('now')),
                processed_at  DATETIME,
                total_samples INTEGER DEFAULT 0,
                lower_count   INTEGER DEFAULT 0,
                upper_count   INTEGER DEFAULT 0,
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE
            );

            -- Las muestras de leche se identifican por `sample_id` (texto), no por
            -- un animal: como en la nube. Las bases anteriores se migran abajo.
            CREATE TABLE IF NOT EXISTS milk_quality_results (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id    TEXT    NOT NULL,
                upload_id    INTEGER NOT NULL,
                result       TEXT    NOT NULL CHECK (result IN ('Lower', 'Upper')),
                created_at   DATETIME NOT NULL DEFAULT (datetime('now')),
                origin       TEXT    DEFAULT 'edge',
                cloud_id     INTEGER,
                synced_at    DATETIME,
                is_synced    INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (upload_id) REFERENCES milk_quality_uploads(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sync_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                last_sync_at DATETIME NOT NULL DEFAULT (datetime('now')),
                status       TEXT    NOT NULL CHECK (status IN ('success', 'error')),
                last_error   TEXT    NOT NULL DEFAULT ''
            );

            -- Cloud sync config (stores cloud credentials for bidirectional sync)
            CREATE TABLE IF NOT EXISTS cloud_config (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    NOT NULL DEFAULT '',
                password      TEXT    NOT NULL DEFAULT '',
                cloud_url     TEXT    NOT NULL DEFAULT '',
                last_sync_at  DATETIME,
                client_id     INTEGER DEFAULT 0
            );

            -- Generic key/value settings (e.g. the user's OpenWeatherMap API key)
            CREATE TABLE IF NOT EXISTS app_settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL DEFAULT '',
                updated_at  DATETIME NOT NULL DEFAULT (datetime('now'))
            );

            -- Farm Calendar sync tracking (maps local IDs to FC UUIDs)
            CREATE TABLE IF NOT EXISTS farmcalendar_sync (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type   TEXT    NOT NULL CHECK (entity_type IN ('farm', 'parcel', 'animal')),
                local_id      INTEGER NOT NULL,
                fc_uuid       TEXT    NOT NULL,
                synced_at     DATETIME NOT NULL DEFAULT (datetime('now')),
                UNIQUE(entity_type, local_id)
            );
        """)

        # ── Migrations: add sync tracking columns to existing tables ──
        migrations = [
            ("farms", "origin", "TEXT", "'edge'"),
            ("farms", "cloud_id", "INTEGER", "NULL"),
            ("farms", "synced_at", "DATETIME", "NULL"),
            ("farms", "latitude", "REAL", "NULL"),
            ("farms", "longitude", "REAL", "NULL"),
            # Relación de la persona con la granja según la nube: owner, shared o
            # admin. NULL en una granja solo local.
            ("farms", "cloud_access", "TEXT", "NULL"),
            # 1 = la persona ya no ve esta granja en la nube (se dejó de compartir,
            # cambió la propietaria o se borró). Se oculta, no se borra.
            ("farms", "hidden", "INTEGER", "0"),
            ("animals", "origin", "TEXT", "'edge'"),
            ("animals", "cloud_id", "INTEGER", "NULL"),
            ("animals", "synced_at", "DATETIME", "NULL"),
            ("animal_readings", "origin", "TEXT", "'edge'"),
            ("animal_readings", "cloud_id", "INTEGER", "NULL"),
            ("animal_readings", "synced_at", "DATETIME", "NULL"),
            ("uploads", "origin", "TEXT", "'edge'"),
            ("uploads", "cloud_id", "INTEGER", "NULL"),
            ("uploads", "synced_at", "DATETIME", "NULL"),
            ("detection_results", "origin", "TEXT", "'edge'"),
            ("detection_results", "cloud_id", "INTEGER", "NULL"),
            ("detection_results", "synced_at", "DATETIME", "NULL"),
            ("milk_quality_uploads", "origin", "TEXT", "'edge'"),
            ("milk_quality_uploads", "cloud_id", "INTEGER", "NULL"),
            ("milk_quality_uploads", "synced_at", "DATETIME", "NULL"),
        ]
        for table, col, col_type, default in migrations:
            try:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

        self.connection.commit()

        # Bases anteriores: la leche pasa de «un animal por muestra» a `sample_id`.
        # Hace copia de seguridad y es transaccional (ver milk_migration.py).
        migrate_milk_if_needed(self.connection, self.db_path)
        # Y la fecha de las lecturas pasa a ser opcional (ver readings_migration.py).
        migrate_readings_if_needed(self.connection, self.db_path)

    # ------------------------------------------------------------------
    # Farms CRUD
    # ------------------------------------------------------------------
    def add_farm(
        self,
        name: str,
        location: str = "",
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO farms (name, location, latitude, longitude) VALUES (?, ?, ?, ?)",
            (name, location, latitude, longitude),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_farm(self, farm_id: int, include_hidden: bool = False) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM farms WHERE id = ?" + ("" if include_hidden else " AND hidden = 0"),
            (farm_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_farms(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM farms" + ("" if include_hidden else " WHERE hidden = 0") + " ORDER BY name"
        )
        return [dict(row) for row in cursor.fetchall()]

    def update_farm(
        self,
        farm_id: int,
        name: str,
        location: str,
        coords: Optional[Tuple[Optional[float], Optional[float]]] = None,
    ) -> bool:
        """Update a farm. `coords` None leaves the coordinates untouched;
        (None, None) clears them."""
        cursor = self.connection.cursor()
        if coords is None:
            cursor.execute(
                "UPDATE farms SET name = ?, location = ? WHERE id = ?",
                (name, location, farm_id),
            )
        else:
            cursor.execute(
                "UPDATE farms SET name = ?, location = ?, latitude = ?, longitude = ? WHERE id = ?",
                (name, location, coords[0], coords[1], farm_id),
            )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_farm(self, farm_id: int) -> bool:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM farms WHERE id = ?", (farm_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def farm_has_uploads(self, farm_id: int) -> bool:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM uploads WHERE farm_id = ?", (farm_id,)
        )
        row = cursor.fetchone()
        return row["cnt"] > 0 if row else False

    # ------------------------------------------------------------------
    # Animals CRUD
    # ------------------------------------------------------------------
    def add_animal(self, farm_id: int, external_tag: str, name: str = "") -> int:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO animals (farm_id, external_tag, name) VALUES (?, ?, ?)",
                (farm_id, external_tag, name),
            )
            self.connection.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Already exists for this farm - return existing
            cursor.execute(
                "SELECT id FROM animals WHERE farm_id = ? AND external_tag = ?",
                (farm_id, external_tag),
            )
            row = cursor.fetchone()
            return row["id"] if row else -1

    def get_animal(self, animal_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM animals WHERE id = ? "
            "AND farm_id NOT IN (SELECT id FROM farms WHERE hidden = 1)",
            (animal_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_animal_by_tag(self, farm_id: int, tag: str) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM animals WHERE farm_id = ? AND external_tag = ?",
            (farm_id, tag),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_animals(self, farm_id: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        if farm_id:
            cursor.execute(
                "SELECT a.*, f.name as farm_name FROM animals a JOIN farms f ON a.farm_id = f.id AND f.hidden = 0 WHERE a.farm_id = ? ORDER BY a.external_tag",
                (farm_id,),
            )
        else:
            cursor.execute(
                "SELECT a.*, f.name as farm_name FROM animals a JOIN farms f ON a.farm_id = f.id AND f.hidden = 0 ORDER BY a.external_tag"
            )
        return [dict(row) for row in cursor.fetchall()]

    def update_animal(self, animal_id: int, name: str) -> bool:
        cursor = self.connection.cursor()
        cursor.execute("UPDATE animals SET name = ? WHERE id = ?", (name, animal_id))
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_animal(self, animal_id: int) -> bool:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM animals WHERE id = ?", (animal_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Animal Readings
    # ------------------------------------------------------------------
    def save_animal_reading(
        self,
        animal_id: int,
        reading_date: Optional[str],
        value: float,
        source_file: str = "",
        reading_order: Optional[int] = None,
        upload_id: Optional[int] = None,
    ) -> int:
        """Guarda una lectura. `reading_date` es None si el Excel no traía fechas:
        entonces la sitúan `reading_order` dentro de su `upload_id`."""
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO animal_readings (animal_id, reading_date, value, source_file, "
            "reading_order, upload_id) VALUES (?, ?, ?, ?, ?, ?)",
            (animal_id, reading_date, value, source_file, reading_order, upload_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_animal_readings(self, animal_id: int) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            # Mismo orden que la nube: por la fecha de la subida si la lectura no
            # tiene la suya, y dentro de la subida por su orden.
            "SELECT r.* FROM animal_readings r "
            "LEFT JOIN uploads u ON u.id = r.upload_id "
            "WHERE r.animal_id = ? "
            "ORDER BY COALESCE(u.upload_date, r.reading_date), r.upload_id, "
            "r.reading_order, r.reading_date, r.id",
            (animal_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_animal_readings_by_date_range(
        self, animal_id: int, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM animal_readings WHERE animal_id = ? AND reading_date BETWEEN ? AND ? ORDER BY reading_date",
            (animal_id, start_date, end_date),
        )
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Uploads
    # ------------------------------------------------------------------
    def create_upload(self, farm_id: int, filename: str) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO uploads (farm_id, filename) VALUES (?, ?)",
            (farm_id, filename),
        )
        self.connection.commit()
        return cursor.lastrowid

    def finalize_upload(
        self, upload_id: int, total_animals: int, celo_count: int, no_celo_count: int
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """UPDATE uploads
               SET processed_at = datetime('now'),
                   total_animals = ?,
                   celo_count = ?,
                   no_celo_count = ?
               WHERE id = ?""",
            (total_animals, celo_count, no_celo_count, upload_id),
        )
        self.connection.commit()

    def get_upload(self, upload_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT u.*, f.name as farm_name
            FROM uploads u
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE u.id = ?
        """,
            (upload_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_uploads(self, farm_id: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        if farm_id:
            cursor.execute(
                """
                SELECT u.*, f.name as farm_name
                FROM uploads u
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                WHERE u.farm_id = ?
                ORDER BY u.upload_date DESC
            """,
                (farm_id,),
            )
        else:
            cursor.execute("""
                SELECT u.*, f.name as farm_name
                FROM uploads u
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                ORDER BY u.upload_date DESC
            """)
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Detection Results
    # ------------------------------------------------------------------
    def save_detection_result(
        self,
        animal_id: int,
        upload_id: int,
        result: str,
        confidence: float,
        probability: float,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO detection_results (animal_id, upload_id, result, confidence, probability) VALUES (?, ?, ?, ?, ?)",
            (animal_id, upload_id, result, confidence, probability),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_results(
        self,
        farm_id: Optional[int] = None,
        upload_id: Optional[int] = None,
        result_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        query = """
            SELECT dr.*, a.external_tag as animal_tag, a.name as animal_name,
                   u.filename, u.upload_date, f.name as farm_name
            FROM detection_results dr
            JOIN animals a ON dr.animal_id = a.id
            JOIN uploads u ON dr.upload_id = u.id
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE 1=1
        """
        params = []
        if farm_id:
            query += " AND u.farm_id = ?"
            params.append(farm_id)
        if upload_id:
            query += " AND dr.upload_id = ?"
            params.append(upload_id)
        if result_filter:
            query += " AND dr.result = ?"
            params.append(result_filter)
        query += " ORDER BY dr.created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_animal_results(self, animal_id: int) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT dr.*, u.filename, u.upload_date, f.name as farm_name
            FROM detection_results dr
            JOIN uploads u ON dr.upload_id = u.id
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE dr.animal_id = ?
            ORDER BY dr.created_at DESC
        """,
            (animal_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_result(
        self, farm_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        if farm_id:
            cursor.execute(
                """
                SELECT dr.*, a.external_tag as animal_tag, a.name as animal_name,
                       u.filename, u.upload_date, f.name as farm_name
                FROM detection_results dr
                JOIN animals a ON dr.animal_id = a.id
                JOIN uploads u ON dr.upload_id = u.id
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                WHERE u.farm_id = ?
                ORDER BY dr.created_at DESC LIMIT 1
            """,
                (farm_id,),
            )
        else:
            cursor.execute("""
                SELECT dr.*, a.external_tag as animal_tag, a.name as animal_name,
                       u.filename, u.upload_date, f.name as farm_name
                FROM detection_results dr
                JOIN animals a ON dr.animal_id = a.id
                JOIN uploads u ON dr.upload_id = u.id
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                ORDER BY dr.created_at DESC LIMIT 1
            """)
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Milk Quality (SCC) Uploads & Results
    # ------------------------------------------------------------------
    def create_milk_quality_upload(self, farm_id: int, filename: str) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO milk_quality_uploads (farm_id, filename) VALUES (?, ?)",
            (farm_id, filename),
        )
        self.connection.commit()
        return cursor.lastrowid

    def finalize_milk_quality_upload(
        self, upload_id: int, total_samples: int, lower_count: int, upper_count: int
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """UPDATE milk_quality_uploads
               SET processed_at = datetime('now'),
                   total_samples = ?,
                   lower_count = ?,
                   upper_count = ?
               WHERE id = ?""",
            (total_samples, lower_count, upper_count, upload_id),
        )
        self.connection.commit()

    def get_milk_quality_upload(self, upload_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT u.*, f.name as farm_name
            FROM milk_quality_uploads u
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE u.id = ?
        """,
            (upload_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_milk_quality_uploads(self, farm_id: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        if farm_id:
            cursor.execute(
                """
                SELECT u.*, f.name as farm_name
                FROM milk_quality_uploads u
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                WHERE u.farm_id = ?
                ORDER BY u.upload_date DESC
            """,
                (farm_id,),
            )
        else:
            cursor.execute("""
                SELECT u.*, f.name as farm_name
                FROM milk_quality_uploads u
                JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
                ORDER BY u.upload_date DESC
            """)
        return [dict(row) for row in cursor.fetchall()]

    def save_milk_quality_result(self, sample_id: str, upload_id: int, result: str) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO milk_quality_results (sample_id, upload_id, result) VALUES (?, ?, ?)",
            (sample_id, upload_id, result),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_milk_quality_results(
        self,
        farm_id: Optional[int] = None,
        upload_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        query = """
            SELECT mr.*, mr.sample_id as animal_tag, '' as animal_name,
                   u.filename, u.upload_date, f.name as farm_name
            FROM milk_quality_results mr
            JOIN milk_quality_uploads u ON mr.upload_id = u.id
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE 1=1
        """
        params = []
        if farm_id:
            query += " AND u.farm_id = ?"
            params.append(farm_id)
        if upload_id:
            query += " AND mr.upload_id = ?"
            params.append(upload_id)
        query += " ORDER BY mr.created_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ------------------------------------------------------------------
    # Sync tracking
    # ------------------------------------------------------------------
    def get_unsynced_results(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT dr.*, a.external_tag as animal_tag, f.name as farm_name,
                   a.cloud_id AS animal_cloud_id, u.cloud_id AS upload_cloud_id
            FROM detection_results dr
            JOIN animals a ON dr.animal_id = a.id
            JOIN uploads u ON dr.upload_id = u.id
            JOIN farms f ON u.farm_id = f.id AND f.hidden = 0
            WHERE dr.is_synced = 0
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'detection_results' AND b.origin_id = dr.id)
            ORDER BY dr.created_at ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

    def mark_result_synced(self, result_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE detection_results SET is_synced = 1 WHERE id = ?", (result_id,)
        )
        self.connection.commit()

    def log_sync(self, status: str, error: str = "") -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO sync_logs (status, last_error) VALUES (?, ?)",
            (status, error),
        )
        self.connection.commit()

    def get_last_sync(self) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM sync_logs ORDER BY last_sync_at DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # App settings (generic key/value)
    # ------------------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        cursor = self.connection.cursor()
        cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now')
        """,
            (key, value),
        )
        self.connection.commit()

    def get_installation_id(self, email: str) -> str:
        """Identificador de ESTA instalación para esa persona (`X-Installation-Id`).

        Se genera una vez y se guarda en la propia base: sobrevive a reinicios y a
        reinstalaciones (la base está fuera de la carpeta de la aplicación). Es uno
        por persona: si en el mismo equipo entra otra, necesita el suyo, porque la
        nube asocia cada identificador a una sola persona.
        """
        clave = "installation_id:" + (email or "").strip().lower()
        valor = self.get_setting(clave)
        if not valor:
            valor = str(uuid.uuid4())
            self.set_setting(clave, valor)
        return valor

    def delete_setting(self, key: str) -> None:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        self.connection.commit()

    # ------------------------------------------------------------------
    # Cloud Config (credentials for bidirectional sync)
    # ------------------------------------------------------------------
    def get_cloud_config(self) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM cloud_config WHERE id = 1")
        row = cursor.fetchone()
        return dict(row) if row else None

    def save_cloud_config(
        self, email: str, password: str, cloud_url: str, client_id: int = 0
    ) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO cloud_config (id, email, password, cloud_url, client_id)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                email = excluded.email,
                password = excluded.password,
                cloud_url = excluded.cloud_url,
                client_id = excluded.client_id
        """,
            (email, password, cloud_url, client_id),
        )
        self.connection.commit()

    def clear_cloud_config(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM cloud_config")
        self.connection.commit()

    def update_cloud_sync_time(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute("""
            INSERT INTO cloud_config (id, last_sync_at)
            VALUES (1, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                last_sync_at = datetime('now')
        """)
        self.connection.commit()

    # ------------------------------------------------------------------
    # Bidirectional Sync: Edge methods for Cloud data
    # ------------------------------------------------------------------
    def get_unsynced_to_cloud(self) -> List[Dict[str, Any]]:
        """Get all records with origin='edge' that haven't been synced to cloud."""
        cursor = self.connection.cursor()
        results = []

        # Detection results
        cursor.execute("""
            SELECT dr.*, a.external_tag as animal_tag, a.farm_id, u.farm_id as upload_farm_id
            FROM detection_results dr
            JOIN animals a ON dr.animal_id = a.id
            JOIN uploads u ON dr.upload_id = u.id
            WHERE dr.is_synced = 0
            ORDER BY dr.created_at ASC
        """)
        results.extend([dict(row) for row in cursor.fetchall()])

        return results

    def get_unsynced_farms_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT * FROM farms
            WHERE ((origin = 'edge' AND (cloud_id IS NULL OR synced_at IS NULL))
                   OR origin IS NULL)
              AND hidden = 0
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'farms' AND b.origin_id = farms.id)
            ORDER BY id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_animals_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT a.*, f.cloud_id AS farm_cloud_id
            FROM animals a
            JOIN farms f ON f.id = a.farm_id AND f.hidden = 0
            WHERE ((a.origin = 'edge' AND (a.cloud_id IS NULL OR a.synced_at IS NULL))
                   OR a.origin IS NULL)
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'animals' AND b.origin_id = a.id)
            ORDER BY a.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_uploads_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.*, f.cloud_id AS farm_cloud_id
            FROM uploads u
            JOIN farms f ON f.id = u.farm_id AND f.hidden = 0
            WHERE ((u.origin = 'edge' AND (u.cloud_id IS NULL OR u.synced_at IS NULL))
                   OR u.origin IS NULL)
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'uploads' AND b.origin_id = u.id)
            ORDER BY u.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_readings_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT r.*, a.cloud_id AS animal_cloud_id
            FROM animal_readings r
            JOIN animals a ON a.id = r.animal_id
            JOIN farms f ON f.id = a.farm_id AND f.hidden = 0
            WHERE ((r.origin = 'edge' AND (r.cloud_id IS NULL OR r.synced_at IS NULL))
                   OR r.origin IS NULL)
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'animal_readings' AND b.origin_id = r.id)
            ORDER BY r.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def mark_farm_synced(self, farm_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE farms SET cloud_id = ?, synced_at = datetime('now'), origin = 'edge' WHERE id = ?",
            (cloud_id, farm_id),
        )
        self.connection.commit()

    def mark_animal_synced(self, animal_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE animals SET cloud_id = ?, synced_at = datetime('now'), origin = 'edge' WHERE id = ?",
            (cloud_id, animal_id),
        )
        self.connection.commit()

    def mark_upload_synced(self, upload_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE uploads SET cloud_id = ?, synced_at = datetime('now'), origin = 'edge' WHERE id = ?",
            (cloud_id, upload_id),
        )
        self.connection.commit()

    def mark_reading_synced(self, reading_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE animal_readings SET cloud_id = ?, synced_at = datetime('now'), origin = 'edge' WHERE id = ?",
            (cloud_id, reading_id),
        )
        self.connection.commit()

    # Leche. Solo se envían subidas FINALIZADAS (`processed_at`): la nube no
    # actualiza una subida que ya conoce, y una sincronización automática en
    # mitad de una subida mandaría los contadores a cero para siempre.
    def get_unsynced_milk_uploads_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.*, f.cloud_id AS farm_cloud_id
            FROM milk_quality_uploads u
            JOIN farms f ON f.id = u.farm_id AND f.hidden = 0
            WHERE u.processed_at IS NOT NULL
              AND ((u.origin = 'edge' AND (u.cloud_id IS NULL OR u.synced_at IS NULL))
                   OR u.origin IS NULL)
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'milk_quality_uploads' AND b.origin_id = u.id)
            ORDER BY u.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_milk_results_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT r.*, u.cloud_id AS upload_cloud_id
            FROM milk_quality_results r
            JOIN milk_quality_uploads u ON u.id = r.upload_id
            JOIN farms f ON f.id = u.farm_id AND f.hidden = 0
            WHERE u.processed_at IS NOT NULL
              AND ((r.origin = 'edge' AND (r.cloud_id IS NULL OR r.synced_at IS NULL))
                   OR r.origin IS NULL)
              AND NOT EXISTS (SELECT 1 FROM sync_blocked b WHERE b.table_name = 'milk_quality_results' AND b.origin_id = r.id)
            ORDER BY r.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def mark_milk_upload_synced(self, upload_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE milk_quality_uploads SET cloud_id = ?, synced_at = datetime('now'), "
            "origin = 'edge' WHERE id = ?",
            (cloud_id, upload_id),
        )
        self.connection.commit()

    def mark_milk_result_synced(self, result_id: int, cloud_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE milk_quality_results SET cloud_id = ?, synced_at = datetime('now'), "
            "is_synced = 1, origin = 'edge' WHERE id = ?",
            (cloud_id, result_id),
        )
        self.connection.commit()

    # ------------------------------------------------------------------
    # Upsert from Cloud Sync (receive data from Cloud with origin='cloud')
    # ------------------------------------------------------------------
    def upsert_farm_from_cloud(
        self,
        cloud_id: int,
        name: str,
        location: str,
        created_at: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        access: Optional[str] = None,
    ) -> int:
        # The cloud only sends coordinates when the farm has them; a farm
        # without them never overwrites the ones set locally.
        if latitude is None or longitude is None:
            latitude = longitude = None
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id, hidden FROM farms WHERE cloud_id = ? AND origin = 'cloud'", (cloud_id,)
        )
        row = cursor.fetchone()
        if row:
            # Si la granja volvió a compartirse estaba oculta: se reactiva con su
            # acceso actual, y lo que quedó apartado por falta de permiso se libera.
            cursor.execute(
                "UPDATE farms SET name = ?, location = ?, "
                "latitude = COALESCE(?, latitude), longitude = COALESCE(?, longitude), "
                "cloud_access = COALESCE(?, cloud_access), hidden = 0 "
                "WHERE id = ?",
                (name, location, latitude, longitude, access, row["id"]),
            )
            self.connection.commit()
            if row["hidden"]:
                self.unblock_farm_data(row["id"])
            return row["id"]
        cursor.execute(
            "INSERT INTO farms (name, location, latitude, longitude, created_at, origin, cloud_id, synced_at, cloud_access) "
            "VALUES (?, ?, ?, ?, ?, 'cloud', ?, datetime('now'), ?)",
            (name, location, latitude, longitude, created_at, cloud_id, access),
        )
        self.connection.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Roles: acceso a las granjas y registros apartados
    # ------------------------------------------------------------------
    def set_farm_access(self, cloud_id: int, access: Optional[str]) -> None:
        """Guarda cómo ve la persona una granja que ya está enlazada con la nube."""
        if not access:
            return
        cursor = self.connection.cursor()
        cursor.execute("UPDATE farms SET cloud_access = ? WHERE cloud_id = ?", (access, cloud_id))
        self.connection.commit()

    def hide_farms_by_cloud_id(self, cloud_ids: List[int]) -> int:
        """Oculta (no borra) las granjas que la persona ya no ve en la nube.

        Devuelve cuántas había y quedan ocultas. Una id desconocida se ignora.
        """
        ocultas = 0
        cursor = self.connection.cursor()
        for cloud_id in cloud_ids:
            cursor.execute("UPDATE farms SET hidden = 1 WHERE cloud_id = ?", (cloud_id,))
            ocultas += cursor.rowcount
        self.connection.commit()
        return ocultas

    _TABLAS_APARTABLES = {
        "farms", "animals", "uploads", "animal_readings", "detection_results",
        "milk_quality_uploads", "milk_quality_results",
    }

    def block_record(self, table: str, origin_id: int, reason: str = "") -> bool:
        """Aparta un registro que la nube rechazó por falta de permiso."""
        if table not in self._TABLAS_APARTABLES:
            return False
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO sync_blocked (table_name, origin_id, reason) VALUES (?, ?, ?)",
            (table, origin_id, reason[:300]),
        )
        self.connection.commit()
        return True

    def count_blocked(self) -> int:
        cursor = self.connection.cursor()
        cursor.execute("SELECT COUNT(*) AS n FROM sync_blocked")
        return cursor.fetchone()["n"]

    def list_blocked(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM sync_blocked ORDER BY blocked_at DESC, table_name, origin_id")
        return [dict(row) for row in cursor.fetchall()]

    def unblock_farm_data(self, farm_id: int) -> int:
        """Libera lo apartado que cuelga de una granja (cuando recupera el permiso)."""
        cursor = self.connection.cursor()
        cursor.execute(
            """
            DELETE FROM sync_blocked WHERE
                (table_name = 'farms' AND origin_id = ?)
             OR (table_name = 'animals' AND origin_id IN
                    (SELECT id FROM animals WHERE farm_id = ?))
             OR (table_name = 'uploads' AND origin_id IN
                    (SELECT id FROM uploads WHERE farm_id = ?))
             OR (table_name = 'animal_readings' AND origin_id IN
                    (SELECT r.id FROM animal_readings r JOIN animals a ON a.id = r.animal_id
                     WHERE a.farm_id = ?))
             OR (table_name = 'detection_results' AND origin_id IN
                    (SELECT dr.id FROM detection_results dr JOIN uploads u ON u.id = dr.upload_id
                     WHERE u.farm_id = ?))
             OR (table_name = 'milk_quality_uploads' AND origin_id IN
                    (SELECT id FROM milk_quality_uploads WHERE farm_id = ?))
             OR (table_name = 'milk_quality_results' AND origin_id IN
                    (SELECT r.id FROM milk_quality_results r
                     JOIN milk_quality_uploads u ON u.id = r.upload_id WHERE u.farm_id = ?))
            """,
            (farm_id,) * 7,
        )
        self.connection.commit()
        return cursor.rowcount

    def upsert_animal_from_cloud(
        self, farm_id: int, cloud_id: int, external_tag: str, name: str, created_at: str
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM animals WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE animals SET name = ?, farm_id = ? WHERE id = ?",
                (name, farm_id, row["id"]),
            )
            self.connection.commit()
            return row["id"]
        cursor.execute(
            "INSERT INTO animals (farm_id, external_tag, name, created_at, origin, cloud_id, synced_at) VALUES (?, ?, ?, ?, 'cloud', ?, datetime('now'))",
            (farm_id, external_tag, name, created_at, cloud_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    def upsert_upload_from_cloud(
        self,
        farm_id: int,
        cloud_id: int,
        filename: str,
        upload_date: str,
        total_animals: int,
        celo_count: int,
        no_celo_count: int,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM uploads WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO uploads (farm_id, filename, upload_date, total_animals, celo_count, no_celo_count, origin, cloud_id, synced_at) VALUES (?, ?, ?, ?, ?, ?, 'cloud', ?, datetime('now'))",
            (
                farm_id,
                filename,
                upload_date,
                total_animals,
                celo_count,
                no_celo_count,
                cloud_id,
            ),
        )
        self.connection.commit()
        return cursor.lastrowid

    def upsert_reading_from_cloud(
        self,
        animal_id: int,
        cloud_id: int,
        reading_date: Optional[str],
        value: float,
        source_file: str,
        reading_order: Optional[int] = None,
        upload_id: Optional[int] = None,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM animal_readings WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO animal_readings (animal_id, reading_date, value, source_file, "
            "reading_order, upload_id, origin, cloud_id, synced_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'cloud', ?, datetime('now'))",
            (animal_id, reading_date, value, source_file, reading_order, upload_id, cloud_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    def upsert_result_from_cloud(
        self,
        animal_id: int,
        upload_id: int,
        cloud_id: int,
        result: str,
        confidence: float,
        probability: float,
        created_at: str,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM detection_results WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO detection_results (animal_id, upload_id, result, confidence, probability, created_at, is_synced, origin, cloud_id, synced_at) VALUES (?, ?, ?, ?, ?, ?, 1, 'cloud', ?, datetime('now'))",
            (
                animal_id,
                upload_id,
                result,
                confidence,
                probability,
                created_at,
                cloud_id,
            ),
        )
        self.connection.commit()
        return cursor.lastrowid

    def upsert_milk_upload_from_cloud(
        self,
        farm_id: int,
        cloud_id: int,
        filename: str,
        upload_date: str,
        total_samples: int,
        lower_count: int,
        upper_count: int,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM milk_quality_uploads WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        # processed_at = upload_date: viene ya procesada de la nube
        cursor.execute(
            "INSERT INTO milk_quality_uploads (farm_id, filename, upload_date, processed_at, "
            "total_samples, lower_count, upper_count, origin, cloud_id, synced_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'cloud', ?, datetime('now'))",
            (farm_id, filename, upload_date, upload_date, total_samples,
             lower_count, upper_count, cloud_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    def upsert_milk_result_from_cloud(
        self,
        upload_id: int,
        cloud_id: int,
        sample_id: str,
        result: str,
        created_at: str,
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM milk_quality_results WHERE cloud_id = ? AND origin = 'cloud'",
            (cloud_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["id"]
        cursor.execute(
            "INSERT INTO milk_quality_results (sample_id, upload_id, result, created_at, "
            "is_synced, origin, cloud_id, synced_at) "
            "VALUES (?, ?, ?, ?, 1, 'cloud', ?, datetime('now'))",
            (sample_id, upload_id, result, created_at, cloud_id),
        )
        self.connection.commit()
        return cursor.lastrowid

    # ------------------------------------------------------------------
    # Farm Calendar Sync (tracking FC UUIDs ↔ local IDs)
    # ------------------------------------------------------------------
    def get_fc_uuid(self, entity_type: str, local_id: int) -> Optional[str]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT fc_uuid FROM farmcalendar_sync WHERE entity_type = ? AND local_id = ?",
            (entity_type, local_id),
        )
        row = cursor.fetchone()
        return row["fc_uuid"] if row else None

    def save_fc_uuid(self, entity_type: str, local_id: int, fc_uuid: str) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """INSERT INTO farmcalendar_sync (entity_type, local_id, fc_uuid, synced_at)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(entity_type, local_id) DO UPDATE SET
                   fc_uuid = excluded.fc_uuid,
                   synced_at = datetime('now')""",
            (entity_type, local_id, fc_uuid),
        )
        self.connection.commit()
