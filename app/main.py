import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import backup
from .db import connect, init_db

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Backup Lab", version="1.0.0", lifespan=lifespan)


def require_token(x_admin_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(503, "ADMIN_TOKEN no está configurado en el servidor")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "token inválido")


class NotaIn(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    with connect() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/notas")
def listar_notas():
    with connect() as conn:
        rows = conn.execute("SELECT id, titulo, creado FROM notas ORDER BY id DESC").fetchall()
    return [{"id": r[0], "titulo": r[1], "creado": r[2].isoformat()} for r in rows]


@app.post("/api/notas", status_code=201)
def crear_nota(nota: NotaIn):
    with connect() as conn:
        row = conn.execute(
            "INSERT INTO notas (titulo) VALUES (%s) RETURNING id, titulo, creado", (nota.titulo,)
        ).fetchone()
    return {"id": row[0], "titulo": row[1], "creado": row[2].isoformat()}


@app.delete("/api/notas/{nota_id}", status_code=204)
def borrar_nota(nota_id: int):
    with connect() as conn:
        cur = conn.execute("DELETE FROM notas WHERE id = %s", (nota_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "nota no encontrada")


@app.get("/api/backups", dependencies=[Depends(require_token)])
def listar_backups():
    return backup.list_backups()


@app.post("/api/backups", status_code=201, dependencies=[Depends(require_token)])
def crear_backup():
    try:
        return backup.create_backup()
    except backup.BackupError as exc:
        raise HTTPException(500, f"pg_dump falló: {exc}")


@app.get("/api/backups/{nombre}", dependencies=[Depends(require_token)])
def descargar_backup(nombre: str):
    try:
        path = backup.resolve(nombre)
    except backup.BackupError as exc:
        raise HTTPException(400, str(exc))
    except FileNotFoundError:
        raise HTTPException(404, "backup no encontrado")
    return FileResponse(path, filename=nombre, media_type="application/octet-stream")


@app.post("/api/backups/{nombre}/restore", dependencies=[Depends(require_token)])
def restaurar_backup(nombre: str):
    try:
        backup.restore_backup(nombre)
    except FileNotFoundError:
        raise HTTPException(404, "backup no encontrado")
    except backup.BackupError as exc:
        raise HTTPException(500, f"pg_restore falló: {exc}")
    return {"restaurado": nombre}
