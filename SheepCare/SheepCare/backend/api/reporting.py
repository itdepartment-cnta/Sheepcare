"""
Reporting API - informes PDF por granja (celo y calidad de leche) via
OpenAgri Reporting Service.

Reporting es un proceso local aparte (REPORTING_API_URL) que solo escucha en
127.0.0.1. Este router hace de intermediario para el navegador:

  1. Lee la granja y sus resultados de SQLite (filtrados por dia).
  2. Prepara los datos en el formato del informe y los envia a Reporting.
  3. Espera a que el PDF este listo y lo devuelve en la misma peticion.

Misma API y mismos PDF que la version cloud (/api/reporting/farms/{id}/...).
"""

import asyncio
import logging
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ..data_access.db_manager import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
db = DatabaseManager()

REPORTING_API_URL = os.environ.get("REPORTING_API_URL", "http://127.0.0.1:8004").rstrip("/")
REPORTING_ESTRUS = f"{REPORTING_API_URL}/api/v1/openagri-report/livestock-estrus-report/"
REPORTING_MILK = f"{REPORTING_API_URL}/api/v1/openagri-report/livestock-milk-quality-report/"

# SQLite guarda las fechas en UTC (datetime('now')) sin zona; el informe imprime
# el dia, asi que se convierte a hora local. Misma zona que la version cloud.
REPORT_TIMEZONE = ZoneInfo(os.environ.get("REPORT_TIMEZONE", "Europe/Madrid"))

# Cuanto se espera a que Reporting termine el PDF
ESPERA_MAXIMA_S = 45.0
INTERVALO_S = 0.5

# Reporting usa codigos neutros para no depender del idioma ni de nuestro modelo.
RESULTADOS_CELO = {"Celo": "estrus", "No celo": "no_estrus"}
RESULTADOS_LECHE = {"Lower": "low", "Upper": "high"}


def _fecha_local(texto: str) -> datetime:
    """Fecha de SQLite (UTC, con o sin zona) -> datetime ingenuo en hora local."""
    dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(REPORT_TIMEZONE).replace(tzinfo=None)


def _hora_local(texto: str) -> str:
    return _fecha_local(texto).isoformat()


def filtrar_por_dia(
    resultados: List[dict], from_date: Optional[date], to_date: Optional[date]
) -> List[dict]:
    """Deja los resultados cuya subida cae en [from_date, to_date] (dias locales)."""
    if not from_date and not to_date:
        return resultados
    salida = []
    for r in resultados:
        dia = _fecha_local(r["upload_date"]).date()
        if from_date and dia < from_date:
            continue
        if to_date and dia > to_date:
            continue
        salida.append(r)
    return salida


def preparar_datos_celo(
    granja: dict,
    resultados: List[dict],
    from_date: Optional[date],
    to_date: Optional[date],
) -> dict:
    """Cuerpo de la peticion a Reporting a partir de los datos locales."""
    por_subida: Dict[int, dict] = {}
    animales: Dict[int, list] = defaultdict(list)
    for r in resultados:
        codigo = RESULTADOS_CELO.get(r.get("result"))
        if codigo is None:
            # Un resultado que no es Celo/No celo no debe colarse como uno de ellos
            logger.warning("Resultado desconocido omitido en el informe: %r", r.get("result"))
            continue
        subida = r["upload_id"]
        if subida not in por_subida:
            por_subida[subida] = {
                "upload_date": _hora_local(r["upload_date"]),
                "filename": r.get("filename") or "",
            }
        animales[subida].append(
            {
                # La etiqueta de la oreja identifica al animal; el nombre es opcional
                "animal_id": r.get("animal_tag") or r.get("animal_name") or str(r["animal_id"]),
                "result": codigo,
                "confidence": r.get("confidence"),
            }
        )

    return {
        "farm_name": granja["name"],
        "farm_municipality": granja.get("location") or "",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "uploads": [{**por_subida[i], "animals": animales[i]} for i in sorted(por_subida)],
    }


def preparar_datos_leche(
    granja: dict,
    resultados: List[dict],
    from_date: Optional[date],
    to_date: Optional[date],
) -> dict:
    """Cuerpo de la peticion del informe de calidad de leche."""
    por_subida: Dict[int, dict] = {}
    muestras: Dict[int, list] = defaultdict(list)
    for r in resultados:
        codigo = RESULTADOS_LECHE.get(r.get("result"))
        if codigo is None:
            logger.warning("Resultado desconocido omitido en el informe: %r", r.get("result"))
            continue
        subida = r["upload_id"]
        if subida not in por_subida:
            por_subida[subida] = {
                "upload_date": _hora_local(r["upload_date"]),
                "filename": r.get("filename") or "",
            }
        # En la version local la muestra se guarda con su etiqueta en `animals`
        muestras[subida].append(
            {"sample_id": r.get("animal_tag") or str(r["animal_id"]), "result": codigo}
        )

    return {
        "farm_name": granja["name"],
        "farm_municipality": granja.get("location") or "",
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "uploads": [{**por_subida[i], "samples": muestras[i]} for i in sorted(por_subida)],
    }


def _nombre_fichero(prefijo: str, farm_name: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", farm_name).encode("ascii", "ignore").decode()
    limpio = re.sub(r"[^A-Za-z0-9]+", "-", ascii_).strip("-").lower() or "granja"
    return f"{prefijo}-{limpio}-{date.today().isoformat()}.pdf"


async def _generar_pdf(url_base: str, cuerpo: dict, lang: str) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=20.0) as cliente:
            r = await cliente.post(url_base, params={"lang": lang}, json=cuerpo)
            if r.status_code != 200:
                logger.error("Reporting rechazo el informe (%s): %s", r.status_code, r.text[:300])
                raise HTTPException(502, "El servicio de informes no pudo generarlo")
            url = f"{url_base}{r.json()['uuid']}/"

            esperado = 0.0
            while esperado < ESPERA_MAXIMA_S:
                g = await cliente.get(url)
                if g.status_code == 200:
                    return g.content
                if g.status_code != 202:
                    logger.error("Reporting devolvio %s al recuperar el informe", g.status_code)
                    raise HTTPException(502, "El servicio de informes no pudo generarlo")
                await asyncio.sleep(INTERVALO_S)
                esperado += INTERVALO_S
    except httpx.RequestError as exc:
        logger.error("Reporting no responde: %s", exc)
        raise HTTPException(503, "Servicio de informes no disponible")
    raise HTTPException(504, "El informe tardó demasiado en generarse")


async def _informe_de_la_granja(
    farm_id: int,
    from_date: Optional[date],
    to_date: Optional[date],
    lang: str,
    *,
    obtener_resultados: Callable[[int], List[dict]],
    preparar: Callable[..., dict],
    url_reporting: str,
    prefijo_fichero: str,
) -> Response:
    """Comun a los informes por granja: datos locales -> Reporting -> PDF."""
    if from_date and to_date and to_date < from_date:
        raise HTTPException(422, "La fecha final no puede ser anterior a la inicial")

    granja = db.get_farm(farm_id)
    if not granja:
        raise HTTPException(404, "Granja no encontrada")
    resultados = filtrar_por_dia(obtener_resultados(farm_id), from_date, to_date)

    pdf = await _generar_pdf(url_reporting, preparar(granja, resultados, from_date, to_date), lang)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{_nombre_fichero(prefijo_fichero, granja["name"])}"'
        },
    )


@router.get("/farms/{farm_id}/estrus-report")
async def informe_de_celo(
    farm_id: int,
    from_date: Optional[date] = Query(None, description="Primer dia, inclusive"),
    to_date: Optional[date] = Query(None, description="Ultimo dia, inclusive"),
    lang: str = Query("es", pattern="^(es|en)$"),
):
    """PDF con la deteccion de celo de la granja en el periodo."""
    return await _informe_de_la_granja(
        farm_id, from_date, to_date, lang,
        obtener_resultados=lambda fid: db.get_results(farm_id=fid),
        preparar=preparar_datos_celo,
        url_reporting=REPORTING_ESTRUS,
        prefijo_fichero="informe-celo",
    )


@router.get("/farms/{farm_id}/milk-quality-report")
async def informe_de_calidad_de_leche(
    farm_id: int,
    from_date: Optional[date] = Query(None, description="Primer dia, inclusive"),
    to_date: Optional[date] = Query(None, description="Ultimo dia, inclusive"),
    lang: str = Query("es", pattern="^(es|en)$"),
):
    """PDF con la calidad de leche (SCC) de la granja en el periodo."""
    return await _informe_de_la_granja(
        farm_id, from_date, to_date, lang,
        obtener_resultados=lambda fid: db.get_milk_quality_results(farm_id=fid),
        preparar=preparar_datos_leche,
        url_reporting=REPORTING_MILK,
        prefijo_fichero="informe-leche",
    )
