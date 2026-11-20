# main.py — Ejercicio 6 (solución): la API de libros, lista para producción
# Local:  $env:API_KEY = "una-clave-larga"; uvicorn main:app --reload
# Render: uvicorn main:app --host 0.0.0.0 --port $PORT   (API_KEY en Environment)
import json
import logging
import os
import secrets
import time
from itertools import count
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")
app = FastAPI(title="API de Libros", version="1.1")

API_KEY = os.environ.get("API_KEY")  # secreto: lo inyecta la plataforma
URL_CAMBIO = os.environ.get("URL_CAMBIO", "https://api.frankfurter.dev/v1/latest")  # configuración


# ---------- Contratos ----------
class Libro(BaseModel):
    titulo: str = Field(min_length=1, max_length=300)
    precio: float = Field(gt=0, description="libras esterlinas")
    valoracion: int = Field(ge=1, le=5)
    disponible: bool = True


class LibroParcial(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=300)
    precio: float | None = Field(default=None, gt=0)
    valoracion: int | None = Field(default=None, ge=1, le=5)
    disponible: bool | None = None


class LibroOut(Libro):
    id: int


class ListaLibrosOut(BaseModel):
    total: int
    resultados: list[LibroOut]


# ---------- Datos: el JSON del scraper si existe, si no los de ejemplo ----------
_ids = count(1)
LIBROS: dict[int, dict] = {}
_fichero = Path(__file__).with_name("libros.json")
_semilla = (json.loads(_fichero.read_text(encoding="utf-8")) if _fichero.exists() else
            [{"titulo": "A Light in the Attic", "precio": 51.77, "valoracion": 3},
             {"titulo": "Sharp Objects", "precio": 47.82, "valoracion": 4},
             {"titulo": "Sapiens: A Brief History of Humankind", "precio": 54.23, "valoracion": 5}])
for datos in _semilla:
    nuevo = next(_ids)
    LIBROS[nuevo] = {"id": nuevo, **Libro(**datos).model_dump()}  # validado también al cargar


def buscar(libro_id: int) -> dict:
    if libro_id not in LIBROS:
        raise HTTPException(404, "Libro no encontrado")
    return LIBROS[libro_id]


# ---------- Seguridad: API key para escribir ----------
cabecera = APIKeyHeader(name="X-API-Key")


def verificar(key: str = Security(cabecera)):
    if API_KEY is None:
        raise HTTPException(500, "El servidor no tiene configurada su API key")
    if not secrets.compare_digest(key, API_KEY):
        raise HTTPException(401, "API key inválida")


# ---------- Middleware: cuánto tarda cada petición ----------
@app.middleware("http")
async def medir_tiempo(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Tiempo-Proceso"] = f"{time.perf_counter() - t0:.4f}"
    return response


# ---------- Rutas ----------
@app.get("/health")
def health():
    return {"status": "ok", "libros": len(LIBROS)}


@app.get("/v1/libros", response_model=ListaLibrosOut)
def listar(max_precio: float | None = Query(default=None, gt=0),
           valoracion_min: int | None = Query(default=None, ge=1, le=5),
           limite: int | None = Query(default=None, ge=1),
           desplazamiento: int = Query(default=0, ge=0)):
    datos = list(LIBROS.values())
    if max_precio is not None:
        datos = [l for l in datos if l["precio"] <= max_precio]
    if valoracion_min is not None:
        datos = [l for l in datos if l["valoracion"] >= valoracion_min]
    fin = None if limite is None else desplazamiento + limite
    return {"total": len(datos), "resultados": datos[desplazamiento:fin]}


@app.get("/v1/libros/{libro_id}", response_model=LibroOut)
def detalle(libro_id: int):
    return buscar(libro_id)


@app.get("/v1/libros/{libro_id}/precio-eur")
def precio_eur(libro_id: int):
    libro = buscar(libro_id)
    try:
        r = requests.get(URL_CAMBIO, params={"base": "GBP", "symbols": "EUR"}, timeout=5)
        r.raise_for_status()
        tasa = r.json()["rates"]["EUR"]
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.error(f"Proveedor de cambio caído: {exc}")
        raise HTTPException(503, "Servicio de cambio no disponible, reintenta en unos minutos")
    return {"id": libro_id, "precio_gbp": libro["precio"], "tasa": tasa,
            "precio_eur": round(libro["precio"] * tasa, 2)}


@app.post("/v1/libros", response_model=LibroOut, status_code=201,
          dependencies=[Depends(verificar)])
def crear(libro: Libro):
    nuevo = next(_ids)
    LIBROS[nuevo] = {"id": nuevo, **libro.model_dump()}
    return LIBROS[nuevo]


@app.patch("/v1/libros/{libro_id}", response_model=LibroOut, dependencies=[Depends(verificar)])
def modificar(libro_id: int, cambios: LibroParcial):
    libro = buscar(libro_id)
    libro.update(cambios.model_dump(exclude_unset=True))
    return libro


@app.delete("/v1/libros/{libro_id}", status_code=204, dependencies=[Depends(verificar)])
def borrar(libro_id: int):
    buscar(libro_id)
    del LIBROS[libro_id]
