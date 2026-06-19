"""
payments.py — Sistema de Pagos de Atlos
========================================
Doble pasarela: Telegram Stars (XTR) + CryptoPay (USDT).
Precio: 9 USDT/mes | Equivalente en Stars.
Automatización total: pago → is_vip = True → expiración 30 días.
"""

import os
import logging
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")

# --- Precio VIP ---
VIP_PRICE_USDT = 9
VIP_PRICE_STARS = 150  # ~9 USD en Stars (1 Star ≈ $0.06)
VIP_DURATION_DAYS = 60

# ---------------------------------------------------------------------------
# 1. ACTIVACIÓN Y VERIFICACIÓN VIP
# ---------------------------------------------------------------------------

def activate_vip(user_id: str, days: int = VIP_DURATION_DAYS, payment_id: str = "") -> bool:
    """Activa el VIP de un usuario por N días. Guarda la fecha de expiración."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        expires_at = (datetime.now() + timedelta(days=days)).isoformat()
        
        cursor.execute(
            "UPDATE user_profiles SET is_vip = 1, vip_expires_at = ? WHERE user_id = ?",
            (expires_at, user_id)
        )
        
        # Registrar el pago en el historial
        cursor.execute('''
            INSERT INTO payment_history (user_id, amount, currency, payment_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, VIP_PRICE_USDT, "USDT", payment_id, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        logging.info(f"💎 VIP activado para {user_id} hasta {expires_at}")
        return True
    except Exception as e:
        logging.error(f"Error activando VIP para {user_id}: {e}")
        return False

def check_vip_status(user_id: str) -> dict:
    """
    Verifica si el VIP del usuario sigue activo.
    Si expiró, lo desactiva automáticamente.
    Retorna dict con 'is_vip' y 'days_left'.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT is_vip, vip_expires_at FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"is_vip": False, "days_left": 0}
        
        is_vip = bool(row["is_vip"])
        expires_at = row["vip_expires_at"]
        
        if not is_vip or not expires_at:
            conn.close()
            return {"is_vip": False, "days_left": 0}
        
        # Verificar expiración
        expiry_date = datetime.fromisoformat(expires_at)
        now = datetime.now()
        
        if now >= expiry_date:
            # ¡Expiró! Desactivar automáticamente
            cursor.execute("UPDATE user_profiles SET is_vip = 0, vip_expires_at = NULL WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            logging.info(f"⏰ VIP expirado para {user_id}. Desactivado automáticamente.")
            return {"is_vip": False, "days_left": 0}
        
        days_left = (expiry_date - now).days
        conn.close()
        return {"is_vip": True, "days_left": days_left}
        
    except Exception as e:
        logging.error(f"Error verificando VIP de {user_id}: {e}")
        return {"is_vip": False, "days_left": 0}

def init_payment_tables():
    """Crea las tablas necesarias para el sistema de pagos."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Historial de pagos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                amount REAL,
                currency TEXT,
                payment_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Añadir columna vip_expires_at si no existe
        try:
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN vip_expires_at TEXT")
            logging.info("Columna vip_expires_at añadida a user_profiles.")
        except sqlite3.OperationalError:
            pass  # Ya existe la columna
        
        conn.commit()
        conn.close()
        logging.info("💳 Sistema de pagos inicializado.")
    except Exception as e:
        logging.error(f"Error inicializando tablas de pago: {e}")
