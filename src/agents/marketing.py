import os
import logging
from datetime import datetime
from groq import AsyncGroq
from src.core.database import supabase

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

async def generate_marketing_campaign() -> str:
    """Extrae las noticias top de la semana y crea una campaña viral para RRSS."""
    if not GROQ_API_KEY:
        return "⚠️ GROQ_API_KEY no configurada. No puedo generar la campaña."
        
    client = AsyncGroq(api_key=GROQ_API_KEY)
    
    # 1. Extraer contexto (Últimas noticias de Supabase para usarlas de gancho)
    news_context = ""
    try:
        if supabase:
            res = supabase.table('sent_news').select('title', 'source').order('published_at', desc=True).limit(5).execute()
            for row in res.data:
                news_context += f"- {row['title']} ({row['source']})\n"
    except Exception as e:
        logging.error(f"Error extrayendo noticias para marketing: {e}")
        
    if not news_context:
        news_context = "Bitcoin supera expectativas, la IA automatiza empleos y la geopolítica está tensa."

    prompt = f"""
Eres un experto CMO (Chief Marketing Officer) de Silicon Valley especializado en Growth Hacking para Startups de IA.
El producto a promocionar es 'Atlos', un bot ecosistema en Telegram que entrega información ultra filtrada sobre Cripto, Bolsa, Clima, IA y Geopolítica 24/7.
Precio: Freemium (Gratis con opción VIP de $9/mes).
Link de conversión: t.me/AtlosBot

NOTICIAS RECIENTES PARA USAR COMO 'HOOKS' (Ganchos):
{news_context}

Tu misión es entregar una campaña viral lista para copiar y pegar esta semana. Usa un tono persuasivo, tecnológico y urgente. El color oficial de la marca es 'Celadon' (Verde pálido).

Genera EXACTAMENTE este formato:

📱 **TWEET VIRAL (HILO)**
[Escribe un hilo de 3 tweets que cause FOMO y urgencia. Usa las noticias reales como gancho]

📸 **INSTAGRAM REEL / TIKTOK (GUION 15s)**
[Escribe el guion de voz en off ultra rápido y qué mostrar en pantalla. CTA claro al link de la bio]

🖼️ **CARRUSEL DE INSTAGRAM (TEXTO)**
[Escribe el copy de la descripción. Breve, con emojis y 5 hashtags potentes.]
"""
    try:
        response = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192",
            temperature=0.7,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error(f"Error generando campaña: {e}")
        return "⚠️ Error al generar la campaña publicitaria. Revisa los logs."
