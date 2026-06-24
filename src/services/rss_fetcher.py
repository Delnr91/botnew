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
        "https://techcrunch.com/feed/",
        "https://www.wired.com/feed/rss",
        "https://www.reddit.com/r/artificial/top.rss?t=day"
    ],
    "Geopolítica y Guerra": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "https://www.reddit.com/r/geopolitics/top.rss?t=day"
    ],
    "Criptomonedas": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://cryptonews.com/news/feed/"
    ],
    "Mercados y Wall Street": [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://www.investing.com/rss/news_25.rss",
        "https://www.reddit.com/r/wallstreetbets/top.rss?t=day"
    ],
    "Deportes": [
        "https://e00-marca.uecdn.es/rss/futbol/primera-division.xml",
        "https://www.espn.com/espn/rss/news",
        "https://sports.yahoo.com/rss/"
    ],
    "Astronomía y Ciencia": [
        "https://www.space.com/feeds/all",
        "https://www.sciencenews.org/feed"
    ],
    "Entretenimiento y Cultura": [
        "https://variety.com/feed/",
        "https://www.hollywoodreporter.com/feed/"
    ],
    "Salud y Bienestar": [
        "https://www.medicalnewstoday.com/feed",
        "https://www.healthline.com/rss"
    ],
    "Viajes y Estilo de Vida": [
        "https://www.lonelyplanet.com/news/feed"
    ],
    "Videojuegos y E-Sports": [
        "https://feeds.feedburner.com/ign/all",
        "https://www.polygon.com/rss/index.xml"
    ],
    "Clima y Sostenibilidad": [
        "https://www.nationalgeographic.com/environment/rss" # Reemplazar después si es de pago
    ],
    "Startups y Negocios": [
        "https://www.entrepreneur.com/latest.rss",
        "https://feeds.feedburner.com/TechCrunch/startups"
    ],
    "Motor y Automovilismo": [
        "https://www.motorsport.com/rss/f1/news/",
        "https://www.autoblog.com/rss.xml"
    ]
}

import random

async def fetch_rss_feed(url: str, category: str, limit: int = 2) -> List[Dict]:
    """Obtiene noticias de un feed RSS de forma asíncrona."""
    news_list = []
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'application/rss+xml, application/xml;q=0.9, */*;q=0.8'
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
    # Lanzar peticiones con un pequeño desfase para no saturar Reddit (Rate Limit)
    for i, (category, urls) in enumerate(RSS_FEEDS.items()):
        for url in urls:
            tasks.append(fetch_rss_feed(url, category, limit=fetch_limit))
            
    # Ejecutamos en lotes de 3 para no golpear la misma IP 25 veces por segundo
    batch_size = 3
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        results = await asyncio.gather(*batch)
        for result_list in results:
            all_news.extend(result_list)
        await asyncio.sleep(1) # Pausa de 1 seg entre lotes
        
    return all_news
