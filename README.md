# Backup Lab · estrategia de respaldo con PostgreSQL

App mínima (FastAPI + PostgreSQL) para demostrar backups lógicos completos con `pg_dump`,
restauración con `pg_restore`, retención de copias y un backup programado fuera del servidor.

## Probar en local (2 comandos)

```bash
docker compose up --build
# abrir http://localhost:8000   (token de administrador: demo-token)
```

Sin Docker: necesitas Python 3.12, PostgreSQL 17 y su cliente (`pg_dump`).

```bash
cp .env.example .env && export $(cat .env | xargs)
pip install -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload
```

## Qué hace

| Endpoint | Para qué |
|---|---|
| `GET /` | Interfaz web mínima |
| `GET/POST/DELETE /api/notas` | Datos de ejemplo |
| `POST /api/backups` | Backup completo (`pg_dump -Fc`) con retención de N copias |
| `GET /api/backups` | Lista de backups |
| `GET /api/backups/{nombre}` | Descarga |
| `POST /api/backups/{nombre}/restore` | Restaura con `pg_restore --clean` |
| `GET /health` | Chequeo de salud |

Los endpoints de backup exigen la cabecera `X-Admin-Token`.

## Automatización (GitHub Actions)

- `ci.yml`: en cada push corre los tests contra PostgreSQL 17, construye la imagen Docker y,
  si estás en `main`, dispara el despliegue en Render con un Deploy Hook.
- `backup.yml`: cada día a las 06:00 UTC hace un `pg_dump` de la base en producción, lo cifra con AES-256, lo guarda como
  artefacto 7 días y lo restaura en una base limpia para comprobar que sirve.

## Desplegar en Render

1. Sube este repo a GitHub (público).
2. Render → **New → Blueprint** → elige el repo. Crea la BD `backuplab-db` y el servicio `backuplab`.
3. En el servicio: **Settings → Deploy Hook** → copia la URL.
4. En GitHub → **Settings → Secrets and variables → Actions** crea:
   - `RENDER_DEPLOY_HOOK`: la URL del paso 3.
   - `BACKUP_PASSPHRASE`: una frase larga y aleatoria; cifra los backups antes de subirlos.
   - `BACKUP_DATABASE_URL`: la *External Database URL* de `backuplab-db`
     (Render → la BD → Connect → External).
5. Lee el `ADMIN_TOKEN` generado en Render → servicio → Environment.

Limitaciones del plan gratis de Render: el servicio se duerme tras ~15 min sin tráfico y la base
gratuita expira a los 30 días. El disco del contenedor es efímero: por eso existe el backup
programado que guarda copias fuera del servidor.
