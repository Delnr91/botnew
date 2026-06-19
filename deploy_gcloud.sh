#!/bin/bash
# deploy_gcloud.sh — Script de Deploy para Google Cloud Compute Engine
# =====================================================================
# Costo estimado: ~$4.50 USD/mes (e2-micro) con tus $300 de crédito = ~66 meses
# O $7.50/mes (e2-small) = ~40 meses de operación gratis
#
# INSTRUCCIONES:
# 1. Instala Google Cloud CLI: https://cloud.google.com/sdk/docs/install
# 2. Autentícate: gcloud auth login
# 3. Crea un proyecto: gcloud projects create atlos-bot --name="Atlos Bot"
# 4. Configura el proyecto: gcloud config set project atlos-bot
# 5. Ejecuta este script: bash deploy_gcloud.sh

echo "🚀 Desplegando Atlos Bot en Google Cloud..."

# Crear la VM más económica posible
gcloud compute instances create atlos-bot-vm \
    --zone=us-central1-a \
    --machine-type=e2-micro \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=10GB \
    --tags=atlos-bot \
    --metadata-from-file=startup-script=startup.sh

echo "✅ VM creada. Ahora conectándose..."
echo ""
echo "Para conectarte a la VM:"
echo "  gcloud compute ssh atlos-bot-vm --zone=us-central1-a"
echo ""
echo "Una vez dentro, el bot se iniciará automáticamente."
