#!/usr/bin/env python3
"""
Ejemplos de uso del plugin generalizado de Wikidata.

Este script demuestra cómo:
1. Ejecutar queries SPARQL personalizadas
2. Usar queries predefinidas comunes  
3. Guardar datos como assets con diccionarios
4. Exponer los datos a través del sistema
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from plugins.wikidata_plugin.wikidata_general import (
    WikidataQueryExecutor, 
    fetch_wikidata_query,
    fetch_common_query,
    COMMON_QUERIES
)
import json
from pathlib import Path


def example_custom_query():
    """Ejemplo de query personalizada: bibliotecas en Bolivia."""
    print("=== Ejemplo 1: Query personalizada - Bibliotecas en Bolivia ===")
    
    custom_query = """
    SELECT ?item ?itemLabel ?coord ?typeLabel WHERE {
      ?item wdt:P31/wdt:P279* wd:Q7075 .  # bibliotecas
      ?item wdt:P17 wd:Q750 .  # en Bolivia
      OPTIONAL { ?item wdt:P625 ?coord }
      OPTIONAL { ?item wdt:P31 ?type }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
    }
    """
    
    result = fetch_wikidata_query(
        query=custom_query,
        title="Bibliotecas de Bolivia",
        description="Bibliotecas públicas y académicas en Bolivia obtenidas de Wikidata",
        output_format="geojson",
        limit=100
    )
    
    print(f"Asset creado: {result['asset']['id']}")
    print(f"Datos guardados en: {result['data_path']}")
    print(f"Diccionario guardado en: {result['dictionary_path']}")
    print(f"Total de bibliotecas encontradas: {result['asset']['results_count']}")
    
    # Mostrar una muestra del diccionario de datos
    print("\n--- Muestra del diccionario de datos ---")
    dict_data = result['data_dictionary']
    for var_name, var_info in list(dict_data['variables'].items())[:3]:
        print(f"Variable: {var_name}")
        print(f"  Tipos de datos: {var_info['data_types']}")
        print(f"  Es URI: {var_info['is_uri']}")
        print(f"  Valores de muestra: {var_info['sample_values'][:2]}")
        print()
    
    return result


def example_predefined_query():
    """Ejemplo usando una query predefinida."""
    print("\n=== Ejemplo 2: Query predefinida - Universidades ===")
    
    result = fetch_common_query("universities_bolivia", limit=50)
    
    print(f"Asset creado: {result['asset']['id']}")
    print(f"Total de universidades: {result['asset']['results_count']}")
    
    # Mostrar algunas universidades
    print("\n--- Primeras 3 universidades ---")
    features = result['data']['features'][:3]
    for i, feature in enumerate(features, 1):
        props = feature['properties']
        coords = feature['geometry']['coordinates'] if feature['geometry'] else None
        print(f"{i}. {props.get('itemLabel', 'N/A')}")
        if coords:
            print(f"   Coordenadas: {coords}")
        if 'founded' in props:
            print(f"   Fundada: {props['founded']}")
        print()
    
    return result


def example_json_output():
    """Ejemplo con salida en formato JSON estructurado."""
    print("\n=== Ejemplo 3: Salida JSON - Hospitales ===")
    
    hospitals_query = """
    SELECT ?item ?itemLabel ?coord ?address WHERE {
      ?item wdt:P31/wdt:P279* wd:Q16917 .  # hospitales
      ?item wdt:P17 wd:Q750 .  # en Bolivia
      OPTIONAL { ?item wdt:P625 ?coord }
      OPTIONAL { ?item wdt:P6375 ?address }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
    }
    """
    
    result = fetch_wikidata_query(
        query=hospitals_query,
        title="Hospitales de Bolivia",
        description="Red hospitalaria de Bolivia con coordenadas y direcciones",
        output_format="json",
        limit=30
    )
    
    print(f"Asset creado: {result['asset']['id']}")
    print(f"Total de hospitales: {len(result['data']['data'])}")
    
    # Mostrar primer hospital
    if result['data']['data']:
        hospital = result['data']['data'][0]
        print(f"\nPrimer hospital: {hospital.get('itemLabel', 'N/A')}")
        print(f"URI: {hospital.get('item_uri', 'N/A')}")
        print(f"ID Wikidata: {hospital.get('item_id', 'N/A')}")
    
    return result


def example_executor_advanced():
    """Ejemplo usando directamente el ejecutor para funcionalidad avanzada."""
    print("\n=== Ejemplo 4: Ejecutor avanzado - Análisis de datos ===")
    
    executor = WikidataQueryExecutor()
    
    # Query compleja para sitios arqueológicos
    archaeological_query = """
    SELECT ?item ?itemLabel ?coord ?cultureLabel ?periodLabel WHERE {
      ?item wdt:P31/wdt:P279* wd:Q839954 .  # sitio arqueológico
      ?item wdt:P17 wd:Q750 .  # en Bolivia
      OPTIONAL { ?item wdt:P625 ?coord }
      OPTIONAL { ?item wdt:P2596 ?culture }
      OPTIONAL { ?item wdt:P2348 ?period }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
    }
    """
    
    result = executor.execute_sparql_query(
        query=archaeological_query,
        title="Sitios Arqueológicos de Bolivia",
        description="Patrimonio arqueológico boliviano con información cultural y temporal",
        limit=100,
        output_format="geojson"
    )
    
    print(f"Asset creado: {result['asset']['id']}")
    
    # Análisis del diccionario
    dict_data = result['data_dictionary']
    print(f"\nAnálisis de variables:")
    print(f"Total de variables SPARQL: {len(dict_data['variables'])}")
    print(f"Total de resultados: {dict_data['total_results']}")
    
    # Variables con coordenadas
    coord_vars = [v for v, info in dict_data['variables'].items() if info['is_coordinate']]
    print(f"Variables con coordenadas: {coord_vars}")
    
    # Variables que son URIs
    uri_vars = [v for v, info in dict_data['variables'].items() if info['is_uri']]
    print(f"Variables con URIs: {uri_vars}")
    
    return result


def list_available_assets():
    """Lista todos los assets creados."""
    print("\n=== Assets disponibles en el catálogo ===")
    
    from src.adapters.persistence.local_persistence import LocalPersistence
    persistence = LocalPersistence()
    catalog = persistence.load_catalog()
    
    assets = catalog.get("assets", [])
    wikidata_assets = [a for a in assets if a.get("source") == "wikidata"]
    
    print(f"Total de assets de Wikidata: {len(wikidata_assets)}")
    
    for asset in wikidata_assets[-5:]:  # Últimos 5
        print(f"\nID: {asset['id']}")
        print(f"Título: {asset['title']}")
        print(f"Resultados: {asset.get('results_count', 'N/A')}")
        print(f"Creado: {asset.get('created_at', 'N/A')}")
        if 'data_uri' in asset:
            print(f"Datos: {asset['data_uri']}")
        if 'data_dictionary_uri' in asset:
            print(f"Diccionario: {asset['data_dictionary_uri']}")


def main():
    """Ejecuta todos los ejemplos."""
    print("🚀 Plugin Generalizado de Wikidata - Ejemplos")
    print("=" * 50)
    
    # Mostrar queries disponibles
    print("Queries predefinidas disponibles:")
    for name, info in COMMON_QUERIES.items():
        print(f"  - {name}: {info['title']}")
    print()
    
    try:
        # Ejecutar ejemplos
        example_custom_query()
        example_predefined_query() 
        example_json_output()
        example_executor_advanced()
        
        # Listar assets creados
        list_available_assets()
        
        print("\n✅ Todos los ejemplos ejecutados correctamente!")
        print("\nLos datos están guardados como assets y pueden ser:")
        print("1. Consultados a través del CLI: python -m src.adapters.cli.dm_cli asset list")
        print("2. Expuestos vía API REST")
        print("3. Utilizados por otros plugins")
        
    except Exception as e:
        print(f"\n❌ Error ejecutando ejemplos: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
