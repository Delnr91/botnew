# 🧠 Atlos — Agent-Bot-as-a-Service de Noticias

> Bot de noticias inteligente en Telegram con arquitectura **multi-agente** y **multi-LLM**,
> diseñado para correr en la **capa gratis eterna de Google Cloud (e2-micro, 1 GB)** + **Supabase free**.
> Filtra el ruido del mundo, redacta con IA y entrega solo lo relevante — con un canal de voz premium.

---

## 📑 Tabla de contenido
- [¿Qué es Atlos?](#-qué-es-atlos)
- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Stack tecnológico](#-stack-tecnológico)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Cómo funciona el cerebro (multi-agente + multi-LLM)](#-cómo-funciona-el-cerebro-multi-agente--multi-llm)
- [Modelo freemium y cadencia](#-modelo-freemium-y-cadencia)
- [APIs y capa gratis](#-apis-y-capa-gratis)
- [Variables de entorno](#-variables-de-entorno)
- [Instalación local](#-instalación-local)
- [Despliegue en Google Cloud](#-despliegue-en-google-cloud)
- [Actualizar el bot (SSH)](#-actualizar-el-bot-ssh)
- [Operación y troubleshooting](#-operación-y-troubleshooting)
- [Roadmap](#-roadmap)

---

## 🎯 ¿Qué es Atlos?

Atlos es una plataforma de bots de noticias para Telegram. Un **núcleo central (orquestador)**
escanea ~35 fuentes RSS + APIs, las analiza con un enjambre de agentes de IA, redacta una versión
limpia **una sola vez por ciclo** y la reparte a todos los usuarios. Esto desacopla el **costo**
(constante) del **volumen** (N usuarios), lo que hace viable escalar gratis.

- **Gancho gratis:** noticias relevantes de finanzas, tecnología y actualidad para captar usuarios.
- **VIP:** radar 24/7 por categorías + **canal de voz** (hablas y Atlos responde con datos reales y audio).
- **Pago:** USDT / Telegram Stars (en fase de testeo).

---

## ✨ Características

| Categoría | Detalle |
|---|---|
| 📰 **Noticias IA** | ~35 feeds RSS en 13 categorías, filtrados y redactados por agentes LLM |
| 🧠 **Multi-agente** | Manager → Quant (finanzas) → Editor (redacción) → Psicólogo (tono) → Conversacional (voz) |
| 🔀 **Multi-LLM híbrido** | Groq + Gemini con fallback y rotación de claves ante 429 |
| ⚡ **NewsEngine central** | Procesa el mundo 1 vez por ciclo y cachea → costo de tokens fijo |
| 🎙️ **Voz VIP** | Transcripción (Whisper) + respuesta con datos reales + **audio (Edge-TTS)** |
| 🚨 **Oráculo de Pánico Global** | Detecta crisis (guerra, tsunami, nuclear, asteroide…) y avisa a **todos** en tiempo real |
| 👍👎 **Karmalopy** | Botones like/dislike que entrenan a la IA |
| 🖼️ **Portadas IA** | Imagen generada (Pollinations) en alertas globales |
| 🌤️ **Oráculos** | Clima + calidad del aire (Open-Meteo) y precios cripto (CoinGecko) |
| 🩺 **Coach de salud** | Consejo diario de bienestar |
| 🎛️ **UX button-first** | Todo accesible por botones grandes (inclusivo); los comandos `/` siguen funcionando |
| 💎 **Freemium** | Free con cadencia controlada, VIP con radar 24/7 + voz |

---

## 🏗️ Arquitectura

```
            ┌──────────────── ORQUESTADOR (NewsEngine, 1 proceso) ───────────────┐
            │  Fetch RSS + APIs → Dedup → Quant → Editor (redacción neutra)       │
            │  corre 1 vez por ciclo  →  CACHÉ (memoria / Upstash Redis)          │
            │  Pool multi-LLM con rotación de claves ante 429                     │
            └───────────────┬────────────────────────────────────────────────────┘
                            │  fan-out (0 LLM extra) + filtro por usuario
        ┌───────────────────┼───────────────────────────────┐
   Usuarios FREE        Usuarios VIP                   Crisis global
   pulso cada 8 h       radar 24/7 por categorías      broadcast a TODOS
   + reporte 8 AM       + voz IA + audio               en tiempo real
```

**Principio clave:** el cerebro procesa una vez; los usuarios solo **leen del caché**. Por eso
100 usuarios (o N sub-bots a futuro) **no multiplican** el costo de tokens.

---

## 🛠️ Stack tecnológico

- **Lenguaje:** Python 3.11
- **Bot framework:** [aiogram 3.x](https://aiogram.dev) (Telegram, asíncrono)
- **Scheduler:** APScheduler
- **HTTP async:** aiohttp
- **LLM:** Groq (Llama 3.1) · Google Gemini 2.0 Flash · *(opcional: OpenRouter, GitHub Models, Grok)*
- **Voz:** Groq Whisper (entrada) · Edge-TTS (salida, gratis)
- **Base de datos:** Supabase (PostgreSQL)
- **Caché:** memoria + Upstash Redis (opcional)
- **Infra:** Google Compute Engine `e2-micro` (Debian 12) — capa gratis

---

## 📂 Estructura del proyecto

```
botnew/
├── src/
│   ├── main.py                 # Entrypoint: handlers, scheduler, fan-out
│   ├── agents/
│   │   ├── engine.py           # Multi-LLM router + agentes cognitivos + Oráculo de crisis
│   │   ├── news_engine.py      # NÚCLEO central: procesa 1 vez + caché + selección por usuario
│   │   └── marketing.py        # Generador de campañas
│   ├── core/
│   │   ├── database.py         # Supabase: sent_news
│   │   ├── memory.py           # Perfiles, karma, VIP, preferencias
│   │   └── cache.py            # Caché Upstash Redis (REST, opcional)
│   └── services/
│       ├── rss_fetcher.py      # 13 categorías de feeds RSS
│       ├── oracles.py          # Clima (Open-Meteo) + cripto + bolsa (Finnhub)
│       ├── voice.py            # Text-to-Speech (Edge-TTS)
│       └── payments.py         # VIP: Telegram Stars + USDT
├── infra/
│   ├── Dockerfile
│   ├── startup.sh              # Init de la VM (clone + venv + run)
│   └── deploy_gcloud.sh        # Crea la instancia e2-micro
├── requirements.txt
├── .env.example                # Plantilla de variables (sin valores)
└── README.md
```

---

## 🧠 Cómo funciona el cerebro (multi-agente + multi-LLM)

Cada LLM hace lo que mejor le sale (**modo híbrido para optimizar tokens**):

| Agente | Tarea | LLM primario |
|---|---|---|
| **Quant** | Relevancia (SÍ/NO) + análisis financiero | Groq (rápido y barato) |
| **Editor** | Redacción de la noticia | Gemini (mejor prosa) |
| **Conversacional** | Responder notas de voz | Groq (baja latencia) |
| **Coach** | Consejo de salud diario | Groq |

**Fallback + rotación:** `groq → gemini → openrouter → github → grok`. Ante un `429`/cuota agotada,
el router rota a la siguiente clave del mismo proveedor o cae al siguiente proveedor. Puedes poner
**varias claves separadas por coma** para sumar cuotas free:

```env
GROQ_API_KEY=clave1,clave2,clave3
```

---

## 💎 Modelo freemium y cadencia

| | **Free** | **VIP** |
|---|---|---|
| Noticias normales | Pulso cada `FREE_PULSE_HOURS` (def. 8 h, 2 noticias) + reporte 8 AM | Cada `FETCH_INTERVAL_MINUTES` (def. 120 min), **solo sus categorías** |
| Crisis global | ✅ Tiempo real | ✅ Tiempo real |
| A demanda (botón) | ✅ | ✅ |
| Voz IA (texto + audio) | ❌ | ✅ |
| Precios ETH/SOL + sentimiento | ❌ | ✅ |
| Panel de categorías | ❌ | ✅ |

Ajusta la cadencia sin tocar código vía `.env` (`FREE_PULSE_HOURS`, `FETCH_INTERVAL_MINUTES`).

---

## 🌐 APIs y capa gratis

**Funcionan sin API key:** Open-Meteo (clima), Edge-TTS (voz salida), Pollinations (imágenes),
RSS (noticias), CoinGecko (cripto).

**Requeridas (núcleo):** `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `SUPABASE_URL` + `SUPABASE_KEY`.

**Opcionales (feature-flag — si faltan, esa parte no se activa y nada se rompe):**
`GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `GITHUB_MODELS_TOKEN`, `FINNHUB_API_KEY`,
`OPENWEATHER_API_KEY`, `UPSTASH_REDIS_REST_URL` + `_TOKEN`.

---

## 🔑 Variables de entorno

Copia `.env.example` a `.env` y rellena. Mínimo para arrancar:

```env
TELEGRAM_BOT_TOKEN=123456:ABC...      # @BotFather
GROQ_API_KEY=gsk_...                   # console.groq.com (acepta varias con coma)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...

# Opcionales recomendadas
GEMINI_API_KEY=...                     # aistudio.google.com
FETCH_INTERVAL_MINUTES=120             # cadencia VIP
FREE_PULSE_HOURS=8                     # cadencia Free
```

Ver `.env.example` para la lista completa (OpenRouter, GitHub Models, Finnhub, Upstash, TTS, etc.).

---

## 💻 Instalación local

```bash
git clone https://github.com/Delnr91/botnew.git
cd botnew
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # y completa tus claves
python -m src.main
```

---

## ☁️ Despliegue en Google Cloud

El bot corre en una VM `e2-micro` (capa gratis). Primer despliegue:

```bash
# Crea la instancia (usa infra/deploy_gcloud.sh como referencia)
bash infra/deploy_gcloud.sh
```

El `startup.sh` clona el repo, crea el venv, instala dependencias y arranca el bot dentro de
`screen` para que los logs persistan.

---

## 🔄 Actualizar el bot (SSH)

> Conéctate a la VM, baja los cambios, instala dependencias nuevas y reinicia el bot.

```bash
# 1) Conectarse a la VM
gcloud compute ssh atlos-bot-vm --zone=us-central1-a

# 2) Actualizar código + dependencias + reiniciar (todo en uno)
cd ~/botnew && \
git pull && \
source venv/bin/activate && \
pip install -r requirements.txt && \
screen -S atlos -X quit 2>/dev/null; \
screen -dmS atlos python -m src.main && \
echo "✅ Atlos actualizado y corriendo en screen 'atlos'"

# 3) Ver los logs en vivo
screen -r atlos          # salir sin cerrar: Ctrl+A, luego D
```

**Nota:** `screen -dmS atlos ...` arranca el bot en segundo plano dentro de una sesión `screen`
llamada `atlos`. El `screen -S atlos -X quit` previo cierra cualquier instancia anterior para no
duplicar el bot.

---

## 🩺 Operación y troubleshooting

- **Ver logs:** `screen -r atlos` (salir con `Ctrl+A`, `D`).
- **Confirmar arranque:** en los logs deben aparecer `✅ Groq: N clave(s)`, `✅ Gemini inicializado`
  y `⏰ Scheduler: VIP cada 120min · Free cada 8h · Matutino 8:00`.
- **Bot duplicado / responde doble:** hay 2 procesos. Cierra todo con
  `screen -S atlos -X quit` y `pkill -f "src.main"`, luego vuelve a arrancar.
- **No llegan noticias:** revisa que el caché se llena (`NewsEngine: caché refrescado con N…`).
- **Caché se vacía al reiniciar:** normal sin Redis; configura `UPSTASH_REDIS_*` para persistirlo.
- **`429` en un LLM:** el router rota solo; agrega más claves (coma) u `OPENROUTER_API_KEY` para más respaldo.

---

## 🗺️ Roadmap

- [ ] **Multi-bot real (tenants)** con webhooks — base del modelo Agent-Bot-as-a-Service.
- [ ] Karma **por-usuario** (hoy es global).
- [ ] Filtros finos por keyword (equipo/juego/moneda favorita).
- [ ] Job dedicado de crisis cada 15-20 min (latencia < 30 min).
- [ ] Migrar `google-generativeai` → `google-genai`.
- [ ] Pagos USDT automáticos (CryptoPay).

---

<sub>Hecho para correr ligero en la capa gratis eterna de Google Cloud + Supabase. 🛰️</sub>
