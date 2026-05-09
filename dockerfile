FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./app/

# Puerto (Railway sobrescribe con $PORT)
EXPOSE 8000

# Comando de inicio
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}