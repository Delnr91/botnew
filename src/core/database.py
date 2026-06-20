import os
import logging
from supabase import create_client, Client
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
# Cargamos env si es necesario (ya se carga en main.py)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_db():
    """Conecta a Supabase y verifica la conexión."""
    if not supabase:
        logging.error("No se pudo inicializar Supabase. Faltan credenciales en .env")
        return
    try:
        # Hacemos una petición ligera para verificar conexión
        supabase.table('sent_news').select('id', count='exact').limit(1).execute()
        logging.info("Base de datos conectada correctamente a Supabase.")
    except Exception as e:
        logging.error(f"Error conectando a Supabase: {e}")

def is_news_sent(news_id: str, user_id: str = None) -> bool:
    """Verifica en Supabase si la noticia ya fue enviada a ese usuario."""
    if not supabase: return False
    try:
        record_id = f"{news_id}_{user_id}" if user_id else news_id
        response = supabase.table('sent_news').select('id').eq('id', record_id).execute()
        return len(response.data) > 0
    except Exception as e:
        logging.error(f"Error comprobando is_news_sent en Supabase: {e}")
        return False

def mark_news_as_sent(news_id: str, title: str, source: str, user_id: str = None):
    """Guarda en Supabase que la noticia fue enviada a ese usuario."""
    if not supabase: return
    try:
        record_id = f"{news_id}_{user_id}" if user_id else news_id
        supabase.table('sent_news').insert({
            'id': record_id[:250], # Límite por si el URL es muy largo
            'title': title[:250],
            'source': source[:100]
        }).execute()
    except Exception as e:
        logging.error(f"Error marcando noticia como enviada en Supabase: {e}")

def cleanup_old_records():
    """El Conserje: Borra noticias viejas y usuarios inactivos en Supabase."""
    if not supabase: return
    try:
        # 1. Borrar noticias de más de 7 días
        limit_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        supabase.table('sent_news').delete().lt('published_at', limit_date).execute()
        logging.info("Conserje: Noticias antiguas eliminadas.")
        
        # 2. Borrar usuarios inactivos de más de 60 días
        inactive_date = (datetime.utcnow() - timedelta(days=60)).isoformat()
        supabase.table('user_profiles').delete().lt('last_active_at', inactive_date).execute()
        logging.info("Conserje: Cuentas inactivas eliminadas para optimizar DB.")
        
    except Exception as e:
        logging.error(f"Error en cleanup_old_records (Supabase): {e}")
