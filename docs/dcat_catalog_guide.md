# Catálogo DCAT Extendido - Guía Completa

## 📋 Visión General

El sistema de catálogo DCAT extendido permite realizar un seguimiento completo de fuentes de datos siguiendo el estándar **Data Catalog Vocabulary (DCAT)** del W3C. Este sistema va más allá de los simples "assets" y proporciona una estructura rica para gestionar:

- **🔧 Servicios de datos** (`dcat:DataService`) - Geoservers, APIs, servicios OGC
- **🗃️ Datasets** (`dcat:Dataset`) - Conjuntos de datos temáticos
- **📦 Distribuciones** (`dcat:Distribution`) - Archivos y formatos específicos
- **🔍 Fuentes rastreadas** - URLs y servicios de interés para seguimiento

## 🏗️ Arquitectura

### Estructura del Catálogo

```json
{
  "@context": {
    "dcat": "http://www.w3.org/ns/dcat#",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "vcard": "http://www.w3.org/2006/vcard/ns#"
  },
  "@type": "dcat:Catalog",
  "dcterms:title": "Datamesh Client Catalog",
  "dcat:service": [],        // Servicios de datos
  "dcat:dataset": [],        // Datasets
  "dcat:distribution": [],   // Distribuciones/Assets
  "custom:sources": [],      // Fuentes rastreadas
  "custom:statistics": {}    // Estadísticas del catálogo
}
```

### Componentes Principales

1. **`DCATCatalogManager`** - Gestor principal del catálogo
2. **Plugin GeoServer extendido** - Integración automática con DCAT
3. **Utilidades de línea de comandos** - Gestión manual del catálogo

## 🚀 Uso Rápido

### 1. Registrar un Servicio de Datos

```python
from plugins.geoserver_plugin.plugin_interface import geoserver_plugin

# Registrar un geoserver como servicio
result = geoserver_plugin.execute_method(
    "register_service",
    base_url="https://ejemplo.com/geoserver",
    server_type="geoserver",
    service_name="Mi GeoServer",
    description="Servidor con datos geoespaciales importantes"
)

service_id = result["result"]["service_id"]
```

### 2. Registrar un Dataset

```python
# Registrar un layer como dataset
result = geoserver_plugin.execute_method(
    "register_layer_dataset",
    base_url="https://ejemplo.com/geoserver",
    layer_name="mi_layer",
    service_id=service_id  # Vincularlo al servicio
)

dataset_id = result["result"]["dataset_id"]
```

### 3. Descargar y Registrar Distribución

```python
# Descargar layer y registrar automáticamente la distribución
result = geoserver_plugin.execute_method(
    "download_layer",
    base_url="https://ejemplo.com/geoserver",
    layer_name="mi_layer",
    output_format="geojson",
    dataset_id=dataset_id  # Vincular a dataset
)
```

### 4. Registrar Fuente Interesante

```python
# Registrar una fuente para seguimiento futuro
result = geoserver_plugin.execute_method(
    "register_source",
    url="https://nuevo-geoserver.com",
    name="Nuevo Servidor Interesante",
    description="Fuente descubierta con datos prometedores",
    category="government",
    tags=["prometedor", "gobierno", "gis"]
)
```

## 🛠️ Uso desde Línea de Comandos

### Ver Estado del Catálogo

```bash
./dcat_manager.py status
```

### Buscar en el Catálogo

```bash
./dcat_manager.py search "countries"
./dcat_manager.py search "geoserver"
```

### Listar Fuentes Rastreadas

```bash
# Todas las fuentes
./dcat_manager.py sources

# Por categoría
./dcat_manager.py sources --category government

# Por estado
./dcat_manager.py sources --status active
```

### Actualizar Estado de Fuente

```bash
./dcat_manager.py update-source SOURCE_ID checked --notes "Revisado manualmente"
```

### Exportar Catálogo

```bash
./dcat_manager.py export mi_catalogo_backup.json
```

## 📊 Métodos del Plugin Extendido

### Nuevos Métodos Disponibles

| Método | Descripción | Parámetros Principales |
|--------|-------------|----------------------|
| `register_service` | Registra geoserver como servicio | `base_url`, `service_name`, `description` |
| `register_layer_dataset` | Registra layer como dataset | `base_url`, `layer_name`, `service_id` |
| `register_source` | Registra fuente para seguimiento | `url`, `name`, `category`, `tags` |
| `get_catalog_summary` | Obtiene resumen del catálogo | - |

### Métodos Actualizados

- **`download_layer`** - Ahora registra automáticamente distribuciones en DCAT
- Todos los métodos mantienen compatibilidad hacia atrás

## 📁 Estructura de Datos

### Servicio de Datos (`dcat:DataService`)

```json
{
  "@type": "dcat:DataService",
  "dcterms:identifier": "service-uuid",
  "dcterms:title": "Mi GeoServer",
  "dcterms:description": "Descripción del servicio",
  "dcat:endpointURL": "https://ejemplo.com/geoserver",
  "custom:serviceType": "ogc",
  "custom:serverType": "geoserver",
  "custom:ogcServices": ["WMS", "WFS", "WCS"],
  "custom:layers": ["layer1", "layer2"],
  "custom:authentication": {
    "type": "basic",
    "required": true
  },
  "custom:status": "active",
  "custom:tags": ["gis", "ogc", "spatial-data"]
}
```

### Dataset (`dcat:Dataset`)

```json
{
  "@type": "dcat:Dataset",
  "dcterms:identifier": "dataset-uuid",
  "dcterms:title": "Mi Dataset",
  "dcterms:description": "Descripción del dataset",
  "dcterms:spatial": {
    "bbox": [minx, miny, maxx, maxy],
    "crs": "EPSG:4326"
  },
  "dcat:theme": ["geospatial", "geography"],
  "dcat:keyword": ["countries", "borders"],
  "custom:source": "https://ejemplo.com/geoserver/layer/mi_layer",
  "custom:format": ["WMS", "WFS", "GeoJSON"]
}
```

### Distribución (`dcat:Distribution`)

```json
{
  "@type": "dcat:Distribution",
  "dcterms:identifier": "dist-uuid",
  "dcterms:title": "Mi Layer - GeoJSON",
  "dcat:downloadURL": "file:///path/to/layer.geojson",
  "dcat:mediaType": "application/geo+json",
  "dcterms:format": "GEOJSON",
  "dcat:byteSize": 1048576,
  "custom:source": "https://ejemplo.com/geoserver",
  "custom:filePath": "/path/to/layer.geojson",
  "custom:resultsCount": 241,
  "custom:metadata": {
    "layer_name": "mi_layer",
    "bbox": {},
    "crs": "EPSG:4326"
  }
}
```

### Fuente Rastreada (`custom:sources`)

```json
{
  "id": "source-uuid",
  "name": "Fuente Interesante",
  "description": "Descripción de la fuente",
  "url": "https://ejemplo.com",
  "type": "geoserver",
  "category": "government",
  "status": "discovered",
  "check_frequency": "manual",
  "tags": ["prometedor", "gobierno"],
  "notes": "Fuente descubierta automáticamente",
  "related_services": [],
  "related_datasets": []
}
```

## 📈 Flujo de Trabajo Recomendado

### 1. Descubrimiento y Registro

```bash
# 1. Descubrir nuevos geoservers
./dcat_manager.py sources --status discovered

# 2. Probar conexión
python -c "
from plugins.geoserver_plugin.plugin_interface import geoserver_plugin
result = geoserver_plugin.execute_method('test_connection', 
    base_url='https://nuevo-servidor.com/geoserver')
print(result)
"

# 3. Registrar como servicio si funciona
python ejemplo_dcat_catalog.py
```

### 2. Gestión de Datasets

```python
# Listar layers disponibles
layers_result = geoserver_plugin.execute_method(
    "list_layers", 
    base_url="https://mi-servidor.com/geoserver"
)

# Registrar layers interesantes como datasets
for layer in layers_result["result"]["layers"]:
    if "country" in layer["name"].lower():
        geoserver_plugin.execute_method(
            "register_layer_dataset",
            base_url="https://mi-servidor.com/geoserver",
            layer_name=layer["name"],
            service_id=service_id
        )
```

### 3. Descarga y Archivado

```python
# Descargar en múltiples formatos
formats = ["geojson", "shapefile", "gml", "csv"]

for fmt in formats:
    result = geoserver_plugin.execute_method(
        "download_layer",
        base_url="https://mi-servidor.com/geoserver",
        layer_name="countries",
        output_format=fmt,
        dataset_id=dataset_id,
        maxFeatures=1000
    )
```

### 4. Monitoreo y Mantenimiento

```bash
# Verificar estado del catálogo
./dcat_manager.py status

# Buscar elementos específicos
./dcat_manager.py search "countries"

# Exportar backup
./dcat_manager.py export backup_$(date +%Y%m%d).json

# Actualizar estados de fuentes
./dcat_manager.py sources --status discovered | while read source_id; do
    ./dcat_manager.py update-source $source_id checked --notes "Revisado $(date)"
done
```

## 🔄 Migración desde Sistema Anterior

El sistema es **completamente compatible hacia atrás**. Los assets existentes se migran automáticamente:

```json
// Antes (assets)
{
  "assets": [
    {
      "id": "asset-123",
      "title": "Mi Asset",
      "description": "Descripción",
      "source": "geoserver"
    }
  ]
}

// Después (DCAT)
{
  "dcat:distribution": [
    {
      "@type": "dcat:Distribution",
      "dcterms:identifier": "asset-123",
      "dcterms:title": "Mi Asset",
      "dcterms:description": "Descripción",
      "custom:source": "geoserver"
    }
  ]
}
```

## 🎯 Casos de Uso

### 1. Investigación Académica

```python
# Registrar repositorios universitarios
universities = [
    "https://maps.princeton.edu/geoserver",
    "https://gis.harvard.edu/geoserver",
    "https://geodata.mit.edu/geoserver"
]

for url in universities:
    geoserver_plugin.execute_method("register_source",
        url=url, category="academic", 
        tags=["university", "research"])
```

### 2. Datos Gubernamentales

```python
# Registrar servicios oficiales
gov_services = [
    {
        "url": "https://geoservices.ign.es/wms",
        "name": "IGN España",
        "category": "government"
    },
    {
        "url": "https://www.ign.gob.ar/geoservicios",
        "name": "IGN Argentina", 
        "category": "government"
    }
]

for service in gov_services:
    geoserver_plugin.execute_method("register_source", **service)
```

### 3. Monitoreo de Calidad

```bash
# Script de monitoreo diario
#!/bin/bash
echo "Verificando fuentes activas..."
./dcat_manager.py sources --status active | while read line; do
    echo "Verificando: $line"
    # Aquí iría lógica de verificación
done

# Generar reporte
./dcat_manager.py status > reporte_diario_$(date +%Y%m%d).txt
```

## 📚 Referencias

- [DCAT Specification](https://www.w3.org/TR/vocab-dcat/)
- [Dublin Core Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/)
- [OGC Standards](https://www.ogc.org/standards/)

## 🔧 Extensiones Futuras

- Exportación RDF/TTL completa
- Integración con portales CKAN
- Validación automática de servicios
- Métricas de uso y calidad
- Sincronización con catálogos externos
