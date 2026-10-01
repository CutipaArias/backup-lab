import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/notas")
os.environ["ADMIN_TOKEN"] = "token-de-prueba"

from app import backup  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"X-Admin-Token": "token-de-prueba"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path)
    with TestClient(app) as c:
        for n in c.get("/api/notas").json():
            c.delete(f"/api/notas/{n['id']}")
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_crud_notas(client):
    r = client.post("/api/notas", json={"titulo": "primera"})
    assert r.status_code == 201
    assert [n["titulo"] for n in client.get("/api/notas").json()] == ["primera"]
    assert client.delete(f"/api/notas/{r.json()['id']}").status_code == 204


def test_backups_exigen_token(client):
    assert client.get("/api/backups").status_code == 401
    assert client.post("/api/backups", headers={"X-Admin-Token": "mal"}).status_code == 401


def test_nombre_invalido_rechazado(client):
    r = client.get("/api/backups/..%2F..%2Fetc%2Fpasswd", headers=AUTH)
    assert r.status_code in (400, 404)


def test_backup_y_restauracion(client):
    client.post("/api/notas", json={"titulo": "uno"})
    client.post("/api/notas", json={"titulo": "dos"})

    creado = client.post("/api/backups", headers=AUTH)
    assert creado.status_code == 201
    nombre = creado.json()["nombre"]
    assert nombre in [b["nombre"] for b in client.get("/api/backups", headers=AUTH).json()]

    # Simulamos el desastre: borramos todo
    for n in client.get("/api/notas").json():
        client.delete(f"/api/notas/{n['id']}")
    assert client.get("/api/notas").json() == []

    r = client.post(f"/api/backups/{nombre}/restore", headers=AUTH)
    assert r.status_code == 200, r.text
    assert sorted(n["titulo"] for n in client.get("/api/notas").json()) == ["dos", "uno"]


def test_retencion(client, monkeypatch):
    monkeypatch.setattr(backup, "RETENTION", 2)
    for i in range(4):
        (backup.BACKUP_DIR / f"backup_20260101_00000{i}.dump").write_bytes(b"x")
    client.post("/api/backups", headers=AUTH)
    assert len(client.get("/api/backups", headers=AUTH).json()) == 2
