"""
throttle.py — Capa anti-abuso / anti-bot en memoria (protege la capa gratis)
============================================================================
Estructuras ligeras (sin tocar Supabase) para evitar que un usuario o un bot
quemen peticiones y disparen el costo de la VM o agoten las cuotas free de LLM.

- SlidingWindow: N eventos por ventana de tiempo (ráfagas).
- Cooldown:      tiempo mínimo entre acciones caras (ej. notas de voz).
- DailyCounter:  tope diario por usuario (abuso sostenido de un bot).

Todo vive en RAM: O(usuarios activos), trivial para 1 GB. Se poda solo.
"""

import time
from datetime import datetime, timezone


class SlidingWindow:
    """Permite hasta `limit` eventos por `period` segundos, por clave."""

    def __init__(self):
        self._data: dict = {}

    def allow(self, key, limit: int, period: int) -> bool:
        now = time.time()
        cutoff = now - period
        q = self._data.get(key)
        if q is None:
            q = []
            self._data[key] = q
        # descarta marcas viejas
        while q and q[0] < cutoff:
            q.pop(0)
        if len(q) >= limit:
            q.append(now)  # extiende la penalización si siguen spammeando
            return False
        q.append(now)
        return True

    def count(self, key) -> int:
        return len(self._data.get(key, []))

    def prune(self, period: int):
        """Elimina usuarios sin actividad reciente (evita crecimiento de RAM)."""
        cutoff = time.time() - period
        for k in list(self._data.keys()):
            q = self._data[k]
            while q and q[0] < cutoff:
                q.pop(0)
            if not q:
                del self._data[k]


class Cooldown:
    """Exige un tiempo mínimo entre acciones por clave."""

    def __init__(self):
        self._last: dict = {}

    def check(self, key, seconds: int):
        """Devuelve (permitido, segundos_restantes)."""
        now = time.time()
        last = self._last.get(key, 0.0)
        elapsed = now - last
        if elapsed < seconds:
            return False, int(seconds - elapsed) + 1
        self._last[key] = now
        return True, 0

    def prune(self, max_age: int = 86400):
        cutoff = time.time() - max_age
        for k in list(self._last.keys()):
            if self._last[k] < cutoff:
                del self._last[k]


class DailyCounter:
    """Tope de acciones por día (UTC) por clave. Se reinicia al cambiar el día."""

    def __init__(self):
        self._data: dict = {}  # key -> [ordinal_del_dia, conteo]

    def allow(self, key, limit: int) -> bool:
        if limit <= 0:
            return True
        day = datetime.now(timezone.utc).toordinal()
        entry = self._data.get(key)
        if entry is None or entry[0] != day:
            entry = [day, 0]
        if entry[1] >= limit:
            self._data[key] = entry
            return False
        entry[1] += 1
        self._data[key] = entry
        return True

    def prune(self):
        day = datetime.now(timezone.utc).toordinal()
        for k in list(self._data.keys()):
            if self._data[k][0] != day:
                del self._data[k]
