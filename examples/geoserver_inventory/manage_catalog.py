#!/usr/bin/env python3
"""
Script para añadir nuevos geoservers al catálogo.

Este script facilita la adición de nuevos geoservers al catálogo
de manera interactiva o desde línea de comandos.
"""
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any

# Añadir rutas al path
script_dir = os.path.dirname(__file__)
project_root = os.path.join(script_dir, '..', '..')
sys.path.append(project_root)

from plugins.geoserver_plugin.plugin_interface import geoserver_plugin


def add_geoserver_interactive(catalog_file: str):
    """Añade un geoserver de forma interactiva."""
    print("🌍 Añadir nuevo GeoServer al catálogo")
    print("=" * 40)
    
    # Recopilar información
    name = input("📝 Nombre del servidor: ")
    url = input("🔗 URL base: ")
    description = input("📄 Descripción: ")
    
    print("\n🏷️ Categorías disponibles:")
    print("  1. demo - Servidores de demostración")
    print("  2. government - Servidores gubernamentales")
    print("  3. academic - Servidores académicos")
    print("  4. commercial - Servidores comerciales")
    print("  5. international - Organizaciones internacionales")
    print("  6. other - Otros")
    
    category_map = {
        "1": "demo", "2": "government", "3": "academic",
        "4": "commercial", "5": "international", "6": "other"
    }
    
    cat_choice = input("🏷️ Selecciona categoría (1-6): ")
    category = category_map.get(cat_choice, "other")
    
    country = input("🌍 País: ")
    organization = input("🏢 Organización: ")
    
    print("\n🔧 Tipos de servidor:")
    print("  1. geoserver - GeoServer")
    print("  2. arcgis - ArcGIS Server")
    print("  3. mapserver - MapServer")
    print("  4. qgis - QGIS Server")
    
    type_map = {
        "1": "geoserver", "2": "arcgis", "3": "mapserver", "4": "qgis"
    }
    
    type_choice = input("🔧 Selecciona tipo (1-4): ")
    server_type = type_map.get(type_choice, "geoserver")
    
    # Probar conexión
    print(f"\n🔍 Probando conexión a {url}...")
    test_result = geoserver_plugin.execute_method(
        "test_connection",
        base_url=url,
        server_type=server_type
    )
    
    if test_result.get("success", False):
        print("✅ Conexión exitosa!")
        status = "active"
        
        # Mostrar información de layers
        connection_info = test_result.get("result", {})
        layer_count = connection_info.get("available_layers", 0)
        print(f"📊 Layers disponibles: {layer_count}")
    else:
        print(f"❌ Error de conexión: {test_result.get('error', 'Unknown error')}")
        continue_anyway = input("¿Añadir de todas formas? (y/N): ")
        if continue_anyway.lower() != 'y':
            print("❌ Operación cancelada")
            return
        status = "unknown"
    
    # Crear entrada
    server_entry = {
        "id": name.lower().replace(" ", "_").replace("-", "_"),
        "name": name,
        "description": description,
        "url": url,
        "type": server_type,
        "category": category,
        "country": country,
        "organization": organization,
        "status": status,
        "public": True,
        "authentication": {
            "required": False,
            "type": "none"
        },
        "notes": f"Añadido interactivamente el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    }
    
    # Añadir al catálogo
    success = add_to_catalog(catalog_file, server_entry)
    
    if success:
        print(f"✅ GeoServer '{name}' añadido exitosamente al catálogo")
    else:
        print(f"❌ Error al añadir al catálogo")


def add_geoserver_from_args(catalog_file: str, name: str, url: str, **kwargs):
    """Añade un geoserver desde argumentos de línea de comandos."""
    server_entry = {
        "id": kwargs.get("id", name.lower().replace(" ", "_").replace("-", "_")),
        "name": name,
        "description": kwargs.get("description", f"Servidor {name}"),
        "url": url,
        "type": kwargs.get("type", "geoserver"),
        "category": kwargs.get("category", "other"),
        "country": kwargs.get("country", "Unknown"),
        "organization": kwargs.get("organization", "Unknown"),
        "status": kwargs.get("status", "unknown"),
        "public": kwargs.get("public", True),
        "authentication": {
            "required": kwargs.get("auth_required", False),
            "type": kwargs.get("auth_type", "none")
        },
        "notes": kwargs.get("notes", f"Añadido automáticamente el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    }
    
    # Probar conexión si se solicita
    if kwargs.get("test_connection", True):
        print(f"🔍 Probando conexión a {url}...")
        test_result = geoserver_plugin.execute_method(
            "test_connection",
            base_url=url,
            server_type=server_entry["type"]
        )
        
        if test_result.get("success", False):
            print("✅ Conexión exitosa!")
            server_entry["status"] = "active"
        else:
            print(f"❌ Error de conexión: {test_result.get('error', 'Unknown error')}")
            server_entry["status"] = "unreachable"
    
    # Añadir al catálogo
    success = add_to_catalog(catalog_file, server_entry)
    
    if success:
        print(f"✅ GeoServer '{name}' añadido exitosamente")
        return server_entry
    else:
        print(f"❌ Error al añadir al catálogo")
        return None


def add_to_catalog(catalog_file: str, server_entry: Dict[str, Any]) -> bool:
    """Añade una entrada al catálogo."""
    try:
        # Cargar catálogo existente
        if os.path.exists(catalog_file):
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
        else:
            catalog = {
                "@context": {
                    "dcat": "http://www.w3.org/ns/dcat#",
                    "dcterms": "http://purl.org/dc/terms/",
                    "foaf": "http://xmlns.com/foaf/0.1/",
                    "vcard": "http://www.w3.org/2006/vcard/ns#"
                },
                "@type": "dcat:Catalog",
                "dcterms:title": "Inventario de GeoServers Conocidos",
                "dcterms:description": "Catálogo de geoservers públicos y privados para inventario de layers",
                "dcterms:created": datetime.now().isoformat() + "Z",
                "geoservers": [],
                "custom:statistics": {
                    "total_geoservers": 0,
                    "by_category": {},
                    "by_country": {},
                    "by_type": {}
                }
            }
        
        # Verificar si ya existe
        geoservers = catalog.get("geoservers", [])
        for existing in geoservers:
            if existing.get("url") == server_entry["url"]:
                print(f"⚠️ Ya existe un servidor con URL {server_entry['url']}")
                overwrite = input("¿Sobrescribir? (y/N): ")
                if overwrite.lower() == 'y':
                    geoservers.remove(existing)
                    break
                else:
                    return False
        
        # Añadir nueva entrada
        geoservers.append(server_entry)
        catalog["geoservers"] = geoservers
        
        # Actualizar estadísticas
        catalog["dcterms:modified"] = datetime.now().isoformat() + "Z"
        stats = catalog.setdefault("custom:statistics", {})
        stats["total_geoservers"] = len(geoservers)
        stats["last_updated"] = datetime.now().isoformat() + "Z"
        
        # Actualizar conteos por categoría, país y tipo
        categories = {}
        countries = {}
        types = {}
        
        for server in geoservers:
            cat = server.get("category", "other")
            categories[cat] = categories.get(cat, 0) + 1
            
            country = server.get("country", "Unknown")
            countries[country] = countries.get(country, 0) + 1
            
            srv_type = server.get("type", "unknown")
            types[srv_type] = types.get(srv_type, 0) + 1
        
        stats["by_category"] = categories
        stats["by_country"] = countries
        stats["by_type"] = types
        
        # Guardar catálogo
        with open(catalog_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"❌ Error al guardar catálogo: {e}")
        return False


def list_catalog(catalog_file: str):
    """Lista los geoservers en el catálogo."""
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
        
        geoservers = catalog.get("geoservers", [])
        stats = catalog.get("custom:statistics", {})
        
        print(f"📊 Catálogo de GeoServers")
        print("=" * 40)
        print(f"📈 Total: {len(geoservers)} servidores")
        
        if stats.get("by_category"):
            print(f"\n🏷️ Por categoría:")
            for cat, count in sorted(stats["by_category"].items()):
                print(f"   • {cat}: {count}")
        
        if stats.get("by_country"):
            print(f"\n🌍 Por país:")
            for country, count in sorted(stats["by_country"].items()):
                print(f"   • {country}: {count}")
        
        print(f"\n📋 Servidores registrados:")
        for i, server in enumerate(geoservers, 1):
            status_icon = "✅" if server.get("status") == "active" else "❓" if server.get("status") == "unknown" else "❌"
            print(f"{i:2d}. {status_icon} {server['name']}")
            print(f"    🔗 {server['url']}")
            print(f"    🏷️ {server.get('category', 'unknown')} | 🌍 {server.get('country', 'unknown')}")
            print()
        
    except Exception as e:
        print(f"❌ Error al leer catálogo: {e}")


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Gestiona catálogo de geoservers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('catalog', help='Archivo JSON del catálogo')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando: add (interactivo)
    add_parser = subparsers.add_parser('add', help='Añadir geoserver interactivamente')
    
    # Comando: add-direct (desde argumentos)
    direct_parser = subparsers.add_parser('add-direct', help='Añadir geoserver desde argumentos')
    direct_parser.add_argument('name', help='Nombre del servidor')
    direct_parser.add_argument('url', help='URL del servidor')
    direct_parser.add_argument('--description', help='Descripción')
    direct_parser.add_argument('--type', choices=['geoserver', 'arcgis', 'mapserver', 'qgis'], 
                              default='geoserver', help='Tipo de servidor')
    direct_parser.add_argument('--category', choices=['demo', 'government', 'academic', 'commercial', 'international', 'other'],
                              default='other', help='Categoría')
    direct_parser.add_argument('--country', help='País')
    direct_parser.add_argument('--organization', help='Organización')
    direct_parser.add_argument('--no-test', action='store_true', help='No probar conexión')
    
    # Comando: list
    list_parser = subparsers.add_parser('list', help='Listar geoservers en catálogo')
    
    args = parser.parse_args()
    
    if args.command == 'add':
        add_geoserver_interactive(args.catalog)
    elif args.command == 'add-direct':
        add_geoserver_from_args(
            args.catalog, args.name, args.url,
            description=args.description,
            type=args.type,
            category=args.category,
            country=args.country or "Unknown",
            organization=args.organization or "Unknown",
            test_connection=not args.no_test
        )
    elif args.command == 'list':
        list_catalog(args.catalog)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
