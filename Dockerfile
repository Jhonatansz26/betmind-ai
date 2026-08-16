# BetMind AI — API (despliegue determinista con Docker)
# Python 3.11 fijo (misma versión que CI). Render detecta este archivo
# automáticamente y usa Docker en vez del runtime nativo.

FROM python:3.11-slim

WORKDIR /app

# Dependencias del backend.
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --no-cache-dir -r apps/api/requirements.txt

# Paquete ML (instalado como wheel normal, no editable).
COPY packages/ml ./packages/ml
RUN pip install --no-cache-dir ./packages/ml

# Resto del código.
COPY apps ./apps
COPY scripts ./scripts

# El Plan C (crawl4ai/playwright) degrada si los browsers no están; el
# sistema cae a ESPN/SofaScore igual que en CI. No se instalan browsers
# para mantener la imagen liviana.
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
