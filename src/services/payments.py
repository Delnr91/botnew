"""
payments.py — Sistema de Pagos de Atlos
========================================
Doble pasarela: Telegram Stars (XTR) + CryptoPay (USDT).
Precio: 9 USDT/mes | Equivalente en Stars.
Automatización total: pago -> is_vip = True -> expiración 30 días.
Conectado a Supabase (Anti-Spoofing).
"""

import os
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

# --- Precio VIP ---
VIP_PRICE_USDT = 9
VIP_PRICE_STARS = 150  # ~9 USD en Stars (1 Star ≈ $0.06)
VIP_DURATION_DAYS = 60

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_payment_tables():
    """Conecta con Supabase (las tablas ya deben existir)."""
    if not supabase:
        logging.error("Supabase credentials missing in payments.py")
        return
    logging.info("💳 Sistema de pagos enlazado a Supabase.")

def activate_vip(user_id: str, days: int = VIP_DURATION_DAYS, payment_id: str = "") -> bool:
    """Activa el VIP de un usuario por N días. Guarda la fecha de expiración en Supabase."""
    if not supabase: return False
    try:
        user_id_str = str(user_id)
        expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
        
        # Actualizar user_profiles
        supabase.table('user_profiles').update({
            'is_vip': True,
            'vip_expires_at': expires_at
        }).eq('user_id', user_id_str).execute()
        
        # Registrar el pago en la tabla payments
        supabase.table('payments').insert({
            'user_id': user_id_str,
            'amount_stars': VIP_PRICE_STARS,
            'status': 'completed',
            'payment_id': payment_id
        }).execute()
        
        logging.info(f"💎 VIP activado para {user_id} hasta {expires_at}")
        return True
    except Exception as e:
        logging.error(f"Error activando VIP para {user_id}: {e}")
        return False

def check_vip_status(user_id: str) -> dict:
    """
    Verifica si el VIP del usuario sigue activo en Supabase.
    Si expiró, lo desactiva automáticamente.
    Retorna dict con 'is_vip' y 'days_left'.
    """
    if not supabase: return {"is_vip": False, "days_left": 0}
    try:
        user_id_str = str(user_id)
        res = supabase.table('user_profiles').select('is_vip', 'vip_expires_at').eq('user_id', user_id_str).execute()
        
        if not res.data:
            return {"is_vip": False, "days_left": 0}
            
        row = res.data[0]
        is_vip = row.get("is_vip", False)
        expires_at = row.get("vip_expires_at")
        
        if not is_vip or not expires_at:
            return {"is_vip": False, "days_left": 0}
            
        # Verificar expiración
        expiry_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(expiry_date.tzinfo) if expiry_date.tzinfo else datetime.utcnow()
        
        if now >= expiry_date:
            # ¡Expiró! Desactivar automáticamente
            supabase.table('user_profiles').update({
                'is_vip': False,
                'vip_expires_at': None
            }).eq('user_id', user_id_str).execute()
            
            logging.info(f"⏰ VIP expirado para {user_id}. Desactivado automáticamente.")
            return {"is_vip": False, "days_left": 0}
            
        days_left = (expiry_date - now).days
        return {"is_vip": True, "days_left": days_left}
        
    except Exception as e:
        logging.error(f"Error verificando VIP de {user_id}: {e}")
        return {"is_vip": False, "days_left": 0}
