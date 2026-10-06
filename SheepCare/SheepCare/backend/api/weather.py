"""
Weather API - tiempo y estres termico (THI) por granja, via OpenAgri Weather Service.

Weather es un proceso local aparte (puerto WEATHER_API_URL) que solo escucha en
127.0.0.1. Este router hace de intermediario para el navegador:

  1. Lee las coordenadas de la granja de SQLite. Nunca vienen del cliente.
  2. Comprueba que el usuario haya guardado su clave de OpenWeatherMap.
  3. Firma un token de servicio de vida corta con WEATHER_JWT_KEY y llama a
     Weather con lat/lon. Weather solo valida la firma.

Misma API y mismas respuestas que la version cloud (/api/weather/farms/{id}/...).
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

import httpx
import jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..data_access.db_manager import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()
db = DatabaseManager()

WEATHER_API_URL = os.environ.get("WEATHER_API_URL", "http://127.0.0.1:8003").rstrip("/")
WEATHER_JWT_KEY = os.environ.get("WEATHER_JWT_KEY", "")
WEATHER_API_KEY_SETTING = "weather_openweathermap_api_key"

# Debe cubrir la primera peticion a una ubicacion nueva: Weather llama a
# OpenWeatherMap y guarda el resultado antes de responder.
WEATHER_TIMEOUT = 20.0

# Umbrales de THI para ganado, los mismos por defecto que usa Weather
# (src/utils.py: `thi >= umbral`) y la version cloud.
UMBRALES_THI = (
    (89.0, "critico"),
    (84.0, "severo"),
    (79.0, "moderado"),
    (72.0, "leve"),
)


def nivel_thi(thi: float) -> str:
    for umbral, nivel in UMBRALES_THI:
        if thi >= umbral:
            return nivel
    return "sin_estres"


class RespuestaTHI(BaseModel):
    farm_id: int
    latitude: float
    longitude: float
    thi: float
    level: str  # sin_estres | leve | moderado | severo | critico


class PuntoPrevision(BaseModel):
    """Un instante de la prevision (cada 3 h), con el THI calculado."""

    timestamp: str
    temperature: Optional[float] = None  # grados C
    humidity: Optional[float] = None  # %
    wind_speed: Optional[float] = None  # m/s
    rain_probability: Optional[float] = None  # 0-1
    rain_mm_3h: Optional[float] = None  # mm; solo si se espera lluvia
    thi: Optional[float] = None  # None si falta temperatura o humedad
    level: Optional[str] = None


class RespuestaPrevision(BaseModel):
    farm_id: int
    latitude: float
    longitude: float
    forecast: List[PuntoPrevision]


# Weather devuelve una fila por instante Y magnitud; aqui se agrupan por
# instante. Nombres de `measurement_type` tal como los emite Weather.
_MAGNITUDES = {
    "ambient_temperature": "temperature",
    "ambient_humidity": "humidity",
    "wind_speed": "wind_speed",
    "precipitation": "rain_probability",
    "rainfall_3h": "rain_mm_3h",
}


def calcular_thi(temperatura: float, humedad: float) -> float:
    """Misma formula que Weather (src/utils.py: calculate_thi)."""
    return round(0.8 * temperatura + (humedad / 100) * (temperatura - 14.4) + 46.4, 2)


def _a_utc(marca: str) -> str:
    """Instante en ISO con zona explicita (`...Z`).

    Weather devuelve `...Z` la primera vez y `...` SIN zona cuando el dato sale
    de su cache (fechas ingenuas en UTC). Un navegador interpretaria la segunda
    forma como hora local y desplazaria la prevision.
    """
    dt = datetime.fromisoformat(marca.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def agrupar_prevision(puntos: list) -> List[PuntoPrevision]:
    por_instante: dict = {}
    for p in puntos:
        campo = _MAGNITUDES.get(p.get("measurement_type"))
        if campo is None:
            continue  # p. ej. wind_direction: no se muestra
        por_instante.setdefault(_a_utc(p["timestamp"]), {})[campo] = p["value"]

    filas = []
    for ts in sorted(por_instante):
        v = por_instante[ts]
        thi = None
        if "temperature" in v and "humidity" in v:
            thi = calcular_thi(v["temperature"], v["humidity"])
        filas.append(
            PuntoPrevision(
                timestamp=ts, thi=thi, level=nivel_thi(thi) if thi is not None else None, **v
            )
        )
    return filas


def _token_de_servicio() -> str:
    if not WEATHER_JWT_KEY:
        raise HTTPException(503, "Servicio meteorológico no configurado")
    ahora = int(time.time())
    # Vida corta: se firma uno por peticion, no hace falta reutilizarlo.
    return jwt.encode(
        {"sub": "sheepcare-local", "iat": ahora, "exp": ahora + 60},
        WEATHER_JWT_KEY,
        algorithm="HS256",
    )


def _coordenadas_de_la_granja(farm_id: int) -> tuple:
    """(latitude, longitude) de la granja, o la HTTPException que corresponda."""
    granja = db.get_farm(farm_id)
    if not granja:
        raise HTTPException(404, "Granja no encontrada")
    lat, lon = granja.get("latitude"), granja.get("longitude")
    if lat is None or lon is None:
        raise HTTPException(409, "La granja no tiene coordenadas. Añádelas editando la granja.")
    return float(lat), float(lon)


def _exigir_clave() -> None:
    if not db.get_setting(WEATHER_API_KEY_SETTING):
        raise HTTPException(
            409, "Falta la clave de OpenWeatherMap. Añádela en Ajustes."
        )


async def _llamar_a_weather(ruta: str, lat: float, lon: float):
    try:
        async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT) as cliente:
            r = await cliente.get(
                f"{WEATHER_API_URL}{ruta}",
                params={"lat": lat, "lon": lon},
                headers={"Authorization": f"Bearer {_token_de_servicio()}"},
            )
    except httpx.RequestError as exc:
        logger.error("Weather no responde (%s): %s", ruta, exc)
        raise HTTPException(503, "Servicio meteorológico no disponible")

    if r.status_code != 200:
        # Weather devuelve 500 sin detalle cuando OpenWeatherMap falla (clave
        # invalida, limite de uso agotado...). El motivo real esta en su log.
        logger.error("Weather devolvio %s en %s: %s", r.status_code, ruta, r.text[:200])
        raise HTTPException(502, "El servicio meteorológico no pudo obtener los datos")
    return r.json()


@router.get("/farms/{farm_id}/thi", response_model=RespuestaTHI)
async def thi_de_la_granja(farm_id: int):
    """Indice de estres termico actual de la granja."""
    lat, lon = _coordenadas_de_la_granja(farm_id)
    _exigir_clave()
    datos = await _llamar_a_weather("/api/data/thi/", lat, lon)
    thi = datos.get("thi")
    if thi is None:
        raise HTTPException(502, "Respuesta inesperada del servicio meteorológico")
    return RespuestaTHI(
        farm_id=farm_id, latitude=lat, longitude=lon, thi=thi, level=nivel_thi(thi)
    )


@router.get("/farms/{farm_id}/forecast", response_model=RespuestaPrevision)
async def prevision_de_la_granja(farm_id: int):
    """Prevision a 5 dias de la granja: un punto cada 3 h, con el THI previsto."""
    lat, lon = _coordenadas_de_la_granja(farm_id)
    _exigir_clave()
    puntos = await _llamar_a_weather("/api/data/forecast5/", lat, lon)
    if not isinstance(puntos, list):
        raise HTTPException(502, "Respuesta inesperada del servicio meteorológico")
    return RespuestaPrevision(
        farm_id=farm_id, latitude=lat, longitude=lon, forecast=agrupar_prevision(puntos)
    )
