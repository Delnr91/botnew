"""
news_engine.py — Núcleo Central de Procesamiento (ABaaS)
=======================================================
Procesa el feed global del mundo UNA sola vez por ciclo y cachea el resultado.
Los usuarios (y, a futuro, los sub-bots tenant) leen del caché y filtran
localmente por sus preferencias —SIN gastar tokens LLM extra—.

Esto desacopla el COSTO (constante: ~1 procesamiento por ciclo) del VOLUMEN
(N usuarios × N bots). Es la base económica del modelo Agent-Bot-as-a-Service.

Antes:  cada usuario → fetch + Quant + Editor   →  costo = usuarios × noticias
Ahora:  1 ciclo → fetch + dedup + Quant + Editor →  costo = noticias (fijo)
        usuarios → leen caché y filtran          →  costo LLM = 0
"""

import json
import logging
from datetime import datetime, timezone

from src.services.rss_fetcher import fetch_latest_news
from src.agents.engine import (
    quant_agent, editor_agent, psychologist_agent, detect_global_alert,
)
from src.core.cache import cache_get_json, cache_set_json, enabled as cache_enabled

# Caché central en memoria (un solo proceso orquestador)
_CACHE = {"items": [], "ts": None}
CACHE_TTL_SECONDS = 1800  # 30 min: ventana de frescura antes de reprocesar
REDIS_KEY = "atlos:news_cache"


async def load_persisted_cache() -> int:
    """Al arrancar, intenta restaurar el caché desde Redis (sobrevive reinicios)."""
    if not cache_enabled():
        return 0
    try:
        data = await cache_get_json(REDIS_KEY)
        if data and data.get("items"):
            _CACHE["items"] = data["items"]
            ts = data.get("ts")
            _CACHE["ts"] = datetime.fromisoformat(ts) if ts else None
            logging.info(f"NewsEngine: caché restaurado desde Redis ({len(data['items'])} noticias).")
            return len(data["items"])
    except Exception as e:
        logging.error(f"No se pudo restaurar caché desde Redis: {e}")
    return 0


async def _persist_cache():
    if not cache_enabled():
        return
    ts = _CACHE["ts"].isoformat() if _CACHE["ts"] else None
    await cache_set_json(REDIS_KEY, {"items": _CACHE["items"], "ts": ts}, ttl=CACHE_TTL_SECONDS)

# Tono neutro/amistoso por defecto para la redacción central (1 sola versión).
# La personalización de tono por usuario es una capa posterior y barata.
DEFAULT_TONE = psychologist_agent({})


def is_cache_fresh() -> bool:
    if not _CACHE["ts"]:
        return False
    age = (datetime.now(timezone.utc) - _CACHE["ts"]).total_seconds()
    return age < CACHE_TTL_SECONDS


def get_cached_items() -> list:
    """Copia del caché actual ya procesado."""
    return list(_CACHE["items"])


async def refresh_news_cache(clients: dict, karma_context: str = "", force: bool = False) -> list:
    """
    Procesa el mundo UNA vez: fetch → dedup → Quant (relevancia) → Editor (neutro) → caché.
    Si el caché está fresco y no se fuerza, devuelve lo cacheado sin gastar tokens.
    """
    if not force and is_cache_fresh():
        return _CACHE["items"]

    # Profundidad alta (is_vip=True) para que el caché sirva a Free y VIP por igual.
    raw = await fetch_latest_news(limit_per_feed=3, is_vip=True)

    # Deduplicación por título normalizado (varios feeds publican la misma noticia)
    seen = set()
    unique = []
    for item in raw:
        key = (item.get("title") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)

    procesadas = []
    for item in unique:
        title = item.get("title", "")
        alerta = detect_global_alert(title)

        analysis = await quant_agent(item, clients, is_vip=True)
        if not analysis["is_relevant"] and not alerta:
            continue

        # Karmalopy: reintento si la redacción sale demasiado corta
        editorial = ""
        for intento in range(2):
            extra = karma_context + (" ¡Reintento! El texto anterior era muy corto." if intento else "")
            editorial = await editor_agent(item, analysis["analysis"], extra, DEFAULT_TONE, clients)
            if len(editorial) > 50:
                break
        if not editorial:
            editorial = title

        procesadas.append({
            "title": title,
            "editorial": editorial,
            "link": item.get("link", ""),
            "category": item.get("category", "General"),
            "news_id": item.get("id", ""),
            "is_global_alert": alerta,
        })

    _CACHE["items"] = procesadas
    _CACHE["ts"] = datetime.now(timezone.utc)
    await _persist_cache()
    logging.info(f"NewsEngine: caché refrescado con {len(procesadas)} noticias procesadas "
                 f"(de {len(unique)} únicas / {len(raw)} brutas).")
    return procesadas


def select_for_user(items: list, profile: dict, limit: int) -> list:
    """
    Filtra el caché por las preferencias del usuario. Cero LLM.
    - Las alertas globales pasan SIEMPRE (override del Oráculo de Pánico).
    - El VIP puede apagar categorías desde su Panel; el Free recibe el mix por defecto.
    """
    prefs_raw = profile.get("preferences") or {}
    if isinstance(prefs_raw, str):
        try:
            prefs = json.loads(prefs_raw)
        except Exception:
            prefs = {}
    else:
        prefs = prefs_raw

    is_vip = profile.get("is_vip", False)
    # Si el VIP tiene preferencias configuradas (al menos 1 categoría activa),
    # mostrar SOLO lo que tiene en True. Si nunca abrió el panel (prefs vacío),
    # mostrar todo (comportamiento por defecto para nuevos usuarios).
    vip_has_prefs = is_vip and any(v is True for v in prefs.values())
    out = []
    for it in items:
        if it.get("is_global_alert"):
            out.append(it)
            continue
        cat = it.get("category", "General")
        if is_vip and vip_has_prefs:
            # Whitelist: solo mostrar categorías explícitamente activadas
            if not prefs.get(cat, False):
                continue
        elif is_vip:
            # Panel nunca abierto: respetar al menos los False explícitos
            if prefs.get(cat, True) is False:
                continue
        out.append(it)
    return out[:limit]
