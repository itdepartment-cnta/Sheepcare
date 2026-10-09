"""
Migración de `animal_readings`: la fecha de una lectura puede faltar.

El Excel de celo dejó de traer fechas de medición y rotula las columnas «dia 1»
y «dia 2». La nube guarda esas lecturas SIN fecha, con su orden dentro de la
subida (`reading_order`) y la subida a la que pertenecen (`upload_id`). La
versión local exigía fecha (`reading_date NOT NULL`) y, para cumplirlo, guardaba
la etiqueta de la columna como si fuera una fecha («date_1», «dia 2»), con lo que
no podía recibir las lecturas sin fecha de la nube.

Esta migración reconstruye la tabla con la fecha opcional y las dos columnas
nuevas, y corrige lo ya guardado: una «fecha» que no lo es pasa a ser NULL y, si
termina en un número, ese número es el orden (`date_2` -> orden 2).

Garantías (las mismas que la migración de la leche): copia de seguridad previa,
una sola transacción, idempotente y comprobación de que no se pierde ninguna fila.
No se inventa ninguna fecha.

Uso suelto, sobre una COPIA de la base:

    python -m backend.data_access.readings_migration <base.db>             # solo informa
    python -m backend.data_access.readings_migration <base.db> --aplicar   # migra (con copia)
"""

import logging
import os
import re
import sqlite3
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .milk_migration import backup

logger = logging.getLogger(__name__)

# Esquema de destino. También lo usa `_create_tables` en las instalaciones nuevas.
NEW_TABLE_SQL = """
    CREATE TABLE {name} (
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
    )
"""

_NUMERO_FINAL = re.compile(r"(\d+)\s*$")


def es_fecha(valor: Any) -> bool:
    """¿Es una fecha ISO (YYYY-MM-DD o con hora)?"""
    if valor is None:
        return False
    try:
        datetime.fromisoformat(str(valor).strip())
    except ValueError:
        return False
    return True


def fecha_y_orden(valor: Any) -> Tuple[Optional[str], Optional[int]]:
    """(fecha, orden) de lo que hay guardado como «fecha».

    Una fecha real se conserva y no lleva orden. Lo demás es una etiqueta de
    columna: no hay fecha, y el número con que termina (si lo hay) es el orden.
    """
    if es_fecha(valor):
        return str(valor).strip(), None
    m = _NUMERO_FINAL.search(str(valor)) if valor is not None else None
    return None, (int(m.group(1)) if m else None)


def _columnas(conn: sqlite3.Connection, tabla: str):
    return conn.execute(f"PRAGMA table_info({tabla})").fetchall()


def needs_migration(conn: sqlite3.Connection) -> bool:
    """Pendiente si la fecha sigue siendo obligatoria o faltan las columnas nuevas."""
    info = _columnas(conn, "animal_readings")
    if not info:
        return False
    por_nombre = {c[1]: c for c in info}
    return bool(por_nombre.get("reading_date") and por_nombre["reading_date"][3] == 1) or \
        "reading_order" not in por_nombre or "upload_id" not in por_nombre


def analyze(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Qué haría la migración, sin modificar nada."""
    if not needs_migration(conn):
        return {"pendiente": False}
    filas = conn.execute("SELECT reading_date FROM animal_readings").fetchall()
    etiquetas = [f[0] for f in filas if not es_fecha(f[0])]
    con_orden = sum(1 for e in etiquetas if fecha_y_orden(e)[1] is not None)
    return {
        "pendiente": True,
        "lecturas": len(filas),
        "con_fecha_real": len(filas) - len(etiquetas),
        "etiquetas_de_columna": len(etiquetas),
        "etiquetas_con_orden": con_orden,
        "ejemplos": sorted({str(e) for e in etiquetas})[:5],
    }


def migrate(conn: sqlite3.Connection, db_path: str) -> Dict[str, Any]:
    informe = analyze(conn)
    if not informe["pendiente"]:
        return informe

    if conn.in_transaction:
        conn.commit()
    copia = backup(conn, db_path, "lecturas") if db_path and db_path != ":memory:" else ""
    informe["copia_de_seguridad"] = copia
    logger.warning(
        "Migrando las lecturas: %s lecturas, %s con etiqueta de columna en vez de fecha. Copia: %s",
        informe["lecturas"], informe["etiquetas_de_columna"], copia or "(en memoria)",
    )

    existentes = {c[1] for c in _columnas(conn, "animal_readings")}
    # Las columnas de sincronización pueden no existir en una base muy antigua
    opcionales = [c for c in ("origin", "cloud_id", "synced_at") if c in existentes]
    try:
        conn.execute("BEGIN")
        conn.execute(NEW_TABLE_SQL.format(name="animal_readings_new"))
        cols = ["id", "animal_id", "reading_date", "value", "source_file"] + opcionales
        filas = conn.execute(f"SELECT {', '.join(cols)} FROM animal_readings").fetchall()
        nuevas = []
        for f in filas:
            d = dict(zip(cols, f))
            fecha, orden = fecha_y_orden(d["reading_date"])
            nuevas.append((
                d["id"], d["animal_id"], fecha, d["value"], d["source_file"], orden, None,
                d.get("origin", "edge"), d.get("cloud_id"), d.get("synced_at"),
            ))
        conn.executemany(
            "INSERT INTO animal_readings_new (id, animal_id, reading_date, value, source_file, "
            "reading_order, upload_id, origin, cloud_id, synced_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            nuevas,
        )
        copiadas = conn.execute("SELECT COUNT(*) FROM animal_readings_new").fetchone()[0]
        if copiadas != informe["lecturas"]:
            raise RuntimeError(f"Se esperaban {informe['lecturas']} lecturas y se copiaron {copiadas}")
        conn.execute("DROP TABLE animal_readings")
        conn.execute("ALTER TABLE animal_readings_new RENAME TO animal_readings")
        conn.commit()
    except Exception:
        conn.rollback()
        logger.error(
            "La migración de las lecturas falló y se revirtió. La base no ha cambiado; "
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
        print("Nada que migrar: la fecha de las lecturas ya es opcional.")
        return
    print(f"Lecturas:                         {informe['lecturas']}")
    print(f"  con fecha real (se conservan):  {informe['con_fecha_real']}")
    print(f"  con etiqueta en vez de fecha:   {informe['etiquetas_de_columna']}  (pasan a fecha vacía)")
    print(f"  de ellas, con un orden claro:   {informe['etiquetas_con_orden']}")
    if informe["ejemplos"]:
        print(f"  ejemplos de etiqueta:           {informe['ejemplos']}")
    if informe.get("copia_de_seguridad"):
        print(f"Copia de seguridad:               {informe['copia_de_seguridad']}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1 or not os.path.exists(args[0]):
        sys.exit(__doc__)
    aplicar = "--aplicar" in sys.argv
    con = sqlite3.connect(args[0] if aplicar else f"file:{args[0]}?mode=ro", uri=not aplicar)
    con.execute("PRAGMA foreign_keys=ON")
    try:
        _imprimir(migrate(con, args[0]) if aplicar else analyze(con))
        if not aplicar:
            print("\nSolo informe. Añade --aplicar para migrar (hace copia de seguridad antes).")
    finally:
        con.close()
