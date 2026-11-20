# test_api.py — Ejercicio 6: el contrato de la API, escrito de forma ejecutable
# Ejecutar: pytest -v
import os

os.environ["API_KEY"] = "clave-de-test"  # como haría la plataforma: inyectar antes de arrancar

import pytest
from fastapi.testclient import TestClient

import main
from main import app

CLAVE = {"X-API-Key": "clave-de-test"}
NUEVO = {"titulo": "El Quijote", "precio": 12.5, "valoracion": 5}


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def test_health_responde_ok(cliente):
    assert cliente.get("/health").json()["status"] == "ok"


def test_leer_es_publico(cliente):
    assert cliente.get("/v1/libros").status_code == 200


def test_libro_inexistente_da_404(cliente):
    assert cliente.get("/v1/libros/99999").status_code == 404


def test_crear_sin_clave_da_401(cliente):
    assert cliente.post("/v1/libros", json=NUEVO).status_code == 401


def test_crear_con_clave_erronea_da_401(cliente):
    r = cliente.post("/v1/libros", json=NUEVO, headers={"X-API-Key": "otra"})
    assert r.status_code == 401


def test_crear_con_clave_da_201_y_se_puede_leer(cliente):
    r = cliente.post("/v1/libros", json=NUEVO, headers=CLAVE)
    assert r.status_code == 201
    assert cliente.get(f"/v1/libros/{r.json()['id']}").json()["titulo"] == "El Quijote"


def test_valoracion_fuera_de_rango_da_422(cliente):
    r = cliente.post("/v1/libros", json={**NUEVO, "valoracion": 7}, headers=CLAVE)
    assert r.status_code == 422


def test_proveedor_caido_da_503_y_no_500(cliente, monkeypatch):
    monkeypatch.setattr(main, "URL_CAMBIO", "http://127.0.0.1:9/no-existe")  # puerto cerrado
    assert cliente.get("/v1/libros/1/precio-eur").status_code == 503


def test_cada_respuesta_mide_su_tiempo(cliente):
    assert "X-Tiempo-Proceso" in cliente.get("/health").headers
