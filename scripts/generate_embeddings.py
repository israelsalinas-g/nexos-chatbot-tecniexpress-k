#!/usr/bin/env python3
"""
Script para generar embeddings de todas las imágenes del catálogo existente.
Ejecutar una sola vez al inicio, o cuando se agreguen productos masivamente.
"""

import asyncio
import os
import sys
from pathlib import Path

# Agregar app al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from supabase import create_client
from tqdm import tqdm

from app.config import get_settings
from app.services.embedding import embedding_service
from app.models.database import get_supabase_client


async def download_image(url: str) -> bytes | None:
    """Descarga imagen desde URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.content
            print(f"⚠️ Error {response.status_code} descargando: {url}")
            return None
    except Exception as e:
        print(f"❌ Error descargando {url}: {e}")
        return None


async def process_product_images():
    """Procesa todas las imágenes de productos y genera embeddings."""
    settings = get_settings()
    supabase = get_supabase_client()
    
    print("🔍 Obteniendo productos e imágenes...")
    
    # 1. Obtener productos activos
    products_result = supabase.table("products").select(
        "id, sku, name_es, name_en, description_es, category_id, brand_id"
    ).eq("is_active", True).execute()
    
    products = products_result.data or []
    product_ids = [p["id"] for p in products]
    products_map = {p["id"]: p for p in products}
    
    print(f"📦 {len(products)} productos activos encontrados")
    
    # 2. Obtener imágenes de esos productos
    images_result = supabase.table("product_images").select(
        "id, product_id, url, is_primary, storage_path"
    ).in_("product_id", product_ids).order("is_primary", desc=True).execute()
    
    images = images_result.data or []
    print(f"🖼️  {len(images)} imágenes encontradas")
    
    # 3. Verificar cuáles ya tienen embeddings
    existing_result = supabase.table("product_image_embeddings").select(
        "product_image_id"
    ).execute()
    
    existing_ids = {e["product_image_id"] for e in (existing_result.data or [])}
    pending_images = [img for img in images if img["id"] not in existing_ids]
    
    print(f"⏳ {len(pending_images)} imágenes pendientes de procesar")
    
    if not pending_images:
        print("✅ Todas las imágenes ya tienen embeddings")
        return
    
    # 4. Procesar imágenes pendientes
    batch_size = 10
    total_inserted = 0
    
    for i in tqdm(range(0, len(pending_images), batch_size), desc="Procesando lotes"):
        batch = pending_images[i:i + batch_size]
        embeddings_to_insert = []
        
        for img in batch:
            product = products_map.get(img["product_id"])
            if not product:
                continue
            
            # Descargar imagen
            image_bytes = await download_image(img["url"])
            if not image_bytes:
                continue
            
            try:
                # Generar embedding multimodal (imagen + texto del producto)
                embedding = embedding_service.generate_multimodal_embedding(
                    image_input=image_bytes,
                    product_name=product.get("name_es", ""),
                    product_description=product.get("description_es", "")
                )
                
                embedding_list = embedding_service.embedding_to_list(embedding)
                
                embeddings_to_insert.append({
                    "product_id": img["product_id"],
                    "product_image_id": img["id"],
                    "image_url": img["url"],
                    "embedding": embedding_list,
                    "model_version": settings.clip_model
                })
                
            except Exception as e:
                print(f"\n❌ Error generando embedding para {img['url']}: {e}")
                continue
        
        # Insertar batch en Supabase
        if embeddings_to_insert:
            try:
                supabase.table("product_image_embeddings").insert(
                    embeddings_to_insert
                ).execute()
                total_inserted += len(embeddings_to_insert)
                print(f"\n💾 Insertados {len(embeddings_to_insert)} embeddings")
            except Exception as e:
                print(f"\n❌ Error insertando batch: {e}")
        
        # Pequeña pausa entre lotes
        await asyncio.sleep(0.5)
    
    # 5. Reporte final
    stats_result = supabase.rpc("get_embedding_stats").execute()
    stats = stats_result.data[0] if stats_result.data else {}
    
    print("\n" + "=" * 50)
    print("📊 ESTADÍSTICAS FINALES")
    print("=" * 50)
    print(f"   Productos con embeddings: {stats.get('total_embeddings', 0)}")
    print(f"   Total productos activos:  {stats.get('total_products', 0)}")
    print(f"   Cobertura:                {stats.get('coverage_percent', 0)}%")
    print(f"   Nuevos embeddings:        {total_inserted}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(process_product_images())