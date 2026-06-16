"""
DatabaseManager - Singleton for SQLite operations.
Extended schema for SHEEPCARE v2: farms, uploads, animal_readings, detection_results.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


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

            CREATE TABLE IF NOT EXISTS animals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id      INTEGER NOT NULL,
                external_tag TEXT    NOT NULL,
                name         TEXT    NOT NULL DEFAULT '',
                created_at   DATETIME NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE CASCADE,
                UNIQUE(farm_id, external_tag)
            );

            CREATE TABLE IF NOT EXISTS animal_readings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                animal_id    INTEGER NOT NULL,
                reading_date DATE    NOT NULL,
                value        FLOAT   NOT NULL,
                source_file  TEXT    NOT NULL DEFAULT '',
                FOREIGN KEY (animal_id) REFERENCES animals(id) ON DELETE CASCADE
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
        ]
        for table, col, col_type, default in migrations:
            try:
                cursor.execute(
                    f"ALTER TABLE {table} ADD COLUMN {col} {col_type} DEFAULT {default}"
                )
            except sqlite3.OperationalError:
                pass  # Column already exists

        self.connection.commit()

    # ------------------------------------------------------------------
    # Farms CRUD
    # ------------------------------------------------------------------
    def add_farm(self, name: str, location: str = "") -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO farms (name, location) VALUES (?, ?)",
            (name, location),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_farm(self, farm_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM farms WHERE id = ?", (farm_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_farms(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM farms ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def update_farm(self, farm_id: int, name: str, location: str) -> bool:
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE farms SET name = ?, location = ? WHERE id = ?",
            (name, location, farm_id),
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
        cursor.execute("SELECT * FROM animals WHERE id = ?", (animal_id,))
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
                "SELECT a.*, f.name as farm_name FROM animals a JOIN farms f ON a.farm_id = f.id WHERE a.farm_id = ? ORDER BY a.external_tag",
                (farm_id,),
            )
        else:
            cursor.execute(
                "SELECT a.*, f.name as farm_name FROM animals a JOIN farms f ON a.farm_id = f.id ORDER BY a.external_tag"
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
        self, animal_id: int, reading_date: str, value: float, source_file: str = ""
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO animal_readings (animal_id, reading_date, value, source_file) VALUES (?, ?, ?, ?)",
            (animal_id, reading_date, value, source_file),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_animal_readings(self, animal_id: int) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT * FROM animal_readings WHERE animal_id = ? ORDER BY reading_date",
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
            JOIN farms f ON u.farm_id = f.id
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
                JOIN farms f ON u.farm_id = f.id
                WHERE u.farm_id = ?
                ORDER BY u.upload_date DESC
            """,
                (farm_id,),
            )
        else:
            cursor.execute("""
                SELECT u.*, f.name as farm_name
                FROM uploads u
                JOIN farms f ON u.farm_id = f.id
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
            JOIN farms f ON u.farm_id = f.id
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
            JOIN farms f ON u.farm_id = f.id
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
                JOIN farms f ON u.farm_id = f.id
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
                JOIN farms f ON u.farm_id = f.id
                ORDER BY dr.created_at DESC LIMIT 1
            """)
        row = cursor.fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Sync tracking
    # ------------------------------------------------------------------
    def get_unsynced_results(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT dr.*, a.external_tag as animal_tag, f.name as farm_name
            FROM detection_results dr
            JOIN animals a ON dr.animal_id = a.id
            JOIN uploads u ON dr.upload_id = u.id
            JOIN farms f ON u.farm_id = f.id
            WHERE dr.is_synced = 0
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
            WHERE (origin = 'edge' AND (cloud_id IS NULL OR synced_at IS NULL))
               OR origin IS NULL
            ORDER BY id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_animals_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT a.* FROM animals a
            WHERE (a.origin = 'edge' AND (a.cloud_id IS NULL OR a.synced_at IS NULL))
               OR a.origin IS NULL
            ORDER BY a.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_uploads_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT u.* FROM uploads u
            WHERE (u.origin = 'edge' AND (u.cloud_id IS NULL OR u.synced_at IS NULL))
               OR u.origin IS NULL
            ORDER BY u.id
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_unsynced_readings_to_cloud(self) -> List[Dict[str, Any]]:
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT r.* FROM animal_readings r
            WHERE (r.origin = 'edge' AND (r.cloud_id IS NULL OR r.synced_at IS NULL))
               OR r.origin IS NULL
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

    # ------------------------------------------------------------------
    # Upsert from Cloud Sync (receive data from Cloud with origin='cloud')
    # ------------------------------------------------------------------
    def upsert_farm_from_cloud(
        self, cloud_id: int, name: str, location: str, created_at: str
    ) -> int:
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT id FROM farms WHERE cloud_id = ? AND origin = 'cloud'", (cloud_id,)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE farms SET name = ?, location = ? WHERE id = ?",
                (name, location, row["id"]),
            )
            self.connection.commit()
            return row["id"]
        cursor.execute(
            "INSERT INTO farms (name, location, created_at, origin, cloud_id, synced_at) VALUES (?, ?, ?, 'cloud', ?, datetime('now'))",
            (name, location, created_at, cloud_id),
        )
        self.connection.commit()
        return cursor.lastrowid

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
        reading_date: str,
        value: float,
        source_file: str,
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
            "INSERT INTO animal_readings (animal_id, reading_date, value, source_file, origin, cloud_id, synced_at) VALUES (?, ?, ?, ?, 'cloud', ?, datetime('now'))",
            (animal_id, reading_date, value, source_file, cloud_id),
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
