import time
from typing import List, Optional, Tuple, Literal
from uuid import UUID

from app.models.database import get_supabase_client
from app.models.schemas import ProductMatch, ImageSearchResponse, SearchMetadata
from app.services.embedding import embedding_service
from app.config import get_settings


class SearchService:
    def __init__(self):
        self.supabase = get_supabase_client()
        self.settings = get_settings()
    
    async def search_by_image(
        self,
        image_base64: str,
        category_id: Optional[UUID] = None,
        brand_id: Optional[UUID] = None,
        customer_type: Literal["public", "technician", "wholesale"] = "public",
        max_results: int = 5,
        match_threshold: Optional[float] = None
    ) -> ImageSearchResponse:
        start_time = time.time()
        
        threshold = match_threshold or self.settings.default_match_threshold
        
        # 1. Generar embedding de la imagen del cliente
        query_embedding = embedding_service.generate_image_embedding(image_base64)
        embedding_list = embedding_service.embedding_to_list(query_embedding)
        
        # 2. Llamar RPC en Supabase
        result = self.supabase.rpc(
            "search_products_by_image",
            {
                "query_embedding": embedding_list,
                "match_threshold": 0.60,  # Umbral bajo para no perder candidatos
                "match_count": max_results * 2,  # Pedimos más para filtrar después
                "filter_category_id": str(category_id) if category_id else None,
                "filter_brand_id": str(brand_id) if brand_id else None
            }
        ).execute()
        
        candidates = result.data or []
        search_time = (time.time() - start_time) * 1000
        
        # 3. Procesar y filtrar resultados
        processed = self._process_results(candidates, customer_type, threshold)
        
        # 4. Clasificar por nivel de confianza
        high_confidence = [p for p in processed if p.similarity >= self.settings.high_confidence_threshold]
        medium_confidence = [p for p in processed if self.settings.default_match_threshold <= p.similarity < self.settings.high_confidence_threshold]
        
        # 5. Construir respuesta
        if high_confidence:
            return self._build_direct_match_response(
                high_confidence[:max_results], 
                customer_type, 
                threshold, 
                search_time,
                len(candidates)
            )
        elif medium_confidence:
            return self._build_multiple_options_response(
                medium_confidence[:max_results], 
                customer_type, 
                threshold, 
                search_time,
                len(candidates)
            )
        else:
            return self._build_no_match_response(
                threshold, 
                search_time,
                len(candidates)
            )
    
    def _process_results(
        self, 
        candidates: List[dict], 
        customer_type: str,
        threshold: float
    ) -> List[ProductMatch]:
        """Procesa los candidatos del RPC y selecciona precio según tipo de cliente."""
        processed = []
        
        for c in candidates:
            # Seleccionar precio según tipo de cliente
            if customer_type == "technician":
                price = c.get("product_price_technician", 0)
            elif customer_type == "wholesale":
                price = c.get("product_price_wholesale", 0)
            else:
                price = c.get("product_price_public", 0)
            
            similarity = float(c.get("similarity", 0))
            
            match = ProductMatch(
                product_id=c["product_id"],
                sku=c["product_sku"],
                name_es=c["product_name_es"],
                name_en=c.get("product_name_en"),
                part_number=c.get("product_part_number"),
                price_public=c.get("product_price_public", 0),
                price_technician=c.get("product_price_technician", 0),
                price_wholesale=c.get("product_price_wholesale", 0),
                stock_quantity=c.get("product_stock_quantity", 0),
                is_active=c.get("product_is_active", True),
                image_url=c["image_url"],
                similarity=similarity,
                confidence_percent=round(similarity * 100),
                brand_name=c.get("brand_name"),
                category_name=c.get("category_name")
            )
            processed.append(match)
        
        # Ordenar por similitud descendente
        processed.sort(key=lambda x: x.similarity, reverse=True)
        return processed
    
    def _build_direct_match_response(
        self,
        products: List[ProductMatch],
        customer_type: str,
        threshold: float,
        search_time: float,
        total_candidates: int
    ) -> ImageSearchResponse:
        return ImageSearchResponse(
            success=True,
            result_type="direct_match",
            message=f"Encontré {len(products)} coincidencia(s) con alta confianza:",
            products=products,
            suggested_action="proceed_to_quote",
            metadata=SearchMetadata(
                threshold_used=threshold,
                customer_type=customer_type,
                filters_applied={},
                total_candidates=total_candidates,
                search_time_ms=round(search_time, 2)
            )
        )
    
    def _build_multiple_options_response(
        self,
        products: List[ProductMatch],
        customer_type: str,
        threshold: float,
        search_time: float,
        total_candidates: int
    ) -> ImageSearchResponse:
        return ImageSearchResponse(
            success=True,
            result_type="multiple_options",
            message="Encontré estas posibles coincidencias. ¿Alguna de estas es el repuesto que buscas?",
            products=products,
            suggested_action="request_confirmation",
            metadata=SearchMetadata(
                threshold_used=threshold,
                customer_type=customer_type,
                filters_applied={},
                total_candidates=total_candidates,
                search_time_ms=round(search_time, 2)
            )
        )
    
    def _build_no_match_response(
        self,
        threshold: float,
        search_time: float,
        total_candidates: int
    ) -> ImageSearchResponse:
        return ImageSearchResponse(
            success=True,
            result_type="no_match",
            message="No encontré coincidencias claras con esa imagen. ¿Puedes enviar otra foto desde otro ángulo, o indicarme la marca y modelo del electrodoméstico?",
            products=[],
            suggested_action="request_more_info",
            alternatives=[
                "Enviar otra foto (diferente ángulo, mejor iluminación)",
                "Indicar marca y modelo del electrodoméstico",
                "Buscar por número de parte si lo conoces"
            ],
            metadata=SearchMetadata(
                threshold_used=threshold,
                customer_type="public",
                filters_applied={},
                total_candidates=total_candidates,
                search_time_ms=round(search_time, 2)
            )
        )


# Singleton
search_service = SearchService()