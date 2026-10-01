# Debian 13 (trixie) trae postgresql-client-17 en sus repos oficiales.
# El cliente pg_dump debe ser >= a la versión del servidor PostgreSQL.
FROM python:3.12-slim-trixie

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-client-17 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV BACKUP_DIR=/tmp/backups
EXPOSE 8000
# Render inyecta $PORT; en local usamos 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
