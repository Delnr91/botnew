import aiohttp
import logging
import feedparser
from typing import List, Dict
import asyncio

# ---------------------------------------------------------------------------
# EL RADAR OMNISCIENTE (100% Gratis, Límite Infinito vía RSS/Reddit)
# ---------------------------------------------------------------------------

RSS_FEEDS = {
    "Deep Tech e IA": [
        "https://www.reddit.com/r/artificial/top.rss?t=day",
        "https://www.reddit.com/r/technology/top.rss?t=day",
        "https://techcrunch.com/feed/"
    ],
    "Geopolítica y Guerra": [
        "https://www.reddit.com/r/worldnews/top.rss?t=day",
        "https://www.reddit.com/r/geopolitics/top.rss?t=day"
    ],
    "Criptomonedas": [
        "https://www.reddit.com/r/CryptoCurrency/top.rss?t=day",
        "https://cointelegraph.com/rss"
    ],
    "Mercados y Wall Street": [
        "https://www.reddit.com/r/wallstreetbets/top.rss?t=day",
        "https://www.reddit.com/r/investing/top.rss?t=day"
    ],
    "Deportes": [
        "https://www.reddit.com/r/sports/top.rss?t=day",
        "https://www.espn.com/espn/rss/news"
    ],
    "Astronomía y Ciencia": [
        "https://www.reddit.com/r/space/top.rss?t=day",
        "https://www.reddit.com/r/science/top.rss?t=day"
    ],
    "Entretenimiento y Cultura": [
        "https://www.reddit.com/r/movies/top.rss?t=day",
        "https://www.reddit.com/r/television/top.rss?t=day"
    ],
    "Salud y Bienestar": [
        "https://www.reddit.com/r/Health/top.rss?t=day",
        "https://www.reddit.com/r/biohackers/top.rss?t=day"
    ],
    "Viajes y Estilo de Vida": [
        "https://www.reddit.com/r/travel/top.rss?t=day"
    ],
    "Videojuegos y E-Sports": [
        "https://www.reddit.com/r/gaming/top.rss?t=day",
        "https://www.reddit.com/r/esports/top.rss?t=day"
    ],
    "Clima y Sostenibilidad": [
        "https://www.reddit.com/r/environment/top.rss?t=day"
    ],
    "Startups y Negocios": [
        "https://www.reddit.com/r/Entrepreneur/top.rss?t=day",
        "https://www.reddit.com/r/startups/top.rss?t=day"
    ],
    "Motor y Automovilismo": [
        "https://www.reddit.com/r/formula1/top.rss?t=day",
        "https://www.reddit.com/r/cars/top.rss?t=day"
    ]
}

async def fetch_rss_feed(url: str, category: str, limit: int = 2) -> List[Dict]:
    """Obtiene noticias de un feed RSS de forma asíncrona."""
    news_list = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    xml_content = await resp.text()
                    # Parsear el XML en un hilo separado para no bloquear el loop
                    feed = await asyncio.to_thread(feedparser.parse, xml_content)
                    
                    for item in feed.entries[:limit]:
                        # Reddit incluye mucho HTML en el summary, el Agente Quant lo limpiará
                        news_list.append({
                            "id": f"rss_{hash(item.link)}",
                            "title": item.title,
                            "summary": getattr(item, 'description', getattr(item, 'summary', "Sin detalle")),
                            "link": item.link,
                            "category": category
                        })
                elif resp.status == 429:
                    logging.warning(f"Rate limit en {url}")
                else:
                    logging.error(f"Error {resp.status} fetching {url}")
    except Exception as e:
        logging.error(f"Error fetching RSS {url}: {e}")
        
    return news_list

async def fetch_latest_news(limit_per_feed: int = 2, is_vip: bool = False) -> List[Dict]:
    """
    Rastrea todas las fuentes de información del mundo de forma simultánea.
    Si el usuario es VIP, el límite de profundidad es mayor.
    """
    logging.info("Scout Agent: Activando Radar Omnisciente (Reddit, Tech, Geo, Mercados)...")
    all_news = []
    
    # VIP lee más profundo en los subreddits (Top 4 del día vs Top 1 del día)
    fetch_limit = 4 if is_vip else 1
    
    tasks = []
    # Lanzar todas las peticiones asíncronas en paralelo para máxima velocidad
    for category, urls in RSS_FEEDS.items():
        for url in urls:
            tasks.append(fetch_rss_feed(url, category, limit=fetch_limit))
            
    # Esperar a que todos los Scouters vuelvan con la info
    results = await asyncio.gather(*tasks)
    
    # Aplanar la lista de listas
    for result_list in results:
        all_news.extend(result_list)
        
    return all_news
