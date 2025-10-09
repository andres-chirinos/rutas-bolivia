"""
Ejemplos de uso del plugin GeoServer para el Datamesh Client.

Este archivo contiene ejemplos prácticos de cómo usar el plugin para
conectar con diferentes tipos de geoservers y descargar layers.
"""
import json
from plugin_interface import GeoServerPlugin


def example_geoserver_basic():
    """Ejemplo básico con GeoServer estándar."""
    plugin = GeoServerPlugin()
    
    # Configuración del geoserver
    base_url = "https://sitservicios.lapaz.bo/geoserver"
    
    # 1. Probar conexión
    print("=== Test Connection ===")
    result = plugin.execute_method("test_connection", 
                                  base_url=base_url, 
                                  server_type="geoserver")
    print(json.dumps(result, indent=2))
    
    # 2. Obtener capabilidades
    print("\n=== Get Capabilities ===")
    result = plugin.execute_method("get_capabilities",
                                  base_url=base_url,
                                  service="WFS")
    print(json.dumps(result, indent=2))
    
    # 3. Listar layers
    print("\n=== List Layers ===")
    result = plugin.execute_method("list_layers",
                                  base_url=base_url,
                                  service="WFS")
    print(json.dumps(result, indent=2))
    
    # 4. Descargar un layer específico
    print("\n=== Download Layer ===")
    result = plugin.execute_method("download_layer",
                                  base_url=base_url,
                                  layer_name="topp:states",
                                  output_format="geojson",
                                  title="US States",
                                  description="United States state boundaries")
    print(json.dumps(result, indent=2))


def example_geoserver_with_auth():
    """Ejemplo con autenticación."""
    plugin = GeoServerPlugin()
    
    # Configuración con autenticación
    base_url = "https://demo.geo-solutions.it/geoserver"
    username = "admin"
    password = "geoserver"
    
    # Descargar layer con autenticación
    result = plugin.execute_method("download_layer",
                                  base_url=base_url,
                                  layer_name="tiger:poi",
                                  output_format="geojson",
                                  username=username,
                                  password=password,
                                  maxFeatures=100)
    print(json.dumps(result, indent=2))


def example_mapserver():
    """Ejemplo con MapServer."""
    plugin = GeoServerPlugin()
    
    # Configuración MapServer
    base_url = "https://demo.mapserver.org/cgi-bin/mapserv"
    
    # Obtener capabilidades
    result = plugin.execute_method("get_capabilities",
                                  base_url=base_url,
                                  server_type="mapserver",
                                  service="WMS")
    print(json.dumps(result, indent=2))


def example_arcgis_server():
    """Ejemplo con ArcGIS Server."""
    plugin = GeoServerPlugin()
    
    # Configuración ArcGIS Server
    base_url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services"
    
    # Obtener capabilidades
    result = plugin.execute_method("get_capabilities",
                                  base_url=base_url,
                                  server_type="arcgis")
    print(json.dumps(result, indent=2))


def example_batch_download():
    """Ejemplo de descarga en lote."""
    plugin = GeoServerPlugin()
    
    base_url = "http://localhost:8080/geoserver"
    layer_names = ["topp:states", "topp:tasmania_roads", "topp:tasmania_cities"]
    
    # Descarga múltiple
    result = plugin.execute_method("batch_download",
                                  base_url=base_url,
                                  layer_names=layer_names,
                                  output_format="geojson",
                                  maxFeatures=50)
    print(json.dumps(result, indent=2))


def example_with_filters():
    """Ejemplo con filtros espaciales y atributos."""
    plugin = GeoServerPlugin()
    
    base_url = "http://localhost:8080/geoserver"
    
    # Descarga con bbox (área específica)
    result = plugin.execute_method("download_layer",
                                  base_url=base_url,
                                  layer_name="topp:states",
                                  output_format="geojson",
                                  bbox="-124,32,-114,42",  # California area
                                  crs="EPSG:4326",
                                  maxFeatures=10,
                                  title="California States",
                                  description="States in California area")
    print(json.dumps(result, indent=2))


def example_different_formats():
    """Ejemplo con diferentes formatos de salida."""
    plugin = GeoServerPlugin()
    
    base_url = "http://localhost:8080/geoserver"
    layer_name = "topp:states"
    
    formats = ["geojson", "shapefile", "gml", "kml", "csv"]
    
    for fmt in formats:
        print(f"\n=== Downloading as {fmt.upper()} ===")
        result = plugin.execute_method("download_layer",
                                      base_url=base_url,
                                      layer_name=layer_name,
                                      output_format=fmt,
                                      maxFeatures=5,
                                      title=f"States as {fmt}")
        if result["success"]:
            print(f"✅ Downloaded: {result['result']['file_path']}")
        else:
            print(f"❌ Error: {result['error']}")


def example_get_server_info():
    """Ejemplo para obtener información del plugin."""
    plugin = GeoServerPlugin()
    
    result = plugin.execute_method("get_server_info")
    print("=== Plugin Information ===")
    print(json.dumps(result, indent=2))


def example_real_world_geoservers():
    """Ejemplos con geoservers públicos reales."""
    plugin = GeoServerPlugin()
    
    # Lista de geoservers públicos para probar
    public_servers = [
        {
            "name": "Natural Earth",
            "url": "https://www.naturalearthdata.com/http//www.naturalearthdata.com/download/50m/cultural/ne_50m_admin_0_countries.zip",
            "type": "direct_download"
        },
        {
            "name": "USGS WFS",
            "url": "https://mrdata.usgs.gov/services/geolex",
            "type": "geoserver"
        }
    ]
    
    for server in public_servers:
        if server["type"] == "geoserver":
            print(f"\n=== Testing {server['name']} ===")
            result = plugin.execute_method("test_connection",
                                          base_url=server["url"],
                                          server_type="geoserver")
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    print("GeoServer Plugin Examples")
    print("=" * 50)
    
    # Ejecutar ejemplos básicos
    print("\n1. Plugin Information")
    example_get_server_info()
    
    print("\n2. Testing public servers")
    example_real_world_geoservers()
    
    # Para los otros ejemplos, necesitarías un geoserver local ejecutándose
    print("\nNote: Other examples require a local GeoServer running at http://localhost:8080/geoserver")
    print("You can start GeoServer using Docker:")
    print("docker run -d -p 8080:8080 kartoza/geoserver:2.18.0")
