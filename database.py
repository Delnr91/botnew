import sqlite3
import os
import logging

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")

def init_db():
    """Inicializa la base de datos y crea la tabla si no existe."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_news (
                id TEXT PRIMARY KEY,
                title TEXT,
                source TEXT,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logging.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logging.error(f"Error inicializando la base de datos: {e}")

def is_news_sent(news_id: str) -> bool:
    """Verifica si una noticia ya fue enviada."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sent_news WHERE id = ?", (news_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        logging.error(f"Error verificando noticia en BD: {e}")
        return False

def mark_news_as_sent(news_id: str, title: str, source: str):
    """Guarda la noticia en la base de datos para no repetirla."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sent_news (id, title, source) VALUES (?, ?, ?)",
            (news_id, title, source)
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        pass # Ya existe
    except Exception as e:
        logging.error(f"Error guardando noticia en BD: {e}")

def cleanup_old_records(days: int = 30):
    """
    Agente de limpieza: Borra las noticias más antiguas que 'days' días
    para mantener la base de datos ligera.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM sent_news WHERE published_at <= date('now', ?)", 
            (f"-{days} days",)
        )
        deleted_rows = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted_rows > 0:
            logging.info(f"Agente de limpieza: Borrados {deleted_rows} registros antiguos.")
    except Exception as e:
        logging.error(f"Error en el agente de limpieza de BD: {e}")

