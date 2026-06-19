#!/bin/bash
# startup.sh — Se ejecuta automáticamente al iniciar la VM en Google Cloud
# =========================================================================

# Actualizar sistema
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git screen

# Crear entorno virtual
cd /home
git clone https://github.com/TU_USUARIO/atlos-bot.git || true
cd atlos-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ejecutar el bot en segundo plano con screen (sobrevive si cierras la terminal)
screen -dmS atlos python3 bot.py

echo "✅ Atlos Bot ejecutándose en segundo plano (screen -r atlos para ver logs)"
