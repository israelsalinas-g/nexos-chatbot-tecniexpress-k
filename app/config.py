from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_anon_key: str
    
    # Modelo de embeddings
    clip_model: str = "sentence-transformers/clip-ViT-B-32"
    embedding_dimension: int = 512
    
    # Búsqueda
    default_match_threshold: float = 0.70
    high_confidence_threshold: float = 0.85
    default_match_count: int = 5
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_image_size_mb: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()