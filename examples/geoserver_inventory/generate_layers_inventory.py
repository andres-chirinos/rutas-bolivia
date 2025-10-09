#!/usr/bin/env python3
"""
Script para generar inventario completo de layers desde múltiples geoservers.

Este script lee un catálogo de geoservers conocidos y genera un CSV completo
con todas las layers disponibles, incluyendo metadatos y información del servidor.
"""
import sys
import os
import json
import csv
import time
from datetime import datetime
from typing import Dict, Any, List
from urllib.parse import urlparse

# Añadir rutas al path
script_dir = os.path.dirname(__file__)
project_root = os.path.join(script_dir, '..', '..')
sys.path.append(project_root)

from plugins.geoserver_plugin.plugin_interface import geoserver_plugin


class GeoServerInventory:
    """Generador de inventario de layers de múltiples geoservers."""
    
    def __init__(self, catalog_file: str):
        """
        Inicializa el inventario.
        
        Args:
            catalog_file: Archivo JSON con el catálogo de geoservers
        """
        self.catalog_file = catalog_file
        self.catalog = self._load_catalog()
        self.results = []
        self.errors = []
        
    def _load_catalog(self) -> Dict[str, Any]:
        """Carga el catálogo de geoservers."""
        try:
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error al cargar catálogo: {e}")
            return {"geoservers": []}
    
    def generate_inventory(self, output_file: str = None, 
                         categories: List[str] = None,
                         countries: List[str] = None,
                         server_types: List[str] = None,
                         test_connection: bool = True,
                         max_servers: int = None) -> str:
        """
        Genera el inventario completo de layers.
        
        Args:
            output_file: Archivo CSV de salida
            categories: Filtrar por categorías específicas
            countries: Filtrar por países específicos  
            server_types: Filtrar por tipos de servidor
            test_connection: Si probar conexión antes de listar layers
            max_servers: Máximo número de servidores a procesar
            
        Returns:
            Ruta del archivo CSV generado
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"geoserver_inventory_{timestamp}.csv"
        
        print(f"🌍 Iniciando inventario de layers de geoservers")
        print(f"📁 Catálogo: {self.catalog_file}")
        print(f"📄 Salida: {output_file}")
        print("=" * 60)
        
        # Filtrar geoservers según criterios
        geoservers = self._filter_geoservers(categories, countries, server_types)
        
        if max_servers:
            geoservers = geoservers[:max_servers]
            
        print(f"📊 Procesando {len(geoservers)} geoservers...")
        
        # Procesar cada geoserver
        for i, server in enumerate(geoservers, 1):
            print(f"\n🔍 [{i}/{len(geoservers)}] Procesando: {server['name']}")
            print(f"   🔗 URL: {server['url']}")
            print(f"   🏷️ Categoría: {server['category']} | País: {server['country']}")
            
            try:
                self._process_server(server, test_connection)
            except Exception as e:
                error_msg = f"Error procesando {server['name']}: {e}"
                print(f"   ❌ {error_msg}")
                self.errors.append({
                    'server_name': server['name'],
                    'server_url': server['url'],
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })
            
            # Pequeña pausa para no sobrecargar servidores
            time.sleep(1)
        
        # Generar CSV
        csv_path = self._generate_csv(output_file)
        
        # Mostrar resumen
        self._show_summary(csv_path)
        
        return csv_path
    
    def _filter_geoservers(self, categories: List[str] = None,
                         countries: List[str] = None,
                         server_types: List[str] = None) -> List[Dict[str, Any]]:
        """Filtra geoservers según criterios especificados."""
        servers = self.catalog.get("geoservers", [])
        
        if categories:
            servers = [s for s in servers if s.get("category") in categories]
            
        if countries:
            servers = [s for s in servers if s.get("country") in countries]
            
        if server_types:
            servers = [s for s in servers if s.get("type") in server_types]
            
        return servers
    
    def _process_server(self, server: Dict[str, Any], test_connection: bool = True):
        """Procesa un servidor individual."""
        server_url = server['url']
        server_type = server.get('type', 'geoserver')
        
        # Test de conexión opcional
        if test_connection:
            print(f"   🔍 Probando conexión...")
            connection_result = geoserver_plugin.execute_method(
                "test_connection",
                base_url=server_url,
                server_type=server_type
            )
            
            if not connection_result.get("success", False):
                error_msg = f"Conexión fallida: {connection_result.get('error', 'Unknown error')}"
                print(f"   ❌ {error_msg}")
                self.errors.append({
                    'server_name': server['name'],
                    'server_url': server_url,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat()
                })
                return
            
            print(f"   ✅ Conexión exitosa")
        
        # Listar layers
        print(f"   📋 Obteniendo lista de layers...")
        layers_result = geoserver_plugin.execute_method(
            "list_layers",
            base_url=server_url,
            server_type=server_type
        )
        
        if not layers_result.get("success", False):
            error_msg = f"Error listando layers: {layers_result.get('error', 'Unknown error')}"
            print(f"   ❌ {error_msg}")
            self.errors.append({
                'server_name': server['name'],
                'server_url': server_url,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            })
            return
        
        layers = layers_result.get("result", {}).get("layers", [])
        print(f"   📊 Encontrados {len(layers)} layers")
        
        # Procesar cada layer
        for layer in layers:
            layer_info = self._extract_layer_info(server, layer)
            self.results.append(layer_info)
            
    def _extract_layer_info(self, server: Dict[str, Any], layer: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae información detallada de un layer."""
        return {
            # Información del servidor
            'server_name': server['name'],
            'server_url': server['url'],
            'server_type': server.get('type', 'unknown'),
            'server_category': server.get('category', 'unknown'),
            'server_country': server.get('country', 'unknown'),
            'server_organization': server.get('organization', 'unknown'),
            
            # Información del layer
            'layer_name': layer.get('name', ''),
            'layer_title': layer.get('title', ''),
            'layer_abstract': layer.get('abstract', ''),
            'layer_service': layer.get('service', ''),
            'layer_services': ', '.join(layer.get('services', [])),
            
            # Información espacial
            'bbox_minx': layer.get('bbox', {}).get('minx', ''),
            'bbox_miny': layer.get('bbox', {}).get('miny', ''),
            'bbox_maxx': layer.get('bbox', {}).get('maxx', ''),
            'bbox_maxy': layer.get('bbox', {}).get('maxy', ''),
            'crs': layer.get('crs', ''),
            
            # URLs de acceso
            'wms_url': f"{server['url']}/wms?service=WMS&version=1.3.0&request=GetMap&layers={layer.get('name', '')}" if server.get('type') == 'geoserver' else '',
            'wfs_url': f"{server['url']}/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName={layer.get('name', '')}" if server.get('type') == 'geoserver' else '',
            
            # Metadatos adicionales
            'keywords': ', '.join(layer.get('keywords', [])),
            'last_modified': layer.get('last_modified', ''),
            'feature_count': layer.get('feature_count', ''),
            
            # Información de inventario
            'inventory_date': datetime.now().isoformat(),
            'accessible': 'Yes',
            'notes': ''
        }
    
    def _generate_csv(self, output_file: str) -> str:
        """Genera el archivo CSV con los resultados."""
        if not self.results:
            print("⚠️ No se encontraron layers para exportar")
            return None
            
        # Definir columnas del CSV
        fieldnames = [
            'server_name', 'server_url', 'server_type', 'server_category', 
            'server_country', 'server_organization',
            'layer_name', 'layer_title', 'layer_abstract', 'layer_service', 'layer_services',
            'bbox_minx', 'bbox_miny', 'bbox_maxx', 'bbox_maxy', 'crs',
            'wms_url', 'wfs_url',
            'keywords', 'last_modified', 'feature_count',
            'inventory_date', 'accessible', 'notes'
        ]
        
        # Escribir CSV
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"\n📄 CSV generado: {output_file}")
        return output_file
    
    def _show_summary(self, csv_path: str):
        """Muestra resumen del inventario generado."""
        print(f"\n📊 RESUMEN DEL INVENTARIO")
        print("=" * 40)
        
        if self.results:
            total_layers = len(self.results)
            total_servers = len(set(r['server_name'] for r in self.results))
            
            print(f"✅ Layers encontrados: {total_layers}")
            print(f"🔧 Servidores procesados: {total_servers}")
            
            # Estadísticas por categoría
            categories = {}
            countries = {}
            server_types = {}
            
            for result in self.results:
                cat = result['server_category']
                categories[cat] = categories.get(cat, 0) + 1
                
                country = result['server_country']
                countries[country] = countries.get(country, 0) + 1
                
                srv_type = result['server_type']
                server_types[srv_type] = server_types.get(srv_type, 0) + 1
            
            print(f"\n📈 Por categoría:")
            for cat, count in sorted(categories.items()):
                print(f"   • {cat}: {count} layers")
                
            print(f"\n🌍 Por país:")
            for country, count in sorted(countries.items()):
                print(f"   • {country}: {count} layers")
                
            print(f"\n🔧 Por tipo de servidor:")
            for srv_type, count in sorted(server_types.items()):
                print(f"   • {srv_type}: {count} layers")
        
        if self.errors:
            print(f"\n❌ Errores encontrados: {len(self.errors)}")
            for error in self.errors[:5]:  # Mostrar solo los primeros 5
                print(f"   • {error['server_name']}: {error['error']}")
            if len(self.errors) > 5:
                print(f"   ... y {len(self.errors) - 5} errores más")
        
        if csv_path:
            file_size = os.path.getsize(csv_path) / 1024  # KB
            print(f"\n📁 Archivo generado:")
            print(f"   📄 {csv_path}")
            print(f"   📊 Tamaño: {file_size:.1f} KB")
        
        print(f"\n✨ Inventario completado!")


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Genera inventario de layers de múltiples geoservers",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('catalog', help='Archivo JSON con catálogo de geoservers')
    parser.add_argument('-o', '--output', help='Archivo CSV de salida')
    parser.add_argument('-c', '--categories', nargs='+', 
                       help='Filtrar por categorías (demo, government, academic, etc.)')
    parser.add_argument('--countries', nargs='+',
                       help='Filtrar por países')
    parser.add_argument('--server-types', nargs='+',
                       help='Filtrar por tipos de servidor (geoserver, arcgis, mapserver)')
    parser.add_argument('--no-test', action='store_true',
                       help='No probar conexión antes de listar layers')
    parser.add_argument('--max-servers', type=int,
                       help='Máximo número de servidores a procesar')
    
    args = parser.parse_args()
    
    # Crear inventario
    inventory = GeoServerInventory(args.catalog)
    
    # Generar inventario
    csv_path = inventory.generate_inventory(
        output_file=args.output,
        categories=args.categories,
        countries=args.countries,
        server_types=args.server_types,
        test_connection=not args.no_test,
        max_servers=args.max_servers
    )
    
    return csv_path


if __name__ == "__main__":
    main()
