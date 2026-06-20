import aiohttp
import logging
import os

# WMO weather codes → descripción corta en español (Open-Meteo)
_WMO = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina con escarcha", 51: "llovizna ligera", 53: "llovizna",
    55: "llovizna intensa", 61: "lluvia ligera", 63: "lluvia", 65: "lluvia fuerte",
    71: "nieve ligera", 73: "nieve", 75: "nieve fuerte", 80: "chubascos",
    81: "chubascos fuertes", 82: "chubascos violentos", 95: "tormenta",
    96: "tormenta con granizo", 99: "tormenta fuerte con granizo",
}

def _aqi_label_eu(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "Desconocido"
    if v <= 20: return "Excelente 🟢"
    if v <= 40: return "Justo 🟡"
    if v <= 60: return "Moderado 🟠"
    if v <= 80: return "Pobre 🔴"
    return "Peligroso ☠️"

async def get_weather_and_aqi(location: str = "Bogota") -> dict:
    """
    Agente Meteorólogo. Primario: Open-Meteo (gratis, sin key, sin límite práctico).
    Fallback: OpenWeatherMap (si hay key). Mismo esquema de retorno.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Geocoding (Open-Meteo, gratis)
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=es"
            async with session.get(geo_url, timeout=10) as resp:
                geo = await resp.json()
            results = geo.get("results") or []
            if results:
                g = results[0]
                lat, lon, name = g["latitude"], g["longitude"], g.get("name", location)

                # 2. Clima actual
                w_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                         f"&current=temperature_2m,weather_code")
                async with session.get(w_url, timeout=10) as resp:
                    w = await resp.json()
                cur = w.get("current", {})
                temp = cur.get("temperature_2m")
                desc = _WMO.get(cur.get("weather_code"), "condiciones variables")

                # 3. Calidad del aire (Open-Meteo Air Quality, gratis)
                aqi_label = "Desconocido"
                try:
                    aq_url = (f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}"
                              f"&longitude={lon}&current=european_aqi")
                    async with session.get(aq_url, timeout=10) as resp:
                        aq = await resp.json()
                    aqi_label = _aqi_label_eu(aq.get("current", {}).get("european_aqi"))
                except Exception:
                    pass

                if temp is not None:
                    return {"status": "ok", "location": name, "temp": round(temp, 1),
                            "description": desc, "aqi": aqi_label}
    except Exception as e:
        logging.warning(f"Open-Meteo falló, intentando OpenWeather: {e}")

    return await _get_weather_openweather(location)

async def _get_weather_openweather(location: str = "Bogota") -> dict:
    """Fallback: OpenWeatherMap (requiere OPENWEATHER_API_KEY)."""
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        logging.warning("No hay OPENWEATHER_API_KEY. Meteorólogo inactivo.")
        return {"status": "error", "message": "Clima no disponible."}
        
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Obtener coordenadas
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={location}&limit=1&appid={api_key}"
            async with session.get(geo_url) as resp:
                geo_data = await resp.json()
                
            if not geo_data:
                return {"status": "error", "message": "Ubicación no encontrada."}
                
            lat = geo_data[0]['lat']
            lon = geo_data[0]['lon']
            
            # 2. Obtener Clima
            weather_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=es&appid={api_key}"
            async with session.get(weather_url) as resp:
                w_data = await resp.json()
                
            # 3. Obtener AQI (Calidad del aire)
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
            async with session.get(aqi_url) as resp:
                aqi_data = await resp.json()
                
            temp = w_data['main']['temp']
            desc = w_data['weather'][0]['description']
            aqi = aqi_data['list'][0]['main']['aqi'] # 1 (Good) to 5 (Very Poor)
            
            aqi_dict = {1: "Excelente 🟢", 2: "Justo 🟡", 3: "Moderado 🟠", 4: "Pobre 🔴", 5: "Peligroso ☠️"}
            
            return {
                "status": "ok",
                "location": geo_data[0]['name'],
                "temp": temp,
                "description": desc,
                "aqi": aqi_dict.get(aqi, "Desconocido")
            }
    except Exception as e:
        logging.error(f"Error en Agente Meteorólogo: {e}")
        return {"status": "error", "message": "Error consultando el clima."}

async def get_btc_oracle() -> dict:
    """
    Oráculo Financiero VIP: Obtiene el precio de BTC, ETH, SOL y calcula el sentimiento macro.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    btc_data = data.get('bitcoin', {})
                    eth_data = data.get('ethereum', {})
                    sol_data = data.get('solana', {})
                    
                    btc_price = btc_data.get('usd', 0)
                    btc_change = btc_data.get('usd_24h_change', 0)
                    eth_price = eth_data.get('usd', 0)
                    sol_price = sol_data.get('usd', 0)
                    
                    if btc_change > 2: sentiment = "Alcista 🚀"
                    elif btc_change < -2: sentiment = "Bajista 🩸"
                    else: sentiment = "Consolidación ⚖️"
                    
                    return {
                        "status": "ok",
                        "price": btc_price,
                        "change": round(btc_change, 2),
                        "eth_price": eth_price,
                        "sol_price": sol_price,
                        "sentiment": sentiment
                    }
                else:
                    return {"status": "error"}
    except Exception as e:
        logging.error(f"Error en Oráculo Crypto: {e}")
        return {"status": "error"}

async def get_market_snapshot() -> str:
    """
    Snapshot de bolsa (acciones/índices) vía Finnhub (capa gratis).
    Devuelve un texto corto para inyectar al agente de voz, o "" si no hay key.
    """
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        return ""

    # Símbolos representativos: S&P500 ETF, Nasdaq ETF, Apple, Nvidia
    symbols = {"SPY": "S&P500", "QQQ": "Nasdaq", "AAPL": "Apple", "NVDA": "Nvidia"}
    partes = []
    try:
        async with aiohttp.ClientSession() as session:
            for sym, nombre in symbols.items():
                try:
                    url = f"https://finnhub.io/api/v1/quote?symbol={sym}&token={api_key}"
                    async with session.get(url, timeout=8) as resp:
                        d = await resp.json()
                    precio = d.get("c")
                    cambio = d.get("dp")
                    if precio:
                        partes.append(f"{nombre} ${precio:,.2f} ({cambio:+.2f}%)")
                except Exception:
                    continue
    except Exception as e:
        logging.error(f"Error en Finnhub: {e}")
        return ""

    return "Bolsa hoy: " + ", ".join(partes) + "." if partes else ""
