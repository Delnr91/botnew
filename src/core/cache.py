"""
cache.py — Caché distribuido opcional vía Upstash Redis (REST, capa gratis)
==========================================================================
Permite que el caché del NewsEngine SOBREVIVA reinicios del bot (clave en una
VM de 1 GB que se reinicia). Usa la API REST de Upstash sobre aiohttp, así que
NO añade dependencias pesadas ni conexiones persistentes.

Feature-flag: si no hay UPSTASH_REDIS_REST_URL/TOKEN, todo queda inactivo y el
NewsEngine usa solo memoria (comportamiento previo).
"""

import os
import json
import logging
import aiohttp

_URL = os.getenv("UPSTASH_REDIS_REST_URL")
_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")


def enabled() -> bool:
    return bool(_URL and _TOKEN)


async def _cmd(*args):
    if not enabled():
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                _URL,
                json=list(args),
                headers={"Authorization": f"Bearer {_TOKEN}"},
                timeout=10,
            ) as resp:
                data = await resp.json()
                return data.get("result")
    except Exception as e:
        logging.error(f"Upstash error ({args[0] if args else '?'}): {e}")
        return None


async def cache_get_json(key: str):
    res = await _cmd("GET", key)
    if not res:
        return None
    try:
        return json.loads(res)
    except Exception:
        return None


async def cache_set_json(key: str, value, ttl: int = 3600) -> bool:
    payload = json.dumps(value, ensure_ascii=False)
    res = await _cmd("SET", key, payload, "EX", str(ttl))
    return res is not None
