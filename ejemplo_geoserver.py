#!/usr/bin/env python3
"""
Ejemplo práctico del plugin GeoServer para el Datamesh Client.

Este script demuestra cómo usar el plugin para conectar con geoservers
y descargar layers en diferentes formatos.
"""
import sys
import os
import json

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.core.services.plugin_manager import PluginManager


def print_separator(title):
    """Imprime un separador con título."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def main():
    """Función principal del ejemplo."""
    
    print("🌍 Plugin GeoServer - Ejemplo Práctico")
    print("Conectando con geoservers y descargando datos geoespaciales")
    
    # Inicializar plugin manager
    manager = PluginManager()
    manager.discover('plugins')
    
    # Obtener plugin de geoserver
    plugin = manager.get_data_fetcher('geoserver')
    if not plugin:
        print("❌ Error: Plugin geoserver no encontrado")
        return
    
    print_separator("1. Información del Plugin")
    
    # Mostrar información del plugin
    result = plugin.execute_method('get_server_info')
    if result['success']:
        info = result['result']
        print(f"✅ Plugin versión: {info['plugin_version']}")
        print(f"📊 Tipos de servidor soportados: {len(info['supported_servers'])}")
        print(f"📄 Formatos de salida soportados: {len(info['supported_formats'])}")
        print(f"🌐 Servicios OGC: {', '.join(info['services'])}")
    else:
        print(f"❌ Error: {result['error']}")
    
    print_separator("2. Probando Conexión con Geoserver Público")
    
    # Probar conexión con un geoserver público
    geoserver_url = "https://sitservicios.lapaz.bo/geoserver/"
    
    result = plugin.execute_method('test_connection', base_url=geoserver_url)
    if result['success']:
        conn_result = result['result']
        if conn_result['connection_status'] == 'success':
            print(f"✅ Conexión exitosa con {geoserver_url}")
            print(f"📊 Layers disponibles: {conn_result['available_layers']}")
            print(f"🔗 URL de capacidades: {conn_result['capabilities_url']}")
        else:
            print(f"❌ Fallo de conexión: {conn_result['error']}")
    else:
        print(f"❌ Error en test: {result['error']}")
    
    print_separator("3. Listando Layers Disponibles")
    
    # Listar layers disponibles
    result = plugin.execute_method('list_layers', 
                                  base_url=geoserver_url, 
                                  service='WMS')
    if result['success']:
        layers_result = result['result']
        layers = layers_result['layers']
        print(f"🗂️ Total de layers WMS encontrados: {len(layers)}")
        
        if layers:
            print("\n📋 Primeros 5 layers:")
            for i, layer in enumerate(layers[:5], 1):
                print(f"  {i}. {layer['name']}: {layer['title']}")
                if layer['abstract']:
                    print(f"     📄 {layer['abstract'][:100]}...")
        
        # Intentar con WFS también
        result_wfs = plugin.execute_method('list_layers',
                                          base_url=geoserver_url,
                                          service='WFS')
        if result_wfs['success']:
            wfs_layers = result_wfs['result']['layers']
            print(f"\n🗃️ Layers WFS encontrados: {len(wfs_layers)}")
    else:
        print(f"❌ Error listando layers: {result['error']}")
    
    print_separator("4. Descargando Layer de Ejemplo")
    
    # Seleccionar layer para descargar
    target_layer = "opengeo:countries"
    
    print(f"📥 Descargando layer: {target_layer}")
    print(f"🔧 Formato: GeoJSON")
    print(f"📊 Límite: 10 features")
    
    result = plugin.execute_method('download_layer',
                                  base_url=geoserver_url,
                                  layer_name=target_layer,
                                  output_format='geojson',
                                  service='WFS',
                                  title='Países del Mundo (Muestra)',
                                  description='Muestra de países del mundo descargada desde geoserver público',
                                  maxFeatures=10)
    
    if result['success']:
        download_result = result['result']
        asset = download_result['asset']
        
        print(f"✅ Descarga exitosa!")
        print(f"📁 Archivo guardado en: {download_result['file_path']}")
        print(f"🆔 Asset ID: {asset['id']}")
        print(f"📊 Features descargadas: {asset['results_count']}")
        print(f"📚 Diccionario de datos: {asset['data_dictionary_uri']}")
        
        # Mostrar preview del archivo
        try:
            with open(download_result['file_path'], 'r') as f:
                data = json.load(f)
                feature_count = len(data.get('features', []))
                print(f"\n📋 Preview del archivo:")
                print(f"   Tipo: {data.get('type', 'N/A')}")
                print(f"   Features: {feature_count}")
                if feature_count > 0:
                    first_feature = data['features'][0]
                    props = first_feature.get('properties', {})
                    print(f"   Propiedades del primer feature:")
                    for key, value in list(props.items())[:3]:
                        print(f"     - {key}: {value}")
        except Exception as e:
            print(f"⚠️ No se pudo leer el archivo: {e}")
    else:
        print(f"❌ Error en descarga: {result['error']}")
    
    print_separator("5. Probando Diferentes Formatos")
    
    # Probar diferentes formatos
    formats_to_test = ['geojson', 'gml', 'csv']
    
    for fmt in formats_to_test:
        print(f"\n🔄 Probando formato: {fmt.upper()}")
        
        result = plugin.execute_method('download_layer',
                                      base_url=geoserver_url,
                                      layer_name=target_layer,
                                      output_format=fmt,
                                      service='WFS',
                                      title=f'Países ({fmt.upper()})',
                                      description=f'Países en formato {fmt}',
                                      maxFeatures=3)
        
        if result['success']:
            download_result = result['result']
            print(f"   ✅ {fmt.upper()}: {download_result['file_path']}")
        else:
            print(f"   ❌ {fmt.upper()}: {result['error']}")
    
    print_separator("6. Resumen Final")
    
    print("🎉 Ejemplo completado!")
    print("\n📋 Lo que hemos demostrado:")
    print("   ✅ Información del plugin y capacidades")
    print("   ✅ Conexión con geoserver público")
    print("   ✅ Listado de layers disponibles")
    print("   ✅ Descarga de datos en formato GeoJSON")
    print("   ✅ Prueba de múltiples formatos de salida")
    print("   ✅ Creación automática de assets y diccionarios de datos")
    
    print("\n🚀 Próximos pasos:")
    print("   - Explorar más geoservers públicos")
    print("   - Usar filtros espaciales (bbox)")
    print("   - Probar con autenticación")
    print("   - Descargar datasets más grandes")
    print("   - Explorar diferentes servicios (WMS, WCS)")
    
    print("\n📚 Para más información:")
    print("   - Ver plugins/geoserver_plugin/README.md")
    print("   - Ejecutar: python -m src.adapters.cli.dm_cli plugin info geoserver")
    print("   - Revisar examples.py para más casos de uso")


if __name__ == "__main__":
    main()
