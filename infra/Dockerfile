# Dockerfile para Atlos Bot
FROM python:3.11-slim

WORKDIR /app

# Copiar dependencias e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Ejecutar el bot
CMD ["python", "-m", "src.main"]
