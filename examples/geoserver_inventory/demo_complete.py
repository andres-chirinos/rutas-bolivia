#!/usr/bin/env python3
"""
Ejemplo práctico de uso del sistema de inventario de geoservers.

Este script demuestra cómo:
1. Añadir un nuevo geoserver al catálogo
2. Generar inventario filtrado
3. Analizar los resultados
"""
import sys
import os

# Añadir rutas al path
script_dir = os.path.dirname(__file__)
project_root = os.path.join(script_dir, '..', '..')
sys.path.append(project_root)

from examples.geoserver_inventory.manage_catalog import add_geoserver_from_args
from examples.geoserver_inventory.generate_layers_inventory import GeoServerInventory


def demo_complete_workflow():
    """Demuestra el flujo completo de trabajo."""
    
    print("🌍 Demo Completa: Sistema de Inventario de GeoServers")
    print("=" * 60)
    
    catalog_file = os.path.join(script_dir, "geoservers_catalog.json")
    
    # 1. Añadir un nuevo geoserver (ejemplo ficticio)
    print("\n📋 1. Añadiendo nuevo geoserver de ejemplo...")
    
    new_server = add_geoserver_from_args(
        catalog_file=catalog_file,
        name="Mi Servidor Local",
        url="http://localhost:8080/geoserver",
        description="Servidor GeoServer local para desarrollo",
        type="geoserver",
        category="demo",
        country="Local",
        organization="Mi Organización",
        test_connection=False,  # No probar conexión para servidor ficticio
        notes="Servidor añadido como ejemplo en el demo"
    )
    
    if new_server:
        print(f"   ✅ Servidor '{new_server['name']}' añadido exitosamente")
    else:
        print("   ❌ Error al añadir servidor")
    
    # 2. Generar inventario de servidores demo
    print("\n📊 2. Generando inventario de servidores demo...")
    
    inventory = GeoServerInventory(catalog_file)
    
    # Generar inventario solo de demos, máximo 3 servidores
    csv_path = inventory.generate_inventory(
        output_file=os.path.join(script_dir, "demo_inventory_example.csv"),
        categories=["demo"],
        max_servers=3,
        test_connection=True
    )
    
    # 3. Analizar resultados
    print("\n📈 3. Análisis de resultados...")
    
    if inventory.results:
        print(f"   ✅ Se encontraron {len(inventory.results)} layers")
        
        # Agrupar por servidor
        servers = {}
        for result in inventory.results:
            server_name = result['server_name']
            if server_name not in servers:
                servers[server_name] = []
            servers[server_name].append(result)
        
        print(f"   🔧 Servidores procesados: {len(servers)}")
        
        for server_name, layers in servers.items():
            print(f"     • {server_name}: {len(layers)} layers")
            
            # Mostrar algunos layers de ejemplo
            for layer in layers[:3]:
                layer_name = layer['layer_name']
                layer_title = layer['layer_title']
                print(f"       - {layer_name}: {layer_title}")
            
            if len(layers) > 3:
                print(f"       ... y {len(layers) - 3} más")
    
    # 4. Mostrar casos de uso prácticos
    print("\n💡 4. Casos de uso prácticos:")
    
    examples = [
        {
            "nombre": "Inventario gubernamental",
            "comando": "python generate_layers_inventory.py geoservers_catalog.json -c government",
            "descripcion": "Solo datos oficiales de gobiernos"
        },
        {
            "nombre": "Datos de América Latina",
            "comando": "python generate_layers_inventory.py geoservers_catalog.json --countries 'Argentina' 'España'",
            "descripcion": "Filtrar por países específicos"
        },
        {
            "nombre": "Test rápido",
            "comando": "python generate_layers_inventory.py geoservers_catalog.json --max-servers 2 --no-test",
            "descripcion": "Inventario rápido sin test de conexión"
        },
        {
            "nombre": "Solo MapServer",
            "comando": "python generate_layers_inventory.py geoservers_catalog.json --server-types mapserver",
            "descripcion": "Filtrar por tipo de servidor"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n   {i}. {example['nombre']}:")
        print(f"      📝 {example['descripcion']}")
        print(f"      💻 {example['comando']}")
    
    # 5. Consejos y mejores prácticas
    print("\n🎯 5. Consejos y mejores prácticas:")
    
    tips = [
        "Usa `--max-servers` para pruebas rápidas",
        "Combina filtros: `-c government --countries 'España'`",
        "El archivo CSV se puede abrir en Excel/LibreOffice",
        "URLs WMS/WFS están listas para usar en QGIS",
        "Ejecuta inventarios periódicamente para monitorear cambios",
        "Usa `--no-test` si tienes problemas de conectividad"
    ]
    
    for i, tip in enumerate(tips, 1):
        print(f"   {i}. ✅ {tip}")
    
    # 6. Archivos generados
    print(f"\n📁 6. Archivos generados en este demo:")
    
    files_to_check = [
        "demo_inventory_example.csv",
        "test_inventory.csv"
    ]
    
    for filename in files_to_check:
        filepath = os.path.join(script_dir, filename)
        if os.path.exists(filepath):
            size_kb = os.path.getsize(filepath) / 1024
            print(f"   📄 {filename} ({size_kb:.1f} KB)")
        else:
            print(f"   📄 {filename} (no generado)")
    
    print(f"\n✨ Demo completada!")
    print(f"📚 Ver README.md para documentación completa")
    print(f"🔧 Explorar scripts en examples/geoserver_inventory/")


if __name__ == "__main__":
    demo_complete_workflow()
