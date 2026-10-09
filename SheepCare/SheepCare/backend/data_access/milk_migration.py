"""
Migración del almacén de calidad de leche de la base SQLite local.

Hasta ahora cada muestra de leche se guardaba como una fila de `animals`
(`db.add_animal(farm_id, sample_id)`) y `milk_quality_results.animal_id`
apuntaba a ella. En la nube las muestras son filas de `milk_quality_results`
con un `sample_id` de texto y sin animal. Si el Edge sincronizara así, sus
muestras llegarían a la nube como animales y se mezclarían con los reales.

Esta migración:
  1. reconstruye `milk_quality_results` con `sample_id` (sin `animal_id`) y las
     columnas de sincronización (`origin`, `cloud_id`, `synced_at`, `is_synced`);
  2. borra de `animals` los «animales» que solo existían por la leche: los
     referenciados únicamente por `milk_quality_results` (ni detecciones de
     celo ni lecturas).

Un animal con leche **y** celo o lecturas NO se borra: es un animal real (o una
etiqueta que coincide con una muestra) y no se puede distinguir. Su resultado de
leche sí se conserva, ya como muestra.

Garantías:
  * Copia de seguridad antes de tocar nada (`<base>.antes-leche-<fecha>.bak`).
  * Una sola transacción: si algo falla se revierte y la base queda como estaba.
  * Idempotente: sin `animal_id` en `milk_quality_results` no hace nada.
  * Comprueba que no se pierde ninguna fila de resultados.

Uso suelto, sobre una COPIA de la base:

    python -m backend.data_access.milk_migration <base.db>             # solo informa
    python -m backend.data_access.milk_migration <base.db> --aplicar   # migra (con copia)
"""

import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Esquema de destino. También lo usa `_create_tables` en las instalaciones nuevas.
NEW_TABLE_SQL = """
    CREATE TABLE {name} (
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
    )
"""

# Animales que solo existen por la leche: tienen resultados de leche y nada más.
_SOLO_LECHE = """
    SELECT DISTINCT mr.animal_id
    FROM milk_quality_results mr
    WHERE mr.animal_id NOT IN (SELECT animal_id FROM detection_results)
      AND mr.animal_id NOT IN (SELECT animal_id FROM animal_readings)
"""


def needs_migration(conn: sqlite3.Connection) -> bool:
    """Hay migración pendiente si `milk_quality_results` aún tiene `animal_id`."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(milk_quality_results)")]
    return "animal_id" in cols


def analyze(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Qué haría la migración, sin modificar nada."""
    if not needs_migration(conn):
        return {"pendiente": False}
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    solo_leche = q(f"SELECT COUNT(*) FROM ({_SOLO_LECHE})")
    con_leche = q("SELECT COUNT(DISTINCT animal_id) FROM milk_quality_results")
    cur = conn.execute(
        f"""
        SELECT a.id, a.farm_id, a.external_tag,
               (SELECT COUNT(*) FROM detection_results d WHERE d.animal_id = a.id) AS detecciones,
               (SELECT COUNT(*) FROM animal_readings l WHERE l.animal_id = a.id) AS lecturas
        FROM animals a
        WHERE a.id IN (SELECT animal_id FROM milk_quality_results)
          AND a.id NOT IN ({_SOLO_LECHE})
        """
    )
    columnas = [d[0] for d in cur.description]
    ambiguos = [dict(zip(columnas, fila)) for fila in cur.fetchall()]
    return {
        "pendiente": True,
        "resultados_leche": q("SELECT COUNT(*) FROM milk_quality_results"),
        "animales_con_leche": con_leche,
        "animales_a_borrar": solo_leche,
        "animales_que_se_conservan": ambiguos,
        # Estos ya se sincronizaron con la nube como animales (caso C6 de la guía):
        # al borrarlos aquí la nube conserva su copia.
        "a_borrar_ya_en_la_nube": (
            q(f"SELECT COUNT(*) FROM animals WHERE cloud_id IS NOT NULL AND id IN ({_SOLO_LECHE})")
            if "cloud_id" in [r[1] for r in conn.execute("PRAGMA table_info(animals)")]
            else 0  # base anterior a la sincronización: nada pudo llegar a la nube
        ),
        "animales_totales": q("SELECT COUNT(*) FROM animals"),
    }


def backup(conn: sqlite3.Connection, db_path: str, etiqueta: str = "leche") -> str:
    """Copia de seguridad consistente (API de copia de SQLite, válida con WAL)."""
    destino = f"{db_path}.antes-{etiqueta}-{datetime.now():%Y%m%d-%H%M%S}.bak"
    copia = sqlite3.connect(destino)
    try:
        conn.backup(copia)
    finally:
        copia.close()
    return destino


def migrate(conn: sqlite3.Connection, db_path: str) -> Dict[str, Any]:
    """Aplica la migración. Devuelve el informe; {'pendiente': False} si no hacía falta."""
    informe = analyze(conn)
    if not informe["pendiente"]:
        return informe

    if conn.in_transaction:
        conn.commit()
    copia = backup(conn, db_path) if db_path and db_path != ":memory:" else ""
    informe["copia_de_seguridad"] = copia
    logger.warning(
        "Migrando la calidad de leche: %s resultados, %s animales-muestra a borrar. Copia: %s",
        informe["resultados_leche"], informe["animales_a_borrar"], copia or "(en memoria)",
    )

    try:
        conn.execute("BEGIN")
        conn.execute(NEW_TABLE_SQL.format(name="milk_quality_results_new"))
        # LEFT JOIN: una fila huérfana no debe perderse ni bloquear el arranque.
        conn.execute(
            """
            INSERT INTO milk_quality_results_new (id, sample_id, upload_id, result, created_at)
            SELECT mr.id, COALESCE(a.external_tag, 'animal-' || mr.animal_id),
                   mr.upload_id, mr.result, mr.created_at
            FROM milk_quality_results mr
            LEFT JOIN animals a ON a.id = mr.animal_id
            """
        )
        copiadas = conn.execute("SELECT COUNT(*) FROM milk_quality_results_new").fetchone()[0]
        if copiadas != informe["resultados_leche"]:
            raise RuntimeError(
                f"Se esperaban {informe['resultados_leche']} resultados y se copiaron {copiadas}"
            )

        candidatos: List[int] = [r[0] for r in conn.execute(_SOLO_LECHE)]
        conn.execute("CREATE TEMP TABLE _animales_muestra (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO _animales_muestra VALUES (?)", [(i,) for i in candidatos])
        conn.execute(
            "DELETE FROM farmcalendar_sync WHERE entity_type = 'animal' "
            "AND local_id IN (SELECT id FROM _animales_muestra)"
        )
        conn.execute("DELETE FROM animals WHERE id IN (SELECT id FROM _animales_muestra)")
        conn.execute("DROP TABLE _animales_muestra")

        conn.execute("DROP TABLE milk_quality_results")
        conn.execute("ALTER TABLE milk_quality_results_new RENAME TO milk_quality_results")
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(
            "La migración de la leche falló y se revirtió. La base no ha cambiado; "
            "copia de seguridad en %s", copia or "(ninguna)",
        )
        raise

    informe["pendiente"] = False
    informe["migrado"] = True
    return informe


def migrate_if_needed(conn: sqlite3.Connection, db_path: str) -> None:
    """Punto de entrada desde `DatabaseManager._create_tables`."""
    migrate(conn, db_path)


def _imprimir(informe: Dict[str, Any]) -> None:
    if not informe.get("pendiente") and not informe.get("migrado"):
        print("Nada que migrar: la base ya usa sample_id.")
        return
    print(f"Resultados de leche:              {informe['resultados_leche']}")
    print(f"Animales con leche:               {informe['animales_con_leche']} (de {informe['animales_totales']} en total)")
    print(f"Animales-muestra a borrar:        {informe['animales_a_borrar']}")
    print(f"  de ellos, ya en la nube:        {informe['a_borrar_ya_en_la_nube']}")
    print(f"Se conservan (leche + celo/lect): {len(informe['animales_que_se_conservan'])}")
    for a in informe["animales_que_se_conservan"]:
        print(f"    id {a['id']}  granja {a['farm_id']}  etiqueta {a['external_tag']!r}  "
              f"detecciones {a['detecciones']}  lecturas {a['lecturas']}")
    if informe.get("copia_de_seguridad"):
        print(f"Copia de seguridad:               {informe['copia_de_seguridad']}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or not os.path.exists(args[0]):
        sys.exit(__doc__)
    aplicar = "--aplicar" in sys.argv
    con = sqlite3.connect(args[0] if aplicar else f"file:{args[0]}?mode=ro", uri=not aplicar)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        _imprimir(migrate(con, args[0]) if aplicar else analyze(con))
        if not aplicar:
            print("\nSolo informe. Añade --aplicar para migrar (hace copia de seguridad antes).")
    finally:
        con.close()
