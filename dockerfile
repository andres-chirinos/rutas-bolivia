# Dockerfile para iniciar un servicio FastAPI (workdir: /src)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

#WORKDIR /src

# Dependencias del sistema (opcional, necesarias para compilar paquetes)
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends build-essential && \
#     rm -rf /var/lib/apt/lists/*

# Copiar y instalar dependencias si existen; asegurar fastapi + uvicorn
COPY requirements.txt ./ 
RUN pip install --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn[standard] && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copiar el código de la aplicación
COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "src.adapters.api.app:app", "--host", "0.0.0.0", "--port", "8000"]