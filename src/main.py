import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    LinkPreviewOptions, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    PreCheckoutQuery, LabeledPrice
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
load_dotenv()

from src.core.database import init_db, is_news_sent, mark_news_as_sent, cleanup_old_records
from src.core.memory import init_memory_db, get_karma_lessons, save_karma, get_or_create_user_profile, update_user_location, get_troll_strikes, add_troll_strike
from src.agents.engine import init_llm_clients, manager_agent, transcribe_audio, conversational_agent
from src.services.oracles import get_weather_and_aqi, get_btc_oracle
from src.services.rss_fetcher import fetch_latest_news
from src.agents.marketing import generate_marketing_campaign
from src.services.payments import (
    activate_vip, check_vip_status, init_payment_tables,
    VIP_PRICE_STARS, VIP_PRICE_USDT, VIP_DURATION_DAYS
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
FETCH_INTERVAL_MINUTES = int(os.getenv('FETCH_INTERVAL_MINUTES', 120))

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
llm_clients = {}

async def process_and_send_news(chat_id: str, limit: int = 5, silent_if_empty: bool = False):
    user_id = str(chat_id)
    profile = get_or_create_user_profile(user_id)
    vip_status = check_vip_status(user_id)
    profile['is_vip'] = vip_status['is_vip']
    is_vip = profile['is_vip']
    
    news_items = await fetch_latest_news(limit_per_feed=3, is_vip=is_vip)
    if not news_items:
        if not silent_if_empty:
            await bot.send_message(chat_id, "📡 Radar despejado. No hay noticias nuevas en el mercado en este momento.")
        return
    nuevas_noticias = [item for item in news_items if not is_news_sent(item['id'])][:limit]
    if not nuevas_noticias:
        if not silent_if_empty:
            await bot.send_message(chat_id, "📡 Ya estás al día. Has leído todas las noticias de alto impacto por ahora.")
        return

    karma_context = get_karma_lessons(limit=5)
    resultados = await manager_agent(
        news_items=nuevas_noticias,
        karma_context=karma_context,
        profile=profile,
        clients=llm_clients
    )
    
    if not resultados:
        if not silent_if_empty:
            await bot.send_message(chat_id, "📡 Radar procesado, pero ninguna noticia superó el filtro de relevancia de la IA. Estás al día.")
        return
        
    enviadas = 0
    await bot.send_message(chat_id, "📰 <b>Tus Noticias de Alto Impacto:</b>")
    for res in resultados:
        karma_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="\U0001f44d Me sirvio", callback_data=f"karma_up_{res['news_id']}"),
                    InlineKeyboardButton(text="\U0001f44e Basura", callback_data=f"karma_down_{res['news_id']}")
                ]
            ]
        )

        # Formato especial para Alertas de Crisis Global
        if res.get('is_global_alert'):
            message_text = (
                f"🚨🚨🚨 <b>ALERTA GLOBAL — ORÁCULO DE PÁNICO</b> 🚨🚨🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>⚠️ EVENTO CRÍTICO DETECTADO</b>\n"
                f"<i>Categoría: {res['category']}</i>\n\n"
                f"{res['editorial']}\n\n"
                f"Fuente — <a href='{res['link']}'>[Leer Original]</a>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Esta alerta se envió a TODOS los usuarios por protocolo de crisis.</i>"
            )
        else:
            message_text = (
                f"\U0001f3af <b>Atlos Radar</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Categoria: {res['category']}</i>\n\n"
                f"{res['editorial']}\n\n"
                f"Fuente — <a href='{res['link']}'>[Leer Original]</a>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Reacciona con \U0001f44d o \U0001f44e para ensenar a la IA.</i>"
            )
        
        try:
            await bot.send_message(
                chat_id=chat_id, 
                text=message_text,
                reply_markup=karma_kb,
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            mark_news_as_sent(res['news_id'], res['title'], res['category'])
            enviadas += 1
            await asyncio.sleep(2)
        except Exception as e:
            pass

from src.core.memory import get_all_users

async def scheduled_job():
    """Motor 24/7 para VIPs: Escanea el radar constantemente y envía PUSH en tiempo real."""
    users = get_all_users()
    vip_users = [u['user_id'] for u in users if check_vip_status(u['user_id'])['is_vip']]
    
    for user_id in vip_users:
        # PUSH en tiempo real para VIPs (Límite 3 para no spamear demasiado en un solo ciclo)
        await process_and_send_news(user_id, limit=3, silent_if_empty=True)

async def scheduled_morning():
    """Motor Diario para Gratis: Envía el resumen general a todos."""
    users = get_all_users()
    free_users = [u['user_id'] for u in users if not check_vip_status(u['user_id'])['is_vip']]
    
    for user_id in free_users:
        try:
            # Enviamos el mensaje matutino
            profile = get_or_create_user_profile(user_id)
            clima = await get_weather_and_aqi(profile['location'] or "Bogota")
            reporte = f"☀️ <b>Buenos días. Aquí tu reporte diario de Atlos.</b>\n\n"
            if clima['status'] == 'ok':
                reporte += f"☁️ <b>Clima ({clima['location']}):</b> {clima['temp']}C\n\n"
            await bot.send_message(user_id, reporte)
            await process_and_send_news(user_id, limit=3, silent_if_empty=True)
            
            # --- FOMO TEASER DIARIO ---
            fomo_teaser = (
                "🔒 <b>[RADAR VIP BLOQUEADO]</b>\n"
                "<i>Hace unos minutos nuestro Agente Quant detectó un evento inusual en los mercados. "
                "Solo los usuarios VIP recibieron esta alerta predictiva en tiempo real.</i>\n"
                "👉 Toca '💎 Premium VIP' en el menú para desbloquear el radar 24/7."
            )
            await bot.send_message(user_id, fomo_teaser)
            
            await asyncio.sleep(1) # Rate limit protection
        except Exception as e:
            pass

def get_main_keyboard(is_vip: bool = False):
    botones = [
        [KeyboardButton(text="☀️ Buenos Días"), KeyboardButton(text="📰 Pulso del Mercado")],
        [KeyboardButton(text="💎 Premium VIP"), KeyboardButton(text="🏢 Sobre Atlos")]
    ]
    if is_vip:
        botones.append([KeyboardButton(text="⚙️ Panel de Control VIP")])
        
    keyboard = ReplyKeyboardMarkup(
        keyboard=botones,
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

from src.core.memory import update_user_demographics

class OnboardingStates(StatesGroup):
    waiting_for_city = State()
    waiting_for_age = State()
    waiting_for_gender = State()

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    username = message.from_user.first_name or "Usuario"
    profile = get_or_create_user_profile(user_id, username)
    
    if profile.get('city') and profile.get('age'):
        welcome_text = (
            f"👋 Bienvenido de vuelta, <b>{username}</b>.\n\n"
            "Tu ecosistema personal de inteligencia está activo.\n"
            "Toca '☀️ Buenos Días' para tu reporte."
        )
        is_vip = check_vip_status(user_id).get('is_vip', False)
        await message.answer(welcome_text, reply_markup=get_main_keyboard(is_vip))
        return

    # Iniciar Onboarding
    await state.set_state(OnboardingStates.waiting_for_city)
    await message.answer(f"👋 Bienvenido a Atlos, <b>{username}</b>.\n\nPara personalizar tu inteligencia artificial y ajustar los oráculos del clima, por favor escribe el nombre de tu <b>Ciudad</b> (Ej: Madrid, Bogotá, Miami):")

@dp.message(OnboardingStates.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OnboardingStates.waiting_for_age)
    await message.answer("Excelente. Ahora, ¿cuál es tu <b>Edad</b>? (Escribe solo el número, ej: 28)")

@dp.message(OnboardingStates.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Por favor escribe solo el número (ej: 28).")
        return
    await state.update_data(age=int(message.text))
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Hombre"), KeyboardButton(text="Mujer")],
            [KeyboardButton(text="Prefiero no decirlo")]
        ], 
        resize_keyboard=True
    )
    await state.set_state(OnboardingStates.waiting_for_gender)
    await message.answer("Perfecto. Por último, ¿cuál es tu <b>Género</b>? (Esto ajusta el tono psicológico de la redacción de noticias)", reply_markup=kb)

@dp.message(OnboardingStates.waiting_for_gender)
async def process_gender(message: types.Message, state: FSMContext):
    data = await state.get_data()
    city = data['city']
    age = data['age']
    gender = message.text
    
    user_id = str(message.from_user.id)
    update_user_location(user_id, city)
    update_user_demographics(user_id, age, gender)
    
    await state.clear()
    
    welcome_text = (
        f"✅ ¡Perfil configurado exitosamente!\n\n"
        "Atlos ya calibró sus oráculos para tu ciudad y ajustó su psicología a tu perfil.\n\n"
        "Toca '☀️ Buenos Días' abajo para recibir tu primer reporte personalizado."
    )
    is_vip = check_vip_status(user_id).get('is_vip', False)
    await message.answer(welcome_text, reply_markup=get_main_keyboard(is_vip))

@dp.message(F.text.contains("Buenos"))
async def cmd_morning(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.first_name or "Usuario"
    profile = get_or_create_user_profile(user_id, username)
    vip_status = check_vip_status(user_id)
    is_vip = vip_status.get('is_vip', False)
    
    await message.answer("Atlos esta preparando tu rutina matutina. Analizando clima, mercados y oraculos globales... 🌍")
    
    try:
        user_location = profile.get('city') or profile.get('location')
        clima = await get_weather_and_aqi(user_location or "Bogota")
        btc = await get_btc_oracle()
        
        reporte = f"🌅 <b>Buenos días, {username}</b>\n\n"
        if clima['status'] == 'ok':
            reporte += f"☁️ <b>Clima ({clima['location']}):</b> {clima['temp']}°C, {clima['description'].capitalize()}\n"
            reporte += f"🌬️ <b>Calidad del Aire:</b> {clima['aqi']}\n"
            if not user_location:
                reporte += "<i>(📍 Escribe /ciudad TuCiudad para personalizar el clima)</i>\n"
            reporte += "\n"
        if btc.get('status') == 'ok':
            reporte += f"💰 <b>Bitcoin:</b> ${btc['price']:,.2f} ({btc.get('change', 0)}%)\n"
            if is_vip:
                reporte += f"💎 <b>Ethereum:</b> ${btc.get('eth_price', 0):,.2f}\n"
                reporte += f"🚀 <b>Solana:</b> ${btc.get('sol_price', 0):,.2f}\n"
                reporte += f"🧠 <b>Sentimiento Macro:</b> {btc.get('sentiment', '')}\n"
            reporte += "\n"
            
        await message.answer(reporte)
    except Exception as e:
        import logging
        logging.error(f"Error en reporte matutino: {e}")
        await message.answer("⚠️ Hubo un error generando parte del reporte. Consultando noticias...")
    
    try:
        await process_and_send_news(str(message.chat.id), limit=3)
    except Exception as e:
        import logging
        logging.error(f"Error en noticias matutinas: {e}")
        await message.answer("📡 Las fuentes de noticias están temporalmente saturadas. Intenta con 'Pulso del Mercado' en unos minutos.")
    
    if not is_vip:
        # --- FOMO TEASER DIARIO ---
        fomo_teaser = (
            "🔒 <b>[RADAR VIP BLOQUEADO]</b>\n"
            "<i>Hace unos minutos nuestro Agente Quant detectó un evento inusual en los mercados. "
            "Solo los usuarios VIP recibieron esta alerta predictiva en tiempo real.</i>\n"
            "👉 Toca '💎 Premium VIP' en el menú para desbloquear el radar 24/7."
        )
        await message.answer(fomo_teaser)

@dp.message(F.text.contains("Pulso del Mercado"))
@dp.message(Command('latest'))
async def cmd_latest(message: types.Message):
    await message.answer("Nuestros agentes estan analizando el mercado global. Un momento... \u23f3")
    try:
        await process_and_send_news(str(message.chat.id), limit=2)
    except Exception as e:
        import logging
        logging.error(f"Error en Pulso del Mercado: {e}")
        await message.answer("📡 He peinado la red y el mercado está en absoluto silencio. Ninguna noticia de alto impacto detectada por ahora.")

@dp.message(Command('ciudad'))
async def cmd_ciudad(message: types.Message):
    user_id = str(message.from_user.id)
    partes = message.text.split(maxsplit=1)
    
    if len(partes) < 2:
        await message.answer("📍 Para cambiar tu ciudad, escribe: <code>/ciudad NombreDeTuCiudad</code>\nEjemplo: <code>/ciudad Santiago</code>")
        return
        
    nueva_ciudad = partes[1].strip()
    update_user_location(user_id, nueva_ciudad)
    await message.answer(f"✅ ¡Listo! Tu radar climático ha sido configurado en <b>{nueva_ciudad}</b>. Toca '☀️ Buenos Días' para probarlo.")

# --- PANEL VIP ---
from src.core.memory import get_user_preferences, update_user_preferences
import json

CATEGORIAS_RADAR = [
    "Criptomonedas", "Geopolítica y Guerra", "Deep Tech e IA", "Mercados y Wall Street", 
    "Deportes", "Astronomía y Ciencia", "Entretenimiento y Cultura", "Salud y Bienestar",
    "Viajes y Estilo de Vida", "Videojuegos y E-Sports", "Clima y Sostenibilidad",
    "Startups y Negocios", "Motor y Automovilismo"
]

def get_panel_keyboard(prefs: dict):
    inline_kb = []
    for cat in CATEGORIAS_RADAR:
        status = prefs.get(cat, True)
        icono = "✅" if status else "❌"
        inline_kb.append([InlineKeyboardButton(text=f"{icono} {cat}", callback_data=f"toggle_{cat}")])
    
    # Botón de Cerrar Panel
    inline_kb.append([InlineKeyboardButton(text="✅ Guardar y Cerrar Panel", callback_data="close_panel")])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

@dp.message(F.text.contains("Panel de Control VIP"))
@dp.message(Command('panel'))
async def cmd_panel(message: types.Message):
    user_id = str(message.from_user.id)
    vip = check_vip_status(user_id)
    
    if not vip['is_vip']:
        await message.answer("🔒 El Panel de Control es exclusivo para usuarios VIP.")
        return
        
    prefs = get_user_preferences(user_id)
    await message.answer(
        "🧠 <b>Panel Omnisciente Atlos</b>\n\n"
        "Configura tu Radar Personal. Apaga las fuentes que no te interesen.\n"
        "<i>Nota: Si ocurre una alerta global crítica (Ej. Tercera Guerra Mundial), el radar hará override y te notificará igual.</i>",
        reply_markup=get_panel_keyboard(prefs)
    )

@dp.callback_query(F.data == "open_panel")
async def process_open_panel(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    prefs = get_user_preferences(user_id)
    await callback.message.edit_text(
        "🧠 <b>Panel Omnisciente Atlos</b>\n\n"
        "Configura tu Radar Personal. Apaga las fuentes que no te interesen.\n"
        "<i>Nota: Si ocurre una alerta global crítica, el radar hará override.</i>",
        reply_markup=get_panel_keyboard(prefs)
    )

@dp.callback_query(F.data == "close_panel")
async def process_close_panel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Panel Omnisciente cerrado.")

@dp.callback_query(F.data.startswith("toggle_"))
async def process_toggle(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    cat_to_toggle = callback.data.replace("toggle_", "")
    
    prefs = get_user_preferences(user_id)
    current_status = prefs.get(cat_to_toggle, True)
    prefs[cat_to_toggle] = not current_status  # Invertir estado
    
    update_user_preferences(user_id, prefs)
    
    await callback.answer(f"Radar de {cat_to_toggle} actualizado.")
    await callback.message.edit_reply_markup(reply_markup=get_panel_keyboard(prefs))



@dp.message(F.text.contains("Premium VIP"))
@dp.message(Command('premium'))
async def cmd_premium(message: types.Message):
    user_id = str(message.from_user.id)
    vip = check_vip_status(user_id)
    
    if vip['is_vip']:
        # Dashboard VIP Interactivo
        dashboard_text = (
            f"👑 <b>DASHBOARD VIP</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Tu nivel de acceso es <b>Omnisciente</b> (Quedan {vip['days_left']} días).\n\n"
            f"🎙️ <b>Inteligencia de Voz Activa:</b>\n"
            f"Mantén presionado el ícono del micrófono en Telegram y háblame. "
            f"Pregúntame sobre el clima de tu ciudad, el precio del Bitcoin, o pídeme "
            f"que analice el mercado de valores. Atlos te escuchará y responderá.\n\n"
            f"⚙️ <b>Radar de Noticias Personalizado:</b>\n"
            f"Usa el botón de abajo para encender o apagar las categorías de tu radar."
        )
        
        dashboard_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Abrir Panel Omnisciente", callback_data="open_panel")]
        ])
        await message.answer(dashboard_text, reply_markup=dashboard_kb)
        return
    
    premium_text = (
        f"💎 <b>Atlos Premium — Simbiosis Total</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Precio:</b> ${VIP_PRICE_USDT} USD por 60 Días (Tarifa Fija)\n\n"
        f"<b>¿Qué obtienes?</b>\n"
        f"• 🎙️ Comandos de Voz (Whisper IA)\n"
        f"• 🧠 Panel de Control Omnisciente (Selecciona tus radares)\n"
        f"• 📊 Análisis Predictivo del Quant\n"
        f"• ⚡ Alertas Breaking News en Tiempo Real\n"
        f"• ⚡ Prioridad en respuestas\n\n"
        f"<i>Elige tu método de pago:</i>"
    )
    
    payment_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"\u2b50 Pagar con Telegram Stars ({VIP_PRICE_STARS} Stars)",
                callback_data="pay_stars"
            )],
            [InlineKeyboardButton(
                text=f"\U0001f48e Pagar con USDT ({VIP_PRICE_USDT} USDT)",
                callback_data="pay_crypto"
            )]
        ]
    )
    
    await message.answer(premium_text, reply_markup=payment_kb)

@dp.callback_query(F.data == "pay_stars")
async def process_stars_payment(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer_invoice(
        title="Atlos Premium VIP",
        description=f"Membresia VIP por {VIP_DURATION_DAYS} dias. Incluye Voz IA, Coach de Salud, Oraculo Avanzado y mas.",
        payload=f"vip_{callback.from_user.id}_{VIP_DURATION_DAYS}d",
        currency="XTR",
        prices=[LabeledPrice(label="Atlos VIP (1 mes)", amount=VIP_PRICE_STARS)]
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment_handler(message: types.Message):
    user_id = str(message.from_user.id)
    payment_info = message.successful_payment
    charge_id = payment_info.telegram_payment_charge_id
    success = activate_vip(user_id, days=VIP_DURATION_DAYS, payment_id=charge_id)
    
    if success:
        await message.answer(
            f"\U0001f389 <b>¡Bienvenido al circulo interno, {message.from_user.first_name}!</b>\n\n"
            f"Tu membresia VIP esta activa por <b>{VIP_DURATION_DAYS} dias</b>.\n\n"
            f"Ahora puedes:\n"
            f"• Enviarme notas de voz \U0001f399\ufe0f\n"
            f"• Recibir analisis profundos del Coach \U0001f9ec\n"
            f"• Acceder al Oraculo Avanzado \U0001f52e\n\n"
            f"<i>Gracias por confiar en Atlos. Tu inversion se pagara sola.</i>"
        )
    else:
        await message.answer("Hubo un error procesando tu pago. Contacta al soporte.")

@dp.callback_query(F.data == "pay_crypto")
async def process_crypto_payment(callback: CallbackQuery):
    await callback.answer()
    crypto_token = os.getenv("CRYPTOPAY_API_TOKEN")
    
    if crypto_token:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                headers = {"Crypto-Pay-API-Token": crypto_token}
                payload = {
                    "asset": "USDT",
                    "amount": str(VIP_PRICE_USDT),
                    "description": f"Atlos VIP {VIP_DURATION_DAYS} dias",
                    "payload": f"vip_{callback.from_user.id}",
                    "expires_in": 3600
                }
                async with session.post(
                    "https://pay.crypt.bot/api/createInvoice",
                    headers=headers, json=payload
                ) as resp:
                    data = await resp.json()
                    
                if data.get("ok"):
                    invoice_url = data["result"]["bot_invoice_url"]
                    invoice_kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="\U0001f4b3 Pagar con @CryptoBot", url=invoice_url)],
                            [InlineKeyboardButton(text="\u2705 Ya pague", callback_data=f"verify_crypto_{data['result']['invoice_id']}")]
                        ]
                    )
                    await callback.message.answer(
                        f"\U0001f48e <b>Pago con USDT</b>\n\n"
                        f"Monto: <b>{VIP_PRICE_USDT} USDT</b>\n"
                        f"Tienes 1 hora para completar el pago.\n\n"
                        f"Toca el boton para pagar:",
                        reply_markup=invoice_kb
                    )
                    return
        except Exception as e:
            pass
    
    wallet = os.getenv("USDT_WALLET", "TU_WALLET_USDT_AQUI")
    await callback.message.answer(
        f"\U0001f48e <b>Pago Manual con USDT</b>\n\n"
        f"Envia exactamente <b>{VIP_PRICE_USDT} USDT</b> (Red TRC-20) a:\n\n"
        f"<code>{wallet}</code>\n\n"
        f"Despues de pagar, envia el comprobante (captura de pantalla) a @tuusuario "
        f"y activaremos tu VIP en menos de 1 hora.\n\n"
        f"<i>Pronto tendremos pagos automaticos con @CryptoBot.</i>"
    )

@dp.callback_query(F.data.startswith("verify_crypto_"))
async def verify_crypto_payment(callback: CallbackQuery):
    invoice_id = callback.data.replace("verify_crypto_", "")
    crypto_token = os.getenv("CRYPTOPAY_API_TOKEN")
    
    if not crypto_token:
        await callback.answer("Error: Sistema de pago no configurado.", show_alert=True)
        return
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": crypto_token}
            async with session.get(
                f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}",
                headers=headers
            ) as resp:
                data = await resp.json()
        
        if data.get("ok") and data["result"]["items"]:
            invoice = data["result"]["items"][0]
            if invoice["status"] == "paid":
                user_id = str(callback.from_user.id)
                activate_vip(user_id, days=VIP_DURATION_DAYS, payment_id=str(invoice_id))
                
                await callback.message.edit_text(
                    f"\U0001f389 <b>¡Pago confirmado!</b>\n\n"
                    f"Tu membresia VIP esta activa por <b>{VIP_DURATION_DAYS} dias</b>.\n"
                    f"Enviame una nota de voz para probar tu nueva capacidad \U0001f399\ufe0f"
                )
                await callback.answer("¡Pago verificado! Bienvenido al VIP.", show_alert=True)
            else:
                await callback.answer("\u23f3 El pago aun no se ha completado. Intentalo de nuevo despues de pagar.", show_alert=True)
        else:
            await callback.answer("No se encontro la factura. Intentalo de nuevo.", show_alert=True)
    except Exception as e:
        await callback.answer("Error verificando el pago.", show_alert=True)

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    user_id = str(message.from_user.id)
    vip = check_vip_status(user_id)
    
    if not vip['is_vip']:
        await message.answer(
            "\U0001f399\ufe0f <b>Comandos de voz</b> es una funcion exclusiva VIP.\n\n"
            "Toca '\U0001f48e Premium VIP' para desbloquearla."
        )
        return
        
    await message.answer("\U0001f3a7 Escuchando...")
    
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"voice_{user_id}.ogg"
    await bot.download_file(file.file_path, file_path)
    
    texto_transcrito = await transcribe_audio(llm_clients, file_path)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        
    strikes = get_troll_strikes(user_id)
    if strikes <= 0:
        await message.reply("🚫 <b>Acceso Restringido.</b> Has acumulado demasiados strikes por comportamiento inadecuado. El protocolo Anti-Troll ha bloqueado tu perfil temporalmente.")
        return
        
    await message.reply(f"\U0001f5e3\ufe0f <b>Transcripción:</b> {texto_transcrito}\n\n<i>Analizando...</i>")
    
    # Preparar contexto si preguntan por clima o tiempo
    context_data = ""
    texto_lower = texto_transcrito.lower()
    if "clima" in texto_lower or "tiempo" in texto_lower or "temperatura" in texto_lower:
        profile = get_or_create_user_profile(user_id)
        ciudad = profile.get('city') or "Bogota"
        # Extract city from text if specified, very basic heuristic
        words = texto_lower.split()
        if "en" in words:
            idx = words.index("en")
            if idx + 1 < len(words):
                ciudad = words[idx + 1].capitalize()
        
        clima = await get_weather_and_aqi(ciudad)
        if clima['status'] == 'ok':
            context_data = f"Datos del Clima actual en {clima['location']}: {clima['temp']}C, {clima['description']}."
            
    # Consultar al agente
    res = await conversational_agent(texto_transcrito, check_vip_status(user_id), llm_clients, context_data)
    
    if res["strike"]:
        strikes_left = add_troll_strike(user_id)
        await message.answer(f"⚠️ {res['response']}\n<i>Strikes restantes: {strikes_left}</i>")
    else:
        await message.answer(f"🧠 <b>Atlos:</b>\n{res['response']}")

@dp.message(F.text.contains("Sobre Atlos"))
@dp.message(Command('about'))
async def cmd_about(message: types.Message):
    about_text = (
        "\U0001f9e0 <b>Tecnologia ABaaS (Agent Bot as a Service)</b>\n\n"
        "Soy Atlos. Opero con un 'Manager', un 'Quant', "
        "un 'Meteorologo' y un 'Editor' impulsados por modelos de lenguaje de ultima generacion "
        "(Llama 3, Gemini, Grok). \n\n"
        "Aprendo de tus interacciones (Karma) y adapto mi personalidad a ti."
    )
    await message.answer(about_text)

@dp.callback_query(F.data.startswith("karma_"))
async def process_karma_callback(callback: CallbackQuery):
    data = callback.data
    user_id = str(callback.from_user.id)
    
    if data.startswith("karma_up_"):
        news_id = data.replace("karma_up_", "")
        reaction = "thumbs_up"
        respuesta_usuario = "¡Gracias! Anotado. Buscaremos mas noticias como esta. \U0001f4c8"
    else:
        news_id = data.replace("karma_down_", "")
        reaction = "thumbs_down"
        respuesta_usuario = "Entendido. \U0001f5d1\ufe0f Le dire a la IA que no te envie mas basura de este tipo."
        
    save_karma(news_id=news_id, user_id=user_id, reaction=reaction)
    
    await callback.answer(respuesta_usuario)
    await callback.message.edit_reply_markup(reply_markup=None)

@dp.message(Command("give_vip"))
async def cmd_give_vip(message: types.Message):
    user_id = str(message.from_user.id)
    profile = get_or_create_user_profile(user_id)
    
    if not profile.get('is_vip'):
        await message.answer("⚠️ Solo los administradores (VIP) pueden regalar membresías.")
        return
        
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Uso: /give_vip <ID_DEL_USUARIO> <DIAS>\nEjemplo: /give_vip 123456789 30")
        return
        
    target_id = parts[1]
    
    try:
        days = int(parts[2])
    except ValueError:
        await message.answer("Error: Los días deben ser un número.")
        return
    
    from src.services.payments import activate_vip
    activate_vip(target_id, duration_days=days)
    
    await message.answer(f"👑 Privilegios concedidos. El usuario {target_id} es ahora VIP por {days} días.")
    try:
        await bot.send_message(target_id, f"🎉 ¡Felicidades! Has recibido una membresía VIP de cortesía por {days} días. Disfruta del acceso total a Comandos de Voz e Inteligencia Financiera.")
    except Exception:
        pass

async def main():
    global llm_clients
    init_db()
    init_memory_db()
    init_payment_tables()
    llm_clients = init_llm_clients()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_job, 'interval', minutes=FETCH_INTERVAL_MINUTES) # PUSH VIP 24/7
    scheduler.add_job(scheduled_morning, 'cron', hour=8, minute=0) # Resumen Diario Free a las 8:00 AM
    scheduler.add_job(cleanup_old_records, 'interval', days=1)
    scheduler.start()
    
    logging.info("\U0001f680 Iniciando Atlos — Enjambre Multi-Agente en Telegram...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
