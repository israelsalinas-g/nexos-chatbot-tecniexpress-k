from fastapi import FastAPI

app = FastAPI(
    title="Proyecto FastAPI",
    description="API inicial creada con FastAPI.",
    version="0.1.0",
)


@app.get("/")
async def read_root():
    return {"message": "¡Hola desde FastAPI!"}


@app.get("/ping")
async def ping():
    return {"message": "pong"}
