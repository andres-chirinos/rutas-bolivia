#!/usr/bin/env python3
"""
Demostración del Knowledge Graph Compatible con Wikidata
========================================================

Este script demuestra el nuevo sistema KG con formato Wikidata:

1. 📁 Estructura organizada (items/, properties/, schemas/)
2. 🔗 Formato JSON compatible con Wikidata
3. 🌐 KG soberanos e interoperables
4. 📥 Importación de entidades externas
5. 🔄 Conversión automática desde formato legado
6. 🔍 Búsqueda multilingüe en formato estándar

Esquema de interoperabilidad:
- KG local soberano con IDs propios (Q200001+)
- Referencias a Wikidata real (external_refs)
- Importación automática con preservación de metadatos
- Búsqueda unificada en ambos formatos

Autor: GitHub Copilot
Fecha: 6 de octubre de 2025
"""

import requests
import json
import sys
import os

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
            # Mostrar respuesta truncada si es muy larga
            result_str = json.dumps(result, indent=2, ensure_ascii=False)
            if len(result_str) > 800:
                print(result_str[:800] + "\n... (truncado)")
            else:
                print(result_str)
            return result
        else:
            print(f"❌ ERROR: {response.text}")
            return None
            
    except Exception as e:
        print(f"💥 EXCEPCIÓN: {e}")
        return None

def show_directory_structure():
    """Mostrar la estructura de directorios del KG Wikidata"""
    print(f"\n{'='*60}")
    print("📁 ESTRUCTURA DEL KNOWLEDGE GRAPH WIKIDATA")
    print(f"{'='*60}")
    
    base_path = "/mnt/Archivos/Documents/GitHub/datamesh-client/data_store/wikidata_format"
    
    if os.path.exists(base_path):
        for root, dirs, files in os.walk(base_path):
            level = root.replace(base_path, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files[:5]:  # Mostrar solo los primeros 5 archivos
                print(f"{subindent}{file}")
            if len(files) > 5:
                print(f"{subindent}... y {len(files) - 5} más")
    else:
        print("❌ Directorio no encontrado")

def main():
    print("🧠 DEMOSTRACIÓN DEL KNOWLEDGE GRAPH COMPATIBLE CON WIKIDATA")
    print("=" * 60)
    print("Sistema de KG soberano e interoperable con formato estándar Wikidata")
    
    # 1. Mostrar estructura de archivos
    show_directory_structure()
    
    # 2. Verificar servidor
    health = test_endpoint("GET", "/health", description="Verificar servidor")
    if not health:
        print("❌ Servidor no disponible")
        sys.exit(1)
    
    # 3. Probar entidades en formato Wikidata
    test_endpoint("GET", "/wikidata/entities/Q1", 
                  description="Obtener entidad Bolivia (Q1) en formato Wikidata")
    
    test_endpoint("GET", "/wikidata/entities/Q100001",
                  description="Obtener Museo Nacional de Arte en formato Wikidata")
    
    # 4. Probar propiedades
    test_endpoint("GET", "/wikidata/properties/P31",
                  description="Obtener propiedad 'instancia de' (P31)")
    
    test_endpoint("GET", "/wikidata/properties/P625",
                  description="Obtener propiedad 'coordenadas' (P625)")
    
    # 5. Búsqueda multilingüe
    test_endpoint("GET", "/wikidata/search?query=museo&lang=es&limit=3",
                  description="Buscar 'museo' en español")
    
    test_endpoint("GET", "/wikidata/search?query=Bolivia&lang=en&limit=2",
                  description="Buscar 'Bolivia' en inglés")
    
    # 6. Crear nueva entidad en formato Wikidata
    nueva_entidad = {
        "id": "Q400001",
        "type": "item",
        "labels": {
            "es": {"value": "Cochabamba", "language": "es"},
            "en": {"value": "Cochabamba", "language": "en"}
        },
        "descriptions": {
            "es": {"value": "Ciudad de Bolivia conocida como la ciudad del eterno clima primaveral", "language": "es"},
            "en": {"value": "Bolivian city known as the city of eternal spring weather", "language": "en"}
        },
        "aliases": {
            "es": [
                {"value": "Cercado", "language": "es"},
                {"value": "Ciudad Jardín", "language": "es"}
            ]
        },
        "claims": {
            "P31": [{
                "mainsnak": {
                    "snaktype": "value",
                    "property": "P31",
                    "datavalue": {
                        "value": {"id": "Q515"},
                        "type": "wikibase-entityid"
                    }
                },
                "type": "statement",
                "rank": "normal"
            }],
            "P17": [{
                "mainsnak": {
                    "snaktype": "value",
                    "property": "P17",
                    "datavalue": {
                        "value": {"id": "Q1"},
                        "type": "wikibase-entityid"
                    }
                },
                "type": "statement",
                "rank": "normal"
            }],
            "P625": [{
                "mainsnak": {
                    "snaktype": "value",
                    "property": "P625",
                    "datavalue": {
                        "value": {
                            "latitude": -17.3935,
                            "longitude": -66.1570,
                            "precision": 0.0001
                        },
                        "type": "globecoordinate"
                    }
                },
                "type": "statement",
                "rank": "normal"
            }],
            "P1082": [{
                "mainsnak": {
                    "snaktype": "value",
                    "property": "P1082",
                    "datavalue": {
                        "value": {
                            "amount": "+630587",
                            "unit": "1"
                        },
                        "type": "quantity"
                    }
                },
                "type": "statement",
                "rank": "normal"
            }]
        },
        "external_refs": {
            "wikidata": "Q28279",
            "confidence": 0.99,
            "relation": "same_as"
        }
    }
    
    test_endpoint("POST", "/wikidata/entities", nueva_entidad,
                  description="Crear entidad Cochabamba con formato Wikidata completo")
    
    # 7. Obtener claims específicos
    test_endpoint("GET", "/wikidata/entities/Q400001/claims/P31",
                  description="Obtener claims P31 (instancia de) de Cochabamba")
    
    # 8. Probar importación desde Wikidata (si está disponible)
    test_endpoint("POST", "/wikidata/import/wikidata?external_id=Q717&create_local_id=true",
                  description="Importar entidad desde Wikidata real (Venezuela)")
    
    # 9. Búsqueda final para mostrar todas las entidades
    test_endpoint("GET", "/wikidata/search?query=&lang=es&limit=10",
                  description="Listar todas las entidades disponibles")
    
    print(f"\n{'='*60}")
    print("🎉 DEMOSTRACIÓN COMPLETADA")
    print("💡 Características implementadas:")
    print("   📁 Estructura organizada (items/, properties/, schemas/)")
    print("   🔗 Formato JSON 100% compatible con Wikidata")
    print("   🌐 KG soberano con interoperabilidad externa")
    print("   📥 Importación automática desde Wikidata real")
    print("   🔄 Conversión desde formato legado")
    print("   🔍 Búsqueda multilingüe avanzada")
    print("   ⚡ Claims, propiedades y metadatos completos")
    print("   🏛️ Esquemas de validación (ShEx)")
    print(f"{'='*60}")
    print("🎯 El KG es ahora:")
    print("   • Soberano: IDs propios (Q200001+, Q300001+, Q400001+)")
    print("   • Interoperable: Referencias a Wikidata/DBpedia")
    print("   • Estándar: Formato JSON compatible con Wikidata")
    print("   • Escalable: Estructura de archivos organizada")

if __name__ == "__main__":
    main()
