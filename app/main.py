from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import get_settings
from app.routers import search


def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="Visual Search API - Repuestos",
        description="API de búsqueda visual por similitud para catálogo de repuestos de electrodomésticos",
        version="1.0.0"
    )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # En producción, restringir a tus dominios
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Routers
    app.include_router(search.router)
    
    @app.get("/health")
    async def health_check():
        return {"status": "ok", "service": "visual-search-api"}
    
    @app.get("/")
    async def root():
        return {
            "message": "Visual Search API",
            "docs": "/docs",
            "endpoints": {
                "search_by_image": "POST /api/v1/search/by-image",
                "stats": "GET /api/v1/search/stats"
            }
        }
    
    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )