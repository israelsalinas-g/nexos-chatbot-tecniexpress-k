#!/usr/bin/env python3
"""
Verifica que todos los productos activos tengan embeddings.
Útil para detectar productos nuevos que se agregaron sin embeddings.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import get_supabase_client
from app.config import get_settings


def check_missing_embeddings():
    supabase = get_supabase_client()
    
    # Productos activos SIN embeddings
    result = supabase.rpc("get_embedding_stats").execute()
    stats = result.data[0] if result.data else {}
    
    total_products = stats.get("total_products", 0)
    with_embeddings = stats.get("total_embeddings", 0)
    missing = total_products - with_embeddings
    
    print("=" * 60)
    print("📊 ESTADO DE EMBEDDINGS")
    print("=" * 60)
    print(f"Total productos activos:    {total_products}")
    print(f"Productos con embeddings:   {with_embeddings}")
    print(f"Productos SIN embeddings:   {missing}")
    print(f"Cobertura:                  {stats.get('coverage_percent', 0)}%")
    print("=" * 60)
    
    if missing > 0:
        print(f"\n⚠️  Hay {missing} productos sin embeddings!")
        print("Ejecuta: python scripts/generate_embeddings.py")
        return False
    else:
        print("\n✅ Todos los productos tienen embeddings actualizados")
        return True


def list_recent_products_without_embeddings(days: int = 7):
    """Lista productos creados recientemente que no tienen embeddings."""
    supabase = get_supabase_client()
    
    # Productos creados en los últimos N días sin embeddings
    result = supabase.table("products").select(
        "id, sku, name_es, created_at"
    ).eq("is_active", True).gte(
        "created_at", f"now() - interval '{days} days'"
    ).execute()
    
    recent_products = result.data or []
    
    if not recent_products:
        print(f"\n✅ No hay productos nuevos en los últimos {days} días")
        return []
    
    # Verificar cuáles no tienen embeddings
    product_ids = [p["id"] for p in recent_products]
    
    embeddings_result = supabase.table("product_image_embeddings").select(
        "product_id"
    ).in_("product_id", product_ids).execute()
    
    embedded_ids = {e["product_id"] for e in (embeddings_result.data or [])}
    
    missing = [p for p in recent_products if p["id"] not in embedded_ids]
    
    if missing:
        print(f"\n⚠️  Productos nuevos sin embeddings ({len(missing)}):")
        for p in missing:
            print(f"   - {p['sku']}: {p['name_es']}")
    
    return missing


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Monitorear embeddings")
    parser.add_argument("--check", action="store_true", help="Verificar cobertura general")
    parser.add_argument("--recent", type=int, metavar="DAYS", help="Verificar productos recientes")
    
    args = parser.parse_args()
    
    if args.check or not args.recent:
        ok = check_missing_embeddings()
        if not ok:
            sys.exit(1)
    
    if args.recent:
        missing = list_recent_products_without_embeddings(args.recent)
        if missing:
            print(f"\nEjecuta: python scripts/generate_embeddings.py")