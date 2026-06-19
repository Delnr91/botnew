import os
import logging
import json
from supabase import create_client, Client
from datetime import datetime

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_memory_db():
    if not supabase:
        logging.error("Supabase credentials missing in memory.py")
        return
    logging.info("Memoria (Karma/Agent Memory) lista en Supabase.")

def save_karma(news_id: str, user_id: str, reaction: str):
    if not supabase: return
    try:
        supabase.table('karma').insert({
            'news_id': news_id,
            'user_id': str(user_id),
            'reaction': reaction
        }).execute()
    except Exception as e:
        logging.error(f"Error guardando karma en Supabase: {e}")

def get_karma_lessons(limit: int = 10) -> str:
    if not supabase: return ""
    try:
        res = supabase.table('karma').select('news_id').eq('reaction', 'thumbs_down').order('created_at', desc=True).limit(limit).execute()
        if not res.data:
            return ""
        lessons = "El usuario ha rechazado noticias similares a los siguientes IDs: " + ", ".join([r['news_id'] for r in res.data])
        lessons += ". Evita enviar contenido con el mismo tono o temática."
        return lessons
    except Exception as e:
        logging.error(f"Error leyendo karma en Supabase: {e}")
        return ""

def get_or_create_user_profile(user_id: str, username: str = "") -> dict:
    if not supabase: 
        return {"user_id": user_id, "username": username, "is_vip": False, "city": None, "preferences": {}}
    try:
        user_id_str = str(user_id)
        res = supabase.table('user_profiles').select('*').eq('user_id', user_id_str).execute()
        
        # Update last active
        if res.data:
            supabase.table('user_profiles').update({'last_active_at': datetime.utcnow().isoformat()}).eq('user_id', user_id_str).execute()
            row = res.data[0]
            if isinstance(row.get('preferences'), str):
                try: row['preferences'] = json.loads(row['preferences'])
                except: row['preferences'] = {}
            return row
            
        default_prefs = {"Criptomonedas": True, "Geopolítica y Guerra": True, "Deep Tech e IA": True, "Mercados y Wall Street": True, "Deportes": True, "Astronomía y Ciencia": True, "Entretenimiento y Cultura": True, "Salud y Bienestar": True, "Viajes y Estilo de Vida": True, "Videojuegos y E-Sports": True, "Clima y Sostenibilidad": True, "Startups y Negocios": True, "Motor y Automovilismo": True}
        
        new_user = {
            'user_id': user_id_str,
            'city': None,
            'age': None,
            'gender': None,
            'preferences': default_prefs,
            'is_vip': False,
            'last_active_at': datetime.utcnow().isoformat()
        }
        res_insert = supabase.table('user_profiles').insert(new_user).execute()
        if res_insert.data:
            return res_insert.data[0]
        return new_user
        
    except Exception as e:
        logging.error(f"Error en perfil de usuario (Supabase): {e}")
        return {"user_id": user_id, "username": username, "is_vip": False, "city": None, "preferences": {}}

def update_user_vip_status(user_id: str, is_vip: bool):
    if not supabase: return
    try:
        supabase.table('user_profiles').update({'is_vip': is_vip}).eq('user_id', str(user_id)).execute()
    except Exception as e:
        logging.error(f"Error actualizando VIP status: {e}")

def update_user_location(user_id: str, location: str):
    if not supabase: return
    try:
        supabase.table('user_profiles').update({'city': location}).eq('user_id', str(user_id)).execute()
    except Exception as e:
        logging.error(f"Error actualizando ubicación: {e}")

def update_user_demographics(user_id: str, age: int, gender: str):
    if not supabase: return
    try:
        supabase.table('user_profiles').update({'age': age, 'gender': gender}).eq('user_id', str(user_id)).execute()
    except Exception as e:
        logging.error(f"Error actualizando demografía: {e}")

def get_user_preferences(user_id: str) -> dict:
    profile = get_or_create_user_profile(user_id)
    prefs = profile.get('preferences', {})
    if isinstance(prefs, str):
        try: return json.loads(prefs)
        except: return {}
    return prefs

def update_user_preferences(user_id: str, prefs_dict: dict):
    if not supabase: return
    try:
        supabase.table('user_profiles').update({'preferences': prefs_dict}).eq('user_id', str(user_id)).execute()
    except Exception as e:
        logging.error(f"Error actualizando preferencias: {e}")

def get_all_users() -> list:
    if not supabase: return []
    try:
        res = supabase.table('user_profiles').select('user_id', 'is_vip').execute()
        return res.data
    except Exception as e:
        logging.error(f"Error obteniendo usuarios: {e}")
        return []
