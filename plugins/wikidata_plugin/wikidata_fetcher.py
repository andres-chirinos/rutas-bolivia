"""Plugin: fetch museums in Bolivia from Wikidata and write as GeoJSON.

DEPRECATED: Este archivo mantiene compatibilidad con la versión anterior.
Para nueva funcionalidad, usar wikidata_general.py que incluye:
- Queries SPARQL personalizadas 
- Sistema de assets integrado
- Diccionarios de datos automáticos
"""
import json
import os
from typing import List
from datetime import datetime, timedelta
from pathlib import Path
from .wikidata_general import fetch_museums_bolivia_generalized, fetch_wikidata_query, WikidataQueryExecutor

# Mantener compatibilidad con la función original usando el sistema de assets
def fetch_museums_bolivia(output_geojson: str, limit: int = 500):
    """
    Función original para obtener museos de Bolivia.
    Ahora usa el sistema de assets con caché automático.
    Solo descarga desde Wikidata si no existe un asset reciente (< 1 día).
    """
    # Initialize asset system
    executor = WikidataQueryExecutor()
    
    # Check for existing asset in catalog
    catalog = executor.persistence.load_catalog()
    assets = catalog.get("assets", [])
    
    # Look for recent museums asset - find the most recent one
    museums_asset = None
    most_recent_time = None
    most_recent_asset = None
    
    for asset in assets:
        if (asset.get("title") == "Museos de Bolivia" and 
            "Bolivia" in asset.get("description", "")):
            
            # Check if asset is less than 1 day old
            created_at = asset.get("created_at")
            if created_at:
                try:
                    # Parse datetime - handle both with and without Z suffix
                    if created_at.endswith('Z'):
                        asset_time = datetime.fromisoformat(created_at[:-1])
                    else:
                        asset_time = datetime.fromisoformat(created_at)
                    
                    # Track the most recent asset
                    if most_recent_time is None or asset_time > most_recent_time:
                        most_recent_time = asset_time
                        most_recent_asset = asset
                
                except (ValueError, AttributeError):
                    continue
    
    # Check if the most recent asset is less than 1 day old
    if most_recent_asset and most_recent_time:
        if datetime.now() - most_recent_time < timedelta(days=1):
            museums_asset = most_recent_asset
            print(f"Using cached asset from {most_recent_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"Most recent asset is from {most_recent_time.strftime('%Y-%m-%d %H:%M:%S')}, too old")
    
    # Use existing asset or create new one
    if museums_asset and museums_asset.get("data_uri"):
        # Copy from asset data to output file
        data_path = museums_asset["data_uri"]
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                data = json.load(f)
            with open(output_geojson, 'w') as f:
                json.dump(data, f, indent=2)
            return output_geojson
    
    # No recent asset found, fetch new data
    print("No recent asset found, fetching from Wikidata...")
    
    # Use the generalized system which creates assets automatically
    result = fetch_museums_bolivia_generalized(output_geojson, limit)
    
    return result


# Nuevas funciones expuestas
def fetch_custom_wikidata_query(query: str, title: str, description: str = "", 
                               output_format: str = "geojson", limit: int = 500):
    """
    Ejecuta una query SPARQL personalizada en Wikidata y crea un asset.
    
    Args:
        query: Query SPARQL a ejecutar
        title: Título descriptivo para el asset
        description: Descripción del dataset
        output_format: Formato de salida ('geojson', 'json', 'csv')
        limit: Límite de resultados
        
    Returns:
        Dict con información del asset creado
    """
    return fetch_wikidata_query(
        query=query,
        title=title, 
        description=description,
        output_format=output_format,
        limit=limit
    )

