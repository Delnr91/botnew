from deep_translator import GoogleTranslator
import logging

def translate_to_spanish(text: str) -> str:
    """Traduce texto de cualquier idioma (autodetectado) a español."""
    if not text:
        return ""
    try:
        # Usamos GoogleTranslator que es gratuito y no requiere API Key
        translated = GoogleTranslator(source='auto', target='es').translate(text)
        return translated
    except Exception as e:
        logging.error(f"Error en la traducción: {e}")
        # Si falla, devolvemos el texto original para no perder la noticia
        return text
