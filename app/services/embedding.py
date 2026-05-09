import io
import base64
import re
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer
from typing import List, Tuple
import torch

from app.config import get_settings


class EmbeddingService:
    _instance = None
    _model = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            self._load_model()
    
    def _load_model(self):
        settings = get_settings()
        print(f"🔄 Cargando modelo CLIP: {settings.clip_model}")
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model = SentenceTransformer(settings.clip_model, device=device)
        self._dimension = settings.embedding_dimension
        
        print(f"✅ Modelo cargado en {device}. Dimensión: {self._dimension}")
    
    @property
    def model(self):
        return self._model
    
    def _decode_base64_image(self, base64_string: str) -> Image.Image:
        """Decodifica una imagen base64, con o sin prefijo data URI."""
        # Remover prefijo si existe
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        
        # Limpiar caracteres no válidos
        base64_string = re.sub(r'[^A-Za-z0-9+/=]', '', base64_string)
        
        image_bytes = base64.b64decode(base64_string)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    def generate_image_embedding(self, image_input: str | bytes) -> np.ndarray:
        """
        Genera embedding de una imagen.
        
        Args:
            image_input: Base64 string o bytes de la imagen
        """
        if isinstance(image_input, str):
            image = self._decode_base64_image(image_input)
        else:
            image = Image.open(io.BytesIO(image_input)).convert("RGB")
        
        # CLIP de sentence-transformers ya maneja el preprocessing internamente
        embedding = self._model.encode(image, convert_to_numpy=True)
        
        # Normalizar (importante para cosine similarity)
        embedding = embedding / np.linalg.norm(embedding)
        
        return embedding
    
    def generate_text_embedding(self, text: str) -> np.ndarray:
        """Genera embedding de texto."""
        embedding = self._model.encode(text, convert_to_numpy=True)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding
    
    def generate_multimodal_embedding(
        self, 
        image_input: str | bytes,
        product_name: str = "",
        product_description: str = ""
    ) -> np.ndarray:
        """
        Combina embedding de imagen + texto para mejor precisión en repuestos.
        70% imagen + 30% texto
        """
        image_emb = self.generate_image_embedding(image_input)
        
        if product_name:
            text_input = f"{product_name} {product_description}".strip()[:77]
            text_emb = self.generate_text_embedding(text_input)
            
            # Combinar: 70% imagen + 30% texto
            combined = image_emb * 0.7 + text_emb * 0.3
            combined = combined / np.linalg.norm(combined)
            return combined
        
        return image_emb
    
    def embedding_to_list(self, embedding: np.ndarray) -> List[float]:
        """Convierte numpy array a lista de Python para JSON/PostgreSQL."""
        return embedding.astype(np.float32).tolist()


# Singleton global
embedding_service = EmbeddingService()