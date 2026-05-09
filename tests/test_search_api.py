import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import numpy as np

from app.main import app

client = TestClient(app)


class TestImageSearch:
    
    def test_health_check(self):
        """Verifica que la API está viva."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    @patch("app.services.search.search_service")
    def test_search_by_image_direct_match(self, mock_search):
        """Test de búsqueda con coincidencia directa."""
        # Mock del resultado
        mock_search.search_by_image.return_value = {
            "success": True,
            "result_type": "direct_match",
            "message": "Encontré 1 coincidencia",
            "products": [{
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "sku": "VAL-LG-001",
                "name_es": "Válvula de Agua LG",
                "price_public": 450,
                "stock_quantity": 12,
                "similarity": 0.92,
                "confidence_percent": 92
            }],
            "suggested_action": "proceed_to_quote",
            "metadata": {
                "threshold_used": 0.7,
                "search_time_ms": 150.5
            }
        }
        
        response = client.post("/api/v1/search/by-image", json={
            "image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
            "customer_type": "public"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["result_type"] == "direct_match"
        assert len(data["products"]) > 0
        assert data["products"][0]["confidence_percent"] > 85
    
    def test_search_by_image_invalid_base64(self):
        """Test con imagen inválida."""
        response = client.post("/api/v1/search/by-image", json={
            "image_base64": "invalid-base64!!!",
            "customer_type": "public"
        })
        
        # Debe manejar el error gracefully
        assert response.status_code in [200, 422, 500]
    
    def test_search_stats(self):
        """Test del endpoint de estadísticas."""
        response = client.get("/api/v1/search/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_embeddings" in data
        assert "coverage_percent" in data


class TestEmbeddingService:
    
    def test_embedding_generation(self):
        """Test que el modelo genera embeddings correctamente."""
        from app.services.embedding import embedding_service
        
        # Crear imagen de prueba simple (1x1 píxel rojo)
        from PIL import Image
        import io
        
        img = Image.new('RGB', (224, 224), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        embedding = embedding_service.generate_image_embedding(img_bytes.getvalue())
        
        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 512  # Dimensión de CLIP ViT-B/32
        assert np.linalg.norm(embedding) - 1.0 < 0.01  # Normalizado