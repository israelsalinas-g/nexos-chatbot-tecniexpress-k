# Proyecto FastAPI

Proyecto inicial de FastAPI con una API mínima y dos rutas básicas.

## Requisitos

- Python 3.11+ recomendado
- `git` instalado para control de versiones

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Endpoints

- `/` → mensaje de bienvenida
- `/ping` → respuesta `pong`

## Archivos principales

- `main.py`: aplicación FastAPI y rutas básicas.
- `requirements.txt`: dependencias de FastAPI y Uvicorn.
- `.gitignore`: exclusiones comunes para entornos Python.

## Uso

Una vez levantada la aplicación, abre en el navegador:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/ping`

## Desarrollo

Para agregar rutas nuevas, edita `main.py` y reinicia el servidor.
