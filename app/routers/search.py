from fastapi import APIRouter, HTTPException, status
from typing import Optional

from app.models.schemas import ImageSearchRequest, ImageSearchResponse, EmbeddingStats
from app.services.search import search_service
from app.models.database import get_supabase_client

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("/by-image", response_model=ImageSearchResponse)
async def search_by_image(request: ImageSearchRequest):
    """
    Busca productos por similitud visual usando una imagen.
    
    - **image_base64**: Imagen en base64 (con o sin prefijo data URI)
    - **category_id**: Filtrar por categoría (opcional)
    - **brand_id**: Filtrar por marca (opcional)
    - **customer_type**: Tipo de cliente para precios (public/technician/wholesale)
    - **max_results**: Máximo de resultados (1-10)
    - **match_threshold**: Umbral personalizado de similitud (0.0-1.0)
    """
    try:
        response = await search_service.search_by_image(
            image_base64=request.image_base64,
            category_id=request.category_id,
            brand_id=request.brand_id,
            customer_type=request.customer_type,
            max_results=request.max_results,
            match_threshold=request.match_threshold
        )
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando búsqueda: {str(e)}"
        )


@router.get("/stats", response_model=EmbeddingStats)
async def get_embedding_stats():
    """Obtiene estadísticas de cobertura de embeddings."""
    try:
        supabase = get_supabase_client()
        result = supabase.rpc("get_embedding_stats").execute()
        data = result.data[0] if result.data else {}
        
        return EmbeddingStats(
            total_embeddings=data.get("total_embeddings", 0),
            total_products=data.get("total_products", 0),
            coverage_percent=data.get("coverage_percent", 0.0)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )