import codecs

bot_code = r"""import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    LinkPreviewOptions, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    PreCheckoutQuery, LabeledPrice
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from database import init_db, is_news_sent, mark_news_as_sent, cleanup_old_records
from memory import init_memory_db, get_karma_lessons, save_karma, get_or_create_user_profile, update_user_location
from oracles import get_weather_and_aqi, get_btc_oracle
from fetcher import fetch_latest_news
from agents import init_llm_clients, manager_agent, transcribe_audio
from payments import (
    activate_vip, check_vip_status, init_payment_tables,
    VIP_PRICE_STARS, VIP_PRICE_USDT, VIP_DURATION_DAYS
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
FETCH_INTERVAL_MINUTES = int(os.getenv('FETCH_INTERVAL_MINUTES', 120))

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
llm_clients = {}

async def process_and_send_news(chat_id: str, limit: int = 5):
    user_id = str(chat_id)
    profile = get_or_create_user_profile(user_id)
    vip_status = check_vip_status(user_id)
    profile['is_vip'] = vip_status['is_vip']
    is_vip = profile['is_vip']
    
    news_items = await fetch_latest_news(limit_per_feed=3, is_vip=is_vip)
    if not news_items:
        return
    nuevas_noticias = [item for item in news_items if not is_news_sent(item['id'])][:limit]
    if not nuevas_noticias:
        return

    karma_context = get_karma_lessons(limit=5)
    resultados = await manager_agent(
        news_items=nuevas_noticias,
        karma_context=karma_context,
        profile=profile,
        clients=llm_clients
    )
    
    enviadas = 0
    for res in resultados:
        karma_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="\U0001f44d Me sirvio", callback_data=f"karma_up_{res['news_id']}"),
                    InlineKeyboardButton(text="\U0001f44e Basura", callback_data=f"karma_down_{res['news_id']}")
                ]
            ]
        )

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

async def scheduled_job():
    if TELEGRAM_CHANNEL_ID:
        await process_and_send_news(TELEGRAM_CHANNEL_ID)

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\u2600\ufe0f Buenos Dias"), KeyboardButton(text="\U0001f4f0 Pulso del Mercado")],
            [KeyboardButton(text="\U0001f48e Premium VIP"), KeyboardButton(text="\U0001f3e2 Sobre Atlos")]
        ],
        resize_keyboard=True,
        persistent=True
    )
    return keyboard

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.first_name or "Usuario"
    get_or_create_user_profile(user_id, username)
    
    welcome_text = (
        f"\U0001f44b Bienvenido, <b>{username}</b>. Soy <b>Atlos</b>.\n\n"
        "Tu ecosistema personal de inteligencia (Simbiosis Humano-IA). "
        "Monitoreo criptomonedas, bolsa, clima y geopolitica 24/7, y te entrego "
        "solo lo que realmente importa para tu vida y bolsillo.\n\n"
        "Toca '\u2600\ufe0f Buenos Dias' para tu primer reporte."
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message(F.text.contains("Buenos Dias"))
async def cmd_morning(message: types.Message):
    user_id = str(message.from_user.id)
    username = message.from_user.first_name or "Usuario"
    profile = get_or_create_user_profile(user_id, username)
    
    await message.answer("Atlos esta preparando tu rutina matutina. Analizando clima, mercados y oraculos globales... \U0001f30d")
    
    clima = await get_weather_and_aqi(profile['location'] or "Bogota")
    btc = await get_btc_oracle()
    
    reporte = f"\U0001f305 <b>Buenos dias, {username}</b>\n\n"
    if clima['status'] == 'ok':
        reporte += f"\u2601\ufe0f <b>Clima ({clima['location']}):</b> {clima['temp']}C, {clima['description'].capitalize()}\n"
        reporte += f"\U0001f32c\ufe0f <b>Calidad del Aire:</b> {clima['aqi']}\n\n"
    if btc['status'] == 'ok':
        reporte += f"\U0001f4b0 <b>Bitcoin:</b> ${btc['price']:,.2f} ({btc['trend']})\n\n"
        
    reporte += "\U0001f4f0 <b>Tus Noticias de Alto Impacto:</b>"
    await message.answer(reporte)
    await process_and_send_news(str(message.chat.id), limit=3)

@dp.message(F.text.contains("Pulso del Mercado"))
@dp.message(Command('latest'))
async def cmd_latest(message: types.Message):
    await message.answer("Nuestros agentes estan analizando el mercado global. Un momento... \u23f3")
    await process_and_send_news(str(message.chat.id), limit=2)

@dp.message(Command('ciudad'))
async def cmd_ciudad(message: types.Message):
    user_id = str(message.from_user.id)
    partes = message.text.split(maxsplit=1)
    
    if len(partes) < 2:
        await message.answer("\U0001f4cd Para cambiar tu ciudad, escribe: <code>/ciudad NombreDeTuCiudad</code>\nEjemplo: <code>/ciudad Santiago</code>")
        return
        
    nueva_ciudad = partes[1].strip()
    update_user_location(user_id, nueva_ciudad)
    await message.answer(f"\u2705 ¡Listo! Tu radar climatico ha sido configurado en <b>{nueva_ciudad}</b>. Toca '\u2600\ufe0f Buenos Dias' para probarlo.")


@dp.message(F.text.contains("Premium VIP"))
@dp.message(Command('premium'))
async def cmd_premium(message: types.Message):
    user_id = str(message.from_user.id)
    vip = check_vip_status(user_id)
    
    if vip['is_vip']:
        await message.answer(
            f"\u2705 <b>Ya eres miembro VIP</b>\n\n"
            f"Tu membresia esta activa por <b>{vip['days_left']} dias mas</b>.\n\n"
            f"Disfruta de:\n"
            f"• \U0001f399\ufe0f Comandos de Voz ilimitados\n"
            f"• \U0001f9ec Agente Coach (Salud y Longevidad)\n"
            f"• \U0001f4ca Analisis profundo del Quant\n"
            f"• \U0001f52e Oraculo Avanzado de BTC"
        )
        return
    
    premium_text = (
        f"\U0001f48e <b>Atlos Premium — Simbiosis Total</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Precio:</b> ${VIP_PRICE_USDT} USD/mes\n\n"
        f"<b>¿Que obtienes?</b>\n"
        f"• \U0001f399\ufe0f Comandos de Voz (Whisper IA)\n"
        f"• \U0001f9ec Agente Coach personal (Salud, Longevidad, Biohacking)\n"
        f"• \U0001f4ca Analisis profundo del Agente Quant\n"
        f"• \U0001f52e Oraculo Avanzado de BTC y Mercados\n"
        f"• \u26a1 Prioridad en respuestas\n\n"
        f"<i>Elige tu metodo de pago:</i>"
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
        
    await message.reply(f"\U0001f5e3\ufe0f <b>Tu dijiste:</b> {texto_transcrito}\n\n<i>(En el futuro, Atlos te respondera contextualmente a esto).</i>")

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

async def main():
    global llm_clients
    init_db()
    init_memory_db()
    init_payment_tables()
    llm_clients = init_llm_clients()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_job, 'interval', minutes=FETCH_INTERVAL_MINUTES)
    scheduler.add_job(cleanup_old_records, 'interval', days=1)
    scheduler.start()
    
    logging.info("\U0001f680 Iniciando Atlos — Enjambre Multi-Agente en Telegram...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
"""

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(bot_code)
print("Archivo bot.py reconstruido en utf-8")
