import sqlite3
import os
import logging

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")

def init_memory_db():
    """Inicializa las tablas de memoria (Karma y Compresión Semántica)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Tabla de Karma (Reacciones del usuario)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS karma (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id TEXT,
                user_id TEXT,
                reaction TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de Memoria a Largo Plazo (Resúmenes comprimidos de la semana)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week TEXT,
                summary TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de Perfiles de Usuario (Para Onboarding sin registro y Status VIP)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                is_vip BOOLEAN DEFAULT 0,
                location TEXT,
                preferences TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logging.info("Memoria (Karma/Agent Memory) inicializada correctamente.")
    except Exception as e:
        logging.error(f"Error inicializando memoria: {e}")

def save_karma(news_id: str, user_id: str, reaction: str):
    """Guarda una reacción (thumbs_up / thumbs_down) en el Karma."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO karma (news_id, user_id, reaction) VALUES (?, ?, ?)",
            (news_id, user_id, reaction)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error guardando karma: {e}")

def get_karma_lessons(limit: int = 10) -> str:
    """Obtiene las lecciones aprendidas (reacciones negativas) para retroalimentar al LLM."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT news_id FROM karma WHERE reaction = 'thumbs_down' ORDER BY created_at DESC LIMIT ?", 
            (limit,)
        )
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return ""
            
        lessons = "El usuario ha rechazado noticias similares a los siguientes IDs: " + ", ".join([r[0] for r in results])
        lessons += ". Evita enviar contenido con el mismo tono o temática."
        return lessons
    except Exception as e:
        logging.error(f"Error leyendo karma: {e}")
        return ""

def save_weekly_summary(week_label: str, summary: str):
    """Guarda la memoria comprimida de la semana."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO agent_memory (week, summary) VALUES (?, ?)",
            (week_label, summary)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error guardando resumen semanal: {e}")

def get_recent_memory(weeks: int = 4) -> str:
    """Devuelve la memoria histórica reciente."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT week, summary FROM agent_memory ORDER BY created_at DESC LIMIT ?", 
            (weeks,)
        )
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return ""
            
        memory = "Contexto histórico de las últimas semanas:\n"
        for row in results:
            memory += f"- Semana {row[0]}: {row[1]}\n"
        return memory
    except Exception as e:
        logging.error(f"Error leyendo memoria: {e}")
        return ""

def get_or_create_user_profile(user_id: str, username: str = "") -> dict:
    """Obtiene el perfil del usuario o lo crea si no existe (Onboarding Invisible)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if row:
            conn.close()
            return dict(row)
            
        # Si no existe, lo creamos con todas las categorías activadas por defecto
        default_prefs = '{"Criptomonedas": true, "Geopolítica y Guerra": true, "Deep Tech e IA": true, "Mercados y Wall Street": true, "Deportes": true, "Astronomía y Ciencia": true, "Entretenimiento y Cultura": true, "Salud y Bienestar": true, "Viajes y Estilo de Vida": true, "Videojuegos y E-Sports": true, "Clima y Sostenibilidad": true, "Startups y Negocios": true, "Motor y Automovilismo": true}'
        cursor.execute(
            "INSERT INTO user_profiles (user_id, username, is_vip, preferences) VALUES (?, ?, 0, ?)",
            (user_id, username, default_prefs)
        )
        conn.commit()
        
        # Volvemos a leerlo
        cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
        new_row = cursor.fetchone()
        conn.close()
        return dict(new_row)
        
    except Exception as e:
        logging.error(f"Error en perfil de usuario: {e}")
        return {"user_id": user_id, "username": username, "is_vip": False, "location": None, "preferences": ""}

def update_user_vip_status(user_id: str, is_vip: bool):
    """Actualiza el estado VIP del usuario (Ej: tras recibir un pago)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_profiles SET is_vip = ? WHERE user_id = ?", (int(is_vip), user_id))
        conn.commit()
        conn.close()
        logging.info(f"Usuario {user_id} VIP status cambiado a {is_vip}.")
    except Exception as e:
        logging.error(f"Error actualizando VIP status: {e}")

def update_user_location(user_id: str, location: str):
    """Guarda la ubicación del usuario para el Agente Meteorólogo."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE user_profiles SET location = ? WHERE user_id = ?", (location, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error actualizando ubicación: {e}")

import json

def get_user_preferences(user_id: str) -> dict:
    """Devuelve las preferencias del usuario como diccionario JSON."""
    profile = get_or_create_user_profile(user_id)
    prefs_str = profile.get('preferences', '')
    try:
        if not prefs_str:
            return {}
        return json.loads(prefs_str)
    except:
        return {}

def update_user_preferences(user_id: str, prefs_dict: dict):
    """Guarda las preferencias del usuario."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        prefs_str = json.dumps(prefs_dict)
        cursor.execute("UPDATE user_profiles SET preferences = ? WHERE user_id = ?", (prefs_str, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error actualizando preferencias: {e}")

def get_all_users() -> list:
    """Obtiene todos los usuarios de la base de datos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, is_vip FROM user_profiles")
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users
    except Exception as e:
        logging.error(f"Error obteniendo usuarios: {e}")
        return []
