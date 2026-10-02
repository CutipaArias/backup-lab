import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .db import database_url

BACKUP_DIR = Path(os.environ.get("BACKUP_DIR", "/tmp/backups"))
RETENTION = int(os.environ.get("BACKUP_RETENTION", "5"))
NAME_RE = re.compile(r"^backup_\d{8}_\d{6}\.dump$")


class BackupError(Exception):
    pass


def _run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise BackupError(result.stderr.strip() or "el comando falló sin mensaje")


def create_backup() -> dict:
    """Backup lógico completo en formato custom (-Fc): comprimido y restaurable con pg_restore."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = datetime.now(timezone.utc).strftime("backup_%Y%m%d_%H%M%S.dump")
    path = BACKUP_DIR / name
    # --no-owner y --no-acl: en bases administradas (Render) el usuario de la app
    # no puede reasignar dueños ni permisos por defecto al restaurar.
    _run(
        [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(path),
            database_url(),
        ]
    )
    _apply_retention()
    return _describe(path)


def _all_files() -> list[Path]:
    if not BACKUP_DIR.exists():
        return []
    return sorted(p for p in BACKUP_DIR.glob("backup_*.dump") if NAME_RE.match(p.name))


def _apply_retention() -> None:
    files = _all_files()
    if RETENTION > 0:
        for old in files[:-RETENTION]:
            old.unlink(missing_ok=True)


def _describe(path: Path) -> dict:
    stat = path.stat()
    return {
        "nombre": path.name,
        "bytes": stat.st_size,
        "creado": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def list_backups() -> list[dict]:
    return [_describe(p) for p in reversed(_all_files())]


def resolve(name: str) -> Path:
    # La regex evita rutas tipo ../../etc/passwd
    if not NAME_RE.match(name):
        raise BackupError("nombre de backup inválido")
    path = BACKUP_DIR / name
    if not path.is_file():
        raise FileNotFoundError(name)
    return path


def restore_backup(name: str) -> None:
    path = resolve(name)
    _run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "--dbname",
            database_url(),
            str(path),
        ]
    )
