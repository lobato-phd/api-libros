# API de libros

La API de libros del ejercicio 6 del módulo *APIs y Servicios de Datos*, lista para desplegar en Render.

## En local

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:API_KEY = "una-clave-larga"
uvicorn main:app --reload
```

Pruebas: `pip install pytest httpx` y `pytest -v`.

## En Render

| Campo | Valor |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Environment | `API_KEY` |
| Health Check Path | `/health` |
