# Plugin GeoServer - Documentación

Este plugin permite conectar con diferentes tipos de geoservers y descargar layers en diversos formatos. Soporta múltiples tipos de servidores geoespaciales y servicios OGC estándar.

## Características

### Tipos de Geoservers Soportados

1. **GeoServer** - Open source server for sharing geospatial data
2. **MapServer** - Platform for publishing spatial data and interactive mapping applications  
3. **ArcGIS Server** - Esri's server software for sharing geospatial services
4. **QGIS Server** - QGIS Server provides web services using QGIS libraries

### Servicios OGC Soportados

- **WMS** (Web Map Service) - Para mapas e imágenes
- **WFS** (Web Feature Service) - Para datos vectoriales
- **WCS** (Web Coverage Service) - Para datos raster/cobertura

### Formatos de Salida

- **GeoJSON** - Formato JSON para datos geoespaciales
- **Shapefile** - Formato estándar ESRI (como ZIP)
- **GML** - Geography Markup Language
- **KML** - Keyhole Markup Language (Google Earth)
- **CSV** - Comma-separated values
- **JSON** - JavaScript Object Notation

## Métodos Disponibles

### 1. `get_capabilities`

Obtiene las capacidades de un geoserver para un servicio específico.

**Parámetros:**
- `base_url` (requerido): URL base del geoserver
- `server_type` (opcional): Tipo de servidor (default: "geoserver")
- `service` (opcional): Tipo de servicio OGC (default: "WMS")
- `username` (opcional): Usuario para autenticación
- `password` (opcional): Contraseña para autenticación
- `token` (opcional): Token de autenticación (para ArcGIS)

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver get_capabilities \
  --json '{"base_url": "http://localhost:8080/geoserver", "service": "WFS"}'
```

### 2. `list_layers`

Lista todos los layers disponibles en un geoserver.

**Parámetros:**
- `base_url` (requerido): URL base del geoserver
- `server_type` (opcional): Tipo de servidor (default: "geoserver")
- `service` (opcional): Tipo de servicio OGC (default: "WFS")
- `username` (opcional): Usuario para autenticación
- `password` (opcional): Contraseña para autenticación

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver list_layers \
  --json '{"base_url": "https://demo.geo-solutions.it/geoserver", "service": "WFS"}'
```

### 3. `download_layer`

Descarga un layer específico del geoserver.

**Parámetros:**
- `base_url` (requerido): URL base del geoserver
- `layer_name` (requerido): Nombre del layer a descargar
- `output_format` (opcional): Formato de salida (default: "geojson")
- `server_type` (opcional): Tipo de servidor (default: "geoserver")
- `service` (opcional): Tipo de servicio OGC (default: "WFS")
- `title` (opcional): Título para el asset resultante
- `description` (opcional): Descripción para el asset
- `username` (opcional): Usuario para autenticación
- `password` (opcional): Contraseña para autenticación
- `bbox` (opcional): Bounding box (minx,miny,maxx,maxy)
- `crs` (opcional): Sistema de coordenadas (default: "EPSG:4326")
- `maxFeatures` (opcional): Número máximo de features
- `filter` (opcional): Expresión de filtro CQL u OGC

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver download_layer \
  --json '{
    "base_url": "http://localhost:8080/geoserver",
    "layer_name": "topp:states",
    "output_format": "geojson",
    "title": "US States",
    "description": "United States state boundaries",
    "maxFeatures": 50
  }'
```

### 4. `batch_download`

Descarga múltiples layers de un geoserver.

**Parámetros:**
- `base_url` (requerido): URL base del geoserver
- `layer_names` (requerido): Lista de nombres de layers
- `output_format` (opcional): Formato de salida (default: "geojson")
- `server_type` (opcional): Tipo de servidor (default: "geoserver")
- `service` (opcional): Tipo de servicio OGC (default: "WFS")
- `username` (opcional): Usuario para autenticación
- `password` (opcional): Contraseña para autenticación
- `maxFeatures` (opcional): Número máximo de features por layer

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver batch_download \
  --json '{
    "base_url": "http://localhost:8080/geoserver",
    "layer_names": ["topp:states", "topp:tasmania_roads"],
    "output_format": "geojson",
    "maxFeatures": 100
  }'
```

### 5. `test_connection`

Prueba la conexión con un geoserver.

**Parámetros:**
- `base_url` (requerido): URL base del geoserver
- `server_type` (opcional): Tipo de servidor (default: "geoserver")
- `username` (opcional): Usuario para autenticación
- `password` (opcional): Contraseña para autenticación

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver test_connection \
  --json '{"base_url": "https://demo.geo-solutions.it/geoserver"}'
```

### 6. `get_server_info`

Obtiene información sobre los tipos de servidores y formatos soportados.

**Parámetros:** Ninguno

**Ejemplo:**
```bash
python -m src.adapters.cli.dm_cli plugin execute geoserver get_server_info
```

## Uso a través de la API REST

### Listar información del plugin
```http
GET /plugins/data-fetchers/geoserver
```

### Ejecutar método
```http
POST /plugins/data-fetchers/geoserver/download_layer
Content-Type: application/json

{
  "base_url": "http://localhost:8080/geoserver",
  "layer_name": "topp:states",
  "output_format": "geojson",
  "title": "US States",
  "maxFeatures": 50
}
```

## Ejemplos de Uso

### Ejemplo 1: GeoServer Básico

```python
from plugins.geoserver_plugin import GeoServerPlugin

plugin = GeoServerPlugin()

# Probar conexión
result = plugin.execute_method("test_connection", 
                              base_url="http://localhost:8080/geoserver")

# Listar layers
result = plugin.execute_method("list_layers",
                              base_url="http://localhost:8080/geoserver",
                              service="WFS")

# Descargar layer
result = plugin.execute_method("download_layer",
                              base_url="http://localhost:8080/geoserver",
                              layer_name="topp:states",
                              output_format="geojson")
```

### Ejemplo 2: Con Autenticación

```python
result = plugin.execute_method("download_layer",
                              base_url="https://secure.geoserver.com",
                              layer_name="my:layer",
                              username="user",
                              password="pass",
                              output_format="shapefile")
```

### Ejemplo 3: Con Filtros Espaciales

```python
result = plugin.execute_method("download_layer",
                              base_url="http://localhost:8080/geoserver",
                              layer_name="topp:states",
                              bbox="-124,32,-114,42",  # California area
                              crs="EPSG:4326",
                              maxFeatures=10,
                              output_format="geojson")
```

### Ejemplo 4: MapServer

```python
result = plugin.execute_method("get_capabilities",
                              base_url="https://demo.mapserver.org/cgi-bin/mapserv",
                              server_type="mapserver",
                              service="WMS")
```

### Ejemplo 5: ArcGIS Server

```python
result = plugin.execute_method("get_capabilities",
                              base_url="https://services.arcgis.com/...",
                              server_type="arcgis")
```

## Configuración de Servidores

### GeoServer Local con Docker

```bash
# Ejecutar GeoServer con Docker
docker run -d -p 8080:8080 kartoza/geoserver:2.18.0

# Acceder a http://localhost:8080/geoserver
# Usuario: admin, Contraseña: geoserver
```

### MapServer Local

```bash
# Instalar MapServer
sudo apt-get install mapserver-bin

# Configurar mapfile y ejecutar
mapserv -nh QUERY_STRING="map=/path/to/mapfile.map&SERVICE=WMS&REQUEST=GetCapabilities"
```

## Manejo de Errores

El plugin maneja varios tipos de errores:

1. **Errores de Conexión**: Servidor no disponible
2. **Errores de Autenticación**: Credenciales incorrectas
3. **Errores de Formato**: Formato no soportado
4. **Errores de Layer**: Layer no encontrado
5. **Errores de Servicio**: Servicio OGC no disponible

Todos los errores se devuelven en un formato consistente:

```json
{
  "success": false,
  "error": "Descripción del error",
  "method": "nombre_del_metodo"
}
```

## Assets Generados

Cada descarga exitosa genera automáticamente:

1. **Asset en el catálogo local** con metadatos
2. **Diccionario de datos** con información de variables
3. **Archivo de datos** en el formato solicitado
4. **Información espacial** (bbox, CRS, etc.)

## Limitaciones

1. **Formatos WCS**: Limitado a formatos básicos (TIFF, NetCDF)
2. **Filtros complejos**: Dependiente del soporte del servidor
3. **Grandes datasets**: Considerar usar `maxFeatures` para evitar timeouts
4. **Autenticación**: Soporta básica y token, no OAuth2 completo

## Contribuir

Para añadir soporte para nuevos tipos de servidores:

1. Añadir configuración en `GEOSERVER_TYPES`
2. Implementar métodos específicos en `GeoServerConnector`
3. Añadir tests y ejemplos
4. Actualizar documentación
