#!/usr/bin/env python3
"""
Ejemplo de uso del plugin GeoServer con el catálogo DCAT extendido.

Este script demuestra cómo:
1. Registrar un geoserver como servicio de datos
2. Registrar layers como datasets
3. Descargar distribuciones y registrarlas en DCAT
4. Registrar fuentes interesantes para seguimiento
5. Obtener resúmenes del catálogo
"""
import sys
import os
import json

# Añadir el directorio padre al path para importar el plugin
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from plugins.geoserver_plugin.plugin_interface import geoserver_plugin


def main():
    """Función principal del ejemplo."""
    print("🌍 Demo del Plugin GeoServer con Catálogo DCAT")
    print("=" * 60)
    
    # URL del geoserver público de prueba
    base_url = "https://ahocevar.com/geoserver"
    
    # 1. Registrar el geoserver como servicio de datos
    print("\n📋 1. Registrando geoserver como servicio de datos...")
    service_result = geoserver_plugin.execute_method(
        "register_service",
        base_url=base_url,
        server_type="geoserver",
        service_name="Demo GeoServer Ahocevar",
        description="Servidor GeoServer público de demostración con datos de ejemplo"
    )
    
    if service_result["success"]:
        print(f"   📋 Resultado completo: {service_result}")
        if "service_id" in service_result["result"]:
            service_id = service_result["result"]["service_id"]
            print(f"   ✅ Servicio registrado con ID: {service_id}")
        else:
            print(f"   ⚠️ Servicio procesado pero sin ID: {service_result['result']}")
            service_id = None
    else:
        print(f"   ❌ Error al registrar servicio: {service_result.get('error', 'Unknown error')}")
        service_id = None
    
    # 2. Listar layers disponibles
    print("\n📊 2. Listando layers disponibles...")
    layers_result = geoserver_plugin.execute_method(
        "list_layers",
        base_url=base_url,
        server_type="geoserver"
    )
    
    if layers_result["success"] and "layers" in layers_result["result"]:
        layers = layers_result["result"]["layers"]
        print(f"   📈 Encontrados {len(layers)} layers:")
        for i, layer in enumerate(layers[:5]):  # Mostrar solo los primeros 5
            print(f"     {i+1}. {layer.get('name', 'N/A')} - {layer.get('title', 'Sin título')}")
        if len(layers) > 5:
            print(f"     ... y {len(layers) - 5} más")
    else:
        print(f"   ❌ Error al listar layers: {layers_result.get('error', 'Unknown error')}")
        return
    
    # 3. Registrar algunos layers como datasets
    print("\n🗃️ 3. Registrando layers como datasets...")
    datasets_registered = []
    
    for layer in layers[:3]:  # Registrar los primeros 3 layers
        layer_name = layer.get("name", "")
        if layer_name:
            dataset_result = geoserver_plugin.execute_method(
                "register_layer_dataset",
                base_url=base_url,
                layer_name=layer_name,
                server_type="geoserver",
                service_id=service_id
            )
            
            if dataset_result["success"]:
                dataset_id = dataset_result["result"]["dataset_id"]
                datasets_registered.append((layer_name, dataset_id))
                print(f"   ✅ Dataset '{layer_name}' registrado con ID: {dataset_id}")
            else:
                print(f"   ❌ Error al registrar dataset '{layer_name}': {dataset_result.get('error', 'Unknown')}")
    
    # 4. Descargar un layer y registrar la distribución
    if datasets_registered:
        print("\n💾 4. Descargando layer y registrando distribución...")
        layer_name, dataset_id = datasets_registered[0]
        
        download_result = geoserver_plugin.execute_method(
            "download_layer",
            base_url=base_url,
            layer_name=layer_name,
            output_format="geojson",
            server_type="geoserver",
            maxFeatures=10,  # Limitar para la demo
            dataset_id=dataset_id
        )
        
        if download_result["success"]:
            file_path = download_result["result"]["file_path"]
            dcat_info = download_result["result"].get("dcat_info", {})
            print(f"   ✅ Layer descargado: {file_path}")
            if "distribution_id" in dcat_info:
                print(f"   📦 Distribución registrada con ID: {dcat_info['distribution_id']}")
            else:
                print(f"   📦 Usando sistema legacy para assets")
        else:
            print(f"   ❌ Error al descargar layer: {download_result.get('error', 'Unknown error')}")
    
    # 5. Registrar algunas fuentes interesantes
    print("\n🔍 5. Registrando fuentes de datos interesantes...")
    interesting_sources = [
        {
            "url": "https://maps.princeton.edu/geoserver",
            "name": "Princeton University GeoServer",
            "description": "Servidor GeoServer de la Universidad de Princeton con datos geográficos académicos",
            "category": "academic"
        },
        {
            "url": "https://geoservices.informatievlaanderen.be/raadpleegdiensten/omwrgbmrvl/wms",
            "name": "Flanders Government WMS",
            "description": "Servicio WMS del gobierno de Flanders con datos oficiales",
            "category": "government"
        },
        {
            "url": "https://demo.mapserver.org/cgi-bin/mapserv",
            "name": "MapServer Demo",
            "description": "Servidor MapServer de demostración oficial",
            "source_type": "mapserver",
            "category": "demo"
        }
    ]
    
    for source in interesting_sources:
        source_result = geoserver_plugin.execute_method(
            "register_source",
            **source,
            tags=["discovered", "demo", source.get("category", "general")]
        )
        
        if source_result["success"]:
            print(f"   ✅ Fuente '{source['name']}' registrada")
        else:
            print(f"   ❌ Error al registrar fuente '{source['name']}': {source_result.get('error', 'Unknown')}")
    
    # 6. Obtener resumen del catálogo
    print("\n📈 6. Resumen del catálogo DCAT...")
    summary_result = geoserver_plugin.execute_method("get_catalog_summary")
    
    if summary_result["success"]:
        summary = summary_result["result"]
        if "error" not in summary:
            stats = summary.get("statistics", {})
            print(f"   📊 Estadísticas del catálogo:")
            print(f"     • Servicios de datos: {stats.get('total_services', 0)}")
            print(f"     • Datasets: {stats.get('total_datasets', 0)}")
            print(f"     • Distribuciones: {stats.get('total_distributions', 0)}")
            print(f"     • Fuentes rastreadas: {stats.get('total_sources', 0)}")
            print(f"     • Última actualización: {stats.get('last_updated', 'N/A')}")
            
            # Información adicional
            services_info = summary.get("services", {})
            print(f"   🔧 Servicios activos: {services_info.get('active', 0)}/{services_info.get('total', 0)}")
            
            sources_info = summary.get("sources", {})
            print(f"   🔍 Fuentes activas: {sources_info.get('active', 0)}/{sources_info.get('total', 0)}")
        else:
            print(f"   ❌ Error en el resumen: {summary['error']}")
    else:
        print(f"   ❌ Error al obtener resumen: {summary_result.get('error', 'Unknown error')}")
    
    # 7. Mostrar información del catálogo actualizado
    print("\n📋 7. Información del catálogo actualizado...")
    catalog_file = "catalog.json"
    
    if os.path.exists(catalog_file):
        try:
            with open(catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
            
            print(f"   📁 Archivo del catálogo: {catalog_file}")
            print(f"   📄 Título: {catalog.get('dcterms:title', 'N/A')}")
            print(f"   📝 Descripción: {catalog.get('dcterms:description', 'N/A')}")
            
            # Mostrar secciones del catálogo
            sections = [
                ("dcat:service", "Servicios de datos"),
                ("dcat:dataset", "Datasets"),
                ("dcat:distribution", "Distribuciones"),
                ("custom:sources", "Fuentes rastreadas")
            ]
            
            for key, name in sections:
                count = len(catalog.get(key, []))
                print(f"   📊 {name}: {count} elementos")
                
        except Exception as e:
            print(f"   ❌ Error al leer catálogo: {e}")
    else:
        print(f"   ⚠️ Archivo de catálogo no encontrado: {catalog_file}")
    
    print("\n✨ Demo completada!")
    print("\n💡 Próximos pasos sugeridos:")
    print("   • Explorar más geoservers y registrarlos como servicios")
    print("   • Descargar más layers en diferentes formatos")
    print("   • Usar filtros espaciales y temáticos en las descargas")
    print("   • Exportar el catálogo en formato RDF/TTL")
    print("   • Integrar con sistemas de metadatos externos")


if __name__ == "__main__":
    main()
