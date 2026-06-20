#!/bin/bash
# startup.sh — Se ejecuta automáticamente al iniciar la VM en Google Cloud
# =========================================================================

# Actualizar sistema
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git screen

# Crear entorno virtual
cd /home
# IMPORTANTE: Reemplaza delnr91/botnew por tu nombre de usuario y repo si cambia
git clone https://github.com/delnr91/botnew.git || true
cd botnew

# Crear el archivo .env con las credenciales (Debes inyectar esto manualmente o a través de Secrets)
cat <<EOT >> .env
# Sustituye estas llaves antes del despliegue final
TELEGRAM_TOKEN=tu_token_aqui
SUPABASE_URL=https://fbmugscywqbdabuedfox.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
GROQ_API_KEY=tu_groq_aqui
EOT

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ejecutar el bot en segundo plano con screen
screen -dmS atlos python -m src.main

echo "✅ Atlos Bot ejecutándose en segundo plano (screen -r atlos para ver logs)"
