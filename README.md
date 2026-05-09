# Proyecto FastAPI

Proyecto inicial de FastAPI con una ruta básica.

## Requisitos

- Python 3.11+ recomendado

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

## Rutas

- `/` → mensaje de bienvenida
- `/ping` → respuesta `pong`
