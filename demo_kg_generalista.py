#!/usr/bin/env python3
"""
Demostración del Knowledge Graph Generalista
============================================

Este script demuestra las nuevas funcionalidades del KG como un "Wikidata propio":

1. 🌐 Búsqueda en KG externos (Wikidata, DBpedia)
2. 📊 Análisis automático de datasets y columnas  
3. 🔗 Vinculación con entidades externas
4. 🧠 Creación de entidades enriquecidas
5. 📝 Descripción contextual automática

Autor: GitHub Copilot
Fecha: 6 de octubre de 2025
"""

import requests
import json
import sys

API_URL = "http://127.0.0.1:8000"

def test_endpoint(method, endpoint, data=None, description=""):
    """Probar un endpoint y mostrar resultado"""
    print(f"\n{'='*60}")
    print(f"🔧 PROBANDO: {description}")
    print(f"{'='*60}")
    
    url = f"{API_URL}{endpoint}"
    print(f"📡 {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data, headers={'Content-Type': 'application/json'})
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ ÉXITO")
            print(f"📄 Respuesta:")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "..." if len(str(result)) > 500 else json.dumps(result, indent=2, ensure_ascii=False))
            return result
        else:
            print(f"❌ ERROR: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 EXCEPCIÓN: {e}")
        return None

def main():
    print("🧠 DEMOSTRACIÓN DEL KNOWLEDGE GRAPH GENERALISTA")
    print("=" * 60)
    print("Un sistema como 'Wikidata propio' para gestión avanzada de conocimiento")
    
    # 1. Verificar que el servidor esté funcionando
    print("\n🔍 Verificando conectividad...")
    health = test_endpoint("GET", "/health", description="Verificar servidor")
    if not health:
        print("❌ Servidor no disponible. Asegúrate de que esté ejecutándose en puerto 8000")
        sys.exit(1)
    
    # 2. Buscar entidades en KG externo
    test_endpoint("GET", "/kg/entities/external?query=Bolivia&source=wikidata&limit=3", 
                  description="Buscar 'Bolivia' en Wikidata")
    
    test_endpoint("GET", "/kg/entities/external?query=Museo&source=dbpedia&limit=3", 
                  description="Buscar 'Museo' en DBpedia")
    
    # 3. Crear entidad enriquecida
    new_entity = {
        "title": "Universidad Mayor de San Andrés",
        "type": "Organization",
        "description": "Principal universidad pública de Bolivia, ubicada en La Paz",
        "aliases": ["UMSA", "Universidad de La Paz"],
        "properties": {
            "type": "Universidad",
            "sector": "Educación Superior",
            "location": "La Paz, Bolivia",
            "founded": "1830",
            "website": "https://www.umsa.bo"
        },
        "external_links": [{
            "external_id": "Q2495456",
            "source": "wikidata",
            "confidence": 0.95,
            "relation_type": "same_as"
        }],
        "tags": ["universidad", "educación", "bolivia", "la-paz"],
        "metadata": {
            "created_for_demo": True,
            "demo_timestamp": "2025-10-06"
        },
        "created_by": "demo_script"
    }
    
    entity_result = test_endpoint("POST", "/kg/entities/create", new_entity,
                                  description="Crear entidad universitaria enriquecida")
    
    # 4. Analizar estructura de datasets
    columns_analysis = {
        "columns": [
            "universidad_nombre",
            "rector_email", 
            "fecha_fundacion",
            "num_estudiantes",
            "latitude",
            "longitude",
            "presupuesto_anual",
            "website_url"
        ]
    }
    
    test_endpoint("POST", "/kg/describe/dataset", columns_analysis,
                  description="Analizar columnas de dataset universitario")
    
    # 5. Análisis de dataset real si existe
    real_dataset = {"dataset_path": "dummy_datasets/sample_input.csv"}
    test_endpoint("POST", "/kg/describe/dataset", real_dataset,
                  description="Analizar dataset real existente")
    
    # 6. Si se creó una entidad, vincular entidad externa
    if entity_result and "entity_id" in entity_result:
        entity_id = entity_result["entity_id"]
        
        external_link = {
            "external_id": "Q8717",  # ID de Wikidata para "Universidad"
            "source": "wikidata",
            "confidence": 0.8,
            "relation_type": "instance_of"
        }
        
        test_endpoint("POST", f"/kg/entities/{entity_id}/link", external_link,
                      description="Vincular entidad local con concepto de Wikidata")
    
    # 7. Búsqueda en KG local para ver las nuevas entidades
    test_endpoint("GET", "/kg/search?query=universidad&limit=5",
                  description="Buscar 'universidad' en KG local")
    
    print(f"\n{'='*60}")
    print("🎉 DEMOSTRACIÓN COMPLETADA")
    print("💡 Funcionalidades demostradas:")
    print("   • Búsqueda en KG externos (Wikidata/DBpedia)")
    print("   • Creación de entidades enriquecidas")
    print("   • Análisis automático de columnas")
    print("   • Vinculación con entidades externas")
    print("   • Descripción contextual automática")
    print("   • Sistema generalista como 'Wikidata propio'")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
