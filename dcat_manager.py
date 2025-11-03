#!/usr/bin/env python3
"""
Utilidad para gestionar el catálogo DCAT desde línea de comandos.

Este script proporciona comandos para:
- Ver el estado del catálogo
- Buscar elementos en el catálogo
- Exportar/importar catálogo
- Gestionar fuentes de datos
"""
import sys
import os
import json
import argparse
from datetime import datetime
from typing import Optional

# Añadir rutas al path
project_root = os.path.dirname(__file__)
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, 'src'))

try:
    from src.core.services.dcat_catalog import get_catalog_manager
except ImportError:
    print("Error: No se pudo importar el gestor de catálogo DCAT")
    sys.exit(1)


def show_status(args):
    """Muestra el estado actual del catálogo."""
    catalog_manager = get_catalog_manager()
    
    print("📊 Estado del Catálogo DCAT")
    print("=" * 40)
    
    try:
        stats = catalog_manager.get_statistics()
        
        print(f"📈 Estadísticas generales:")
        print(f"  • Servicios de datos: {stats.get('total_services', 0)}")
        print(f"  • Datasets: {stats.get('total_datasets', 0)}")
        print(f"  • Distribuciones: {stats.get('total_distributions', 0)}")
        print(f"  • Fuentes rastreadas: {stats.get('total_sources', 0)}")
        print(f"  • Última actualización: {stats.get('last_updated', 'N/A')}")
        
        # Información detallada
        services = catalog_manager.get_services()
        datasets = catalog_manager.get_datasets()
        distributions = catalog_manager.get_distributions()
        sources = catalog_manager.get_sources()
        
        print(f"\n🔧 Servicios de datos:")
        if services:
            for service in services[:5]:  # Mostrar solo los primeros 5
                title = service.get('dcterms:title', 'Sin título')
                endpoint = service.get('dcat:endpointURL', 'N/A')
                status = service.get('custom:status', 'unknown')
                print(f"  • {title} [{status}] - {endpoint}")
            if len(services) > 5:
                print(f"  ... y {len(services) - 5} más")
        else:
            print("  (Ningún servicio registrado)")
        
        print(f"\n🗃️ Datasets:")
        if datasets:
            for dataset in datasets[:5]:
                title = dataset.get('dcterms:title', 'Sin título')
                creator = dataset.get('dcterms:creator', 'N/A')
                print(f"  • {title} (por {creator})")
            if len(datasets) > 5:
                print(f"  ... y {len(datasets) - 5} más")
        else:
            print("  (Ningún dataset registrado)")
        
        print(f"\n📦 Distribuciones:")
        if distributions:
            formats = {}
            total_size = 0
            for dist in distributions:
                fmt = dist.get('dcterms:format', 'unknown')
                formats[fmt] = formats.get(fmt, 0) + 1
                size = dist.get('dcat:byteSize', 0)
                if isinstance(size, (int, float)):
                    total_size += size
            
            print(f"  • Total: {len(distributions)} distribuciones")
            print(f"  • Formatos: {', '.join([f'{k}({v})' for k, v in formats.items()])}")
            if total_size > 0:
                size_mb = total_size / (1024 * 1024)
                print(f"  • Tamaño total: {size_mb:.2f} MB")
        else:
            print("  (Ninguna distribución registrada)")
        
        print(f"\n🔍 Fuentes rastreadas:")
        if sources:
            categories = {}
            for source in sources:
                cat = source.get('category', 'general')
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"  • Total: {len(sources)} fuentes")
            print(f"  • Categorías: {', '.join([f'{k}({v})' for k, v in categories.items()])}")
        else:
            print("  (Ninguna fuente registrada)")
        
    except Exception as e:
        print(f"❌ Error al obtener estado: {e}")


def search_catalog(args):
    """Busca elementos en el catálogo."""
    catalog_manager = get_catalog_manager()
    
    print(f"🔍 Buscando '{args.query}' en el catálogo")
    print("=" * 40)
    
    found_items = []
    
    try:
        # Buscar en servicios
        services = catalog_manager.get_services()
        for service in services:
            title = service.get('dcterms:title', '').lower()
            desc = service.get('dcterms:description', '').lower()
            if args.query.lower() in title or args.query.lower() in desc:
                found_items.append(('servicio', service))
        
        # Buscar en datasets
        datasets = catalog_manager.get_datasets()
        for dataset in datasets:
            title = dataset.get('dcterms:title', '').lower()
            desc = dataset.get('dcterms:description', '').lower()
            keywords = ' '.join(dataset.get('dcat:keyword', [])).lower()
            if (args.query.lower() in title or args.query.lower() in desc or 
                args.query.lower() in keywords):
                found_items.append(('dataset', dataset))
        
        # Buscar en distribuciones
        distributions = catalog_manager.get_distributions()
        for dist in distributions:
            title = dist.get('dcterms:title', '').lower()
            desc = dist.get('dcterms:description', '').lower()
            if args.query.lower() in title or args.query.lower() in desc:
                found_items.append(('distribución', dist))
        
        # Buscar en fuentes
        sources = catalog_manager.get_sources()
        for source in sources:
            name = source.get('name', '').lower()
            desc = source.get('description', '').lower()
            if args.query.lower() in name or args.query.lower() in desc:
                found_items.append(('fuente', source))
        
        if found_items:
            print(f"✅ Encontrados {len(found_items)} elementos:")
            for item_type, item in found_items:
                if item_type == 'servicio':
                    title = item.get('dcterms:title', 'Sin título')
                    endpoint = item.get('dcat:endpointURL', 'N/A')
                    print(f"  🔧 Servicio: {title} - {endpoint}")
                elif item_type == 'dataset':
                    title = item.get('dcterms:title', 'Sin título')
                    creator = item.get('dcterms:creator', 'N/A')
                    print(f"  🗃️ Dataset: {title} (por {creator})")
                elif item_type == 'distribución':
                    title = item.get('dcterms:title', 'Sin título')
                    format_type = item.get('dcterms:format', 'N/A')
                    print(f"  📦 Distribución: {title} [{format_type}]")
                elif item_type == 'fuente':
                    name = item.get('name', 'Sin nombre')
                    url = item.get('url', 'N/A')
                    print(f"  🔍 Fuente: {name} - {url}")
        else:
            print("❌ No se encontraron elementos que coincidan con la búsqueda")
            
    except Exception as e:
        print(f"❌ Error en la búsqueda: {e}")


def export_catalog(args):
    """Exporta el catálogo a un archivo."""
    catalog_manager = get_catalog_manager()
    
    try:
        # Exportar el catálogo completo
        catalog = catalog_manager.catalog
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Catálogo exportado a: {args.output}")
        
        # Estadísticas del export
        stats = catalog_manager.get_statistics()
        print(f"📊 Elementos exportados:")
        print(f"  • Servicios: {stats.get('total_services', 0)}")
        print(f"  • Datasets: {stats.get('total_datasets', 0)}")
        print(f"  • Distribuciones: {stats.get('total_distributions', 0)}")
        print(f"  • Fuentes: {stats.get('total_sources', 0)}")
        
    except Exception as e:
        print(f"❌ Error al exportar: {e}")


def list_sources(args):
    """Lista las fuentes de datos rastreadas."""
    catalog_manager = get_catalog_manager()
    
    print("🔍 Fuentes de Datos Rastreadas")
    print("=" * 40)
    
    try:
        sources = catalog_manager.get_sources()
        
        if not sources:
            print("❌ No hay fuentes registradas")
            return
        
        # Filtrar por categoría si se especifica
        if args.category:
            sources = [s for s in sources if s.get('category') == args.category]
            print(f"📁 Categoría: {args.category}")
        
        # Filtrar por estado si se especifica
        if args.status:
            sources = [s for s in sources if s.get('status') == args.status]
            print(f"📊 Estado: {args.status}")
        
        print(f"\n📈 Total: {len(sources)} fuentes\n")
        
        for i, source in enumerate(sources, 1):
            name = source.get('name', 'Sin nombre')
            url = source.get('url', 'N/A')
            status = source.get('status', 'unknown')
            category = source.get('category', 'general')
            description = source.get('description', '')
            
            print(f"{i}. {name}")
            print(f"   🔗 URL: {url}")
            print(f"   📊 Estado: {status} | Categoría: {category}")
            if description:
                print(f"   📝 Descripción: {description}")
            print()
            
    except Exception as e:
        print(f"❌ Error al listar fuentes: {e}")


def update_source_status(args):
    """Actualiza el estado de una fuente."""
    catalog_manager = get_catalog_manager()
    
    try:
        catalog_manager.update_item_status(args.source_id, args.status, args.notes)
        print(f"✅ Estado de la fuente {args.source_id} actualizado a: {args.status}")
        
        if args.notes:
            print(f"📝 Notas: {args.notes}")
            
    except Exception as e:
        print(f"❌ Error al actualizar estado: {e}")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="Utilidad para gestionar el catálogo DCAT",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando: status
    status_parser = subparsers.add_parser('status', help='Mostrar estado del catálogo')
    status_parser.set_defaults(func=show_status)
    
    # Comando: search
    search_parser = subparsers.add_parser('search', help='Buscar en el catálogo')
    search_parser.add_argument('query', help='Término de búsqueda')
    search_parser.set_defaults(func=search_catalog)
    
    # Comando: export
    export_parser = subparsers.add_parser('export', help='Exportar catálogo')
    export_parser.add_argument('output', help='Archivo de salida')
    export_parser.set_defaults(func=export_catalog)
    
    # Comando: sources
    sources_parser = subparsers.add_parser('sources', help='Listar fuentes rastreadas')
    sources_parser.add_argument('--category', help='Filtrar por categoría')
    sources_parser.add_argument('--status', help='Filtrar por estado')
    sources_parser.set_defaults(func=list_sources)
    
    # Comando: update-source
    update_parser = subparsers.add_parser('update-source', help='Actualizar estado de fuente')
    update_parser.add_argument('source_id', help='ID de la fuente')
    update_parser.add_argument('status', help='Nuevo estado')
    update_parser.add_argument('--notes', help='Notas adicionales')
    update_parser.set_defaults(func=update_source_status)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
