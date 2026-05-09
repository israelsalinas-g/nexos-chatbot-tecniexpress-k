from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from uuid import UUID


class ImageSearchRequest(BaseModel):
    image_base64: str = Field(..., description="Imagen en base64 con o sin prefijo data URI")
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    customer_type: Literal["public", "technician", "wholesale"] = "public"
    max_results: int = Field(default=5, ge=1, le=10)
    match_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ProductMatch(BaseModel):
    product_id: UUID
    sku: str
    name_es: str
    name_en: Optional[str]
    part_number: Optional[str]
    price_public: int
    price_technician: int
    price_wholesale: int
    stock_quantity: int
    is_active: bool
    image_url: str
    similarity: float
    confidence_percent: int
    brand_name: Optional[str]
    category_name: Optional[str]


class SearchMetadata(BaseModel):
    threshold_used: float
    customer_type: str
    filters_applied: dict
    total_candidates: int
    search_time_ms: float


class ImageSearchResponse(BaseModel):
    success: bool
    result_type: Literal["direct_match", "multiple_options", "no_match"]
    message: str
    products: List[ProductMatch]
    suggested_action: str
    alternatives: Optional[List[str]] = None
    metadata: SearchMetadata


class EmbeddingStats(BaseModel):
    total_embeddings: int
    total_products: int
    coverage_percent: float