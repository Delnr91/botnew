import aiohttp
import logging
import os

async def get_weather_and_aqi(location: str = "Bogota") -> dict:
    """
    Agente Meteorólogo: Obtiene el clima y calidad del aire usando OpenWeatherMap.
    Retorna un diccionario con la descripción, temperatura y AQI.
    """
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
