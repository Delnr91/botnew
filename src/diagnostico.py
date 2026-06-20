"""
Script de Diagnóstico — Prueba los feeds RSS y el pipeline de noticias.
Ejecutar: python -m src.diagnostico
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.services.rss_fetcher import fetch_latest_news, fetch_rss_feed
from src.core.database import init_db, is_news_sent

async def main():
    print("=" * 60)
    print("DIAGNOSTICO DE FEEDS RSS")
    print("=" * 60)
    
    print("\nTest 1: Fetching ALL RSS feeds (como VIP)...")
    try:
        news = await fetch_latest_news(limit_per_feed=2, is_vip=True)
        print(f"   ✅ Total noticias obtenidas: {len(news)}")
        
        # Agrupar por categoría
        cats = {}
        for item in news:
            cat = item.get('category', 'Sin cat')
            cats[cat] = cats.get(cat, 0) + 1
        
        print("\n   📊 Noticias por categoría:")
        for cat, count in sorted(cats.items()):
            print(f"      • {cat}: {count} noticias")
            
    except Exception as e:
        print(f"   ❌ ERROR fetching news: {e}")
        return
    
    # Test 2: Verificar cuántas ya fueron enviadas
    print("\n📦 Test 2: Verificando noticias ya enviadas...")
    init_db()
    
    nuevas = 0
    ya_enviadas = 0
    for item in news:
        if is_news_sent(item['id']):
            ya_enviadas += 1
        else:
            nuevas += 1
    
    print(f"   📬 Noticias NUEVAS (no enviadas): {nuevas}")
    print(f"   📭 Noticias YA ENVIADAS: {ya_enviadas}")
    
    # Test 3: Mostrar los primeros títulos nuevos
    if nuevas > 0:
        print("\n📰 Primeras 5 noticias NUEVAS:")
        count = 0
        for item in news:
            if not is_news_sent(item['id']) and count < 5:
                print(f"   [{item['category']}] {item['title'][:80]}")
                count += 1
    else:
        print("\n   ⚠️ TODAS las noticias ya fueron enviadas.")
        print("   💡 Esto explica por qué dice 'silencio'. Espera a que se publiquen nuevas.")
    
    # Test 4: Test individual de un feed
    print("\n🧪 Test 3: Probando feed individual de Reddit (r/technology)...")
    try:
        test = await fetch_rss_feed("https://www.reddit.com/r/technology/top.rss?t=day", "Deep Tech e IA", limit=3)
        print(f"   ✅ Obtenidas: {len(test)} noticias")
        for t in test[:3]:
            print(f"      • {t['title'][:70]}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("✅ DIAGNÓSTICO COMPLETO")
    print("=" * 60)

asyncio.run(main())
