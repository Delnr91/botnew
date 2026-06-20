"""
voice.py — Voz de salida (Text-to-Speech) con Edge-TTS (gratis, sin API key)
===========================================================================
Convierte las respuestas de Atlos en audio para que el VIP "escuche" a la IA,
no solo la lea. Edge-TTS usa los servidores de voz neuronal de Microsoft de
forma gratuita y sin clave. Es ligero: solo una petición HTTP por síntesis.

Feature-flag: si la librería edge-tts no está instalada, queda inactivo y el
bot sigue respondiendo en texto.
"""

import os
import logging

try:
    import edge_tts  # type: ignore
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False

# Voz neuronal en español (masculina, neutra LATAM). Configurable por entorno.
VOICE = os.getenv("TTS_VOICE", "es-MX-JorgeNeural")
MAX_TTS_CHARS = 900  # límite prudente para no generar audios eternos


def tts_available() -> bool:
    return _AVAILABLE


async def text_to_speech(text: str, out_path: str) -> str:
    """Sintetiza `text` a un archivo MP3 en out_path. Devuelve la ruta o "" si falla."""
    if not _AVAILABLE or not text:
        return ""
    clean = text.strip()[:MAX_TTS_CHARS]
    try:
        communicate = edge_tts.Communicate(clean, VOICE)
        await communicate.save(out_path)
        return out_path
    except Exception as e:
        logging.error(f"Error en TTS (Edge): {e}")
        return ""
