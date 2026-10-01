import os
import time

import psycopg


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), autocommit=True)


def init_db(retries: int = 15, wait: float = 2.0) -> None:
    """Crea la tabla si no existe. Reintenta porque la BD puede tardar en arrancar."""
    last = None
    for _ in range(retries):
        try:
            with connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS notas (
                        id      SERIAL PRIMARY KEY,
                        titulo  TEXT NOT NULL,
                        creado  TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
            return
        except psycopg.OperationalError as exc:
            last = exc
            time.sleep(wait)
    raise RuntimeError(f"No se pudo conectar a la base de datos: {last}")
