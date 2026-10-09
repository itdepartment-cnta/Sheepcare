"""
Publica en el Farm Calendar LOCAL las subidas que bajan de la nube con el pull.

Las subidas que se hacen en esta máquina ya se publican al subirlas (ver
`api/uploads.py` y `api/milk_quality.py`). Las que se hicieron en la web de la
nube, o en otra instalación, solo se guardaban en SQLite y el calendario local
no las tenía. Aquí se publican con las mismas funciones del cliente y con la
fecha ORIGINAL de la subida, no la de hoy.

Solo se publican las subidas que acaban de insertarse por primera vez, así que
repetir el pull no duplica nada. Un fallo del calendario nunca debe impedir
guardar el dato ni confirmar el pull: se registra y se sigue.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .farmcalendar_client import FarmCalendarClient

logger = logging.getLogger(__name__)

# Tras este número de fallos seguidos se deja de intentar en esta vuelta: Farm
# Calendar está parado o no responde, y cada intento espera hasta 15 s.
MAX_FALLOS_SEGUIDOS = 2


def _asegurar_granja(db, client, farm_id: int, nombre: str, ubicacion: str) -> None:
    """Crea la granja y su parcela en Farm Calendar si aún no están (como hace la subida)."""
    if db.get_fc_uuid("farm", farm_id):
        return
    fc_uuid = client.sync_farm(nombre, ubicacion)
    if not fc_uuid:
        return
    db.save_fc_uuid("farm", farm_id, fc_uuid)
    parcela = client.sync_parcel(fc_uuid, f"parcel_{farm_id}")
    if parcela:
        db.save_fc_uuid("parcel", farm_id, parcela)


def _filas(db, sql: str, *args) -> List[Dict[str, Any]]:
    cursor = db.connection.execute(sql, args)
    columnas = [d[0] for d in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def publicar_subida_celo(db, upload_id: int, client=None) -> bool:
    subida = _filas(
        db,
        "SELECT u.*, f.name AS farm_name, f.location AS farm_location "
        "FROM uploads u JOIN farms f ON f.id = u.farm_id WHERE u.id = ?",
        upload_id,
    )
    if not subida:
        return False
    u = subida[0]
    client = client or FarmCalendarClient()
    _asegurar_granja(db, client, u["farm_id"], u["farm_name"], u["farm_location"] or "")
    animales = _filas(
        db,
        "SELECT a.external_tag AS animal_id, dr.result AS result, dr.confidence AS confidence "
        "FROM detection_results dr JOIN animals a ON a.id = dr.animal_id "
        "WHERE dr.upload_id = ? ORDER BY dr.id",
        upload_id,
    )
    return client.post_estrus_detection(
        farm_name=u["farm_name"],
        celo_count=u["celo_count"] or 0,
        no_celo_count=u["no_celo_count"] or 0,
        filename=u["filename"],
        upload_date=u["upload_date"],
        animal_details=animales,
    )


def publicar_subida_leche(db, upload_id: int, client=None) -> bool:
    subida = _filas(
        db,
        "SELECT u.*, f.name AS farm_name, f.location AS farm_location "
        "FROM milk_quality_uploads u JOIN farms f ON f.id = u.farm_id WHERE u.id = ?",
        upload_id,
    )
    if not subida:
        return False
    u = subida[0]
    client = client or FarmCalendarClient()
    _asegurar_granja(db, client, u["farm_id"], u["farm_name"], u["farm_location"] or "")
    # El cliente espera la clave `animal_id` también para las muestras de leche
    muestras = _filas(
        db,
        "SELECT sample_id AS animal_id, result FROM milk_quality_results "
        "WHERE upload_id = ? ORDER BY id",
        upload_id,
    )
    return client.post_milk_quality_detection(
        farm_name=u["farm_name"],
        buena_count=u["lower_count"] or 0,
        mala_count=u["upper_count"] or 0,
        filename=u["filename"],
        upload_date=u["upload_date"],
        sample_details=muestras,
    )


def publicar_nuevas(db, nuevas: List[Tuple[str, int]], client=None) -> int:
    """Publica `[("estrus"|"milk", id local de la subida)]`. Devuelve cuántas se publicaron.

    Nunca lanza: lo que falle se registra y se omite.
    """
    if not nuevas:
        return 0
    publicadas = 0
    fallos = 0
    try:
        client = client or FarmCalendarClient()
    except Exception as e:  # noqa: BLE001
        logger.warning("Farm Calendar local no disponible: %s", e)
        return 0
    for i, (tipo, upload_id) in enumerate(nuevas):
        if fallos >= MAX_FALLOS_SEGUIDOS:
            logger.warning(
                "Farm Calendar local no responde: %s subidas se quedan sin publicar en el calendario",
                len(nuevas) - i,
            )
            break
        try:
            ok = (publicar_subida_celo if tipo == "estrus" else publicar_subida_leche)(db, upload_id, client)
        except Exception as e:  # noqa: BLE001
            logger.warning("No se pudo publicar la subida %s %s en Farm Calendar: %s", tipo, upload_id, e)
            ok = False
        if ok:
            publicadas += 1
            fallos = 0
        else:
            fallos += 1
    return publicadas
