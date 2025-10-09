# 🌍 Sistema de Inventario de GeoServers

Este directorio contiene un sistema completo para gestionar catálogos de geoservers conocidos y generar inventarios CSV de todas las layers disponibles.

## 📁 Archivos Incluidos

### 📋 Catálogo Principal
- **`geoservers_catalog.json`** - Catálogo con 10+ geoservers conocidos organizados por categoría

### 🔧 Scripts Principales  
- **`generate_layers_inventory.py`** - Script principal para generar inventario CSV
- **`manage_catalog.py`** - Herramienta para gestionar el catálogo de geoservers
- **`run_inventory.sh`** - Script bash para ejecución rápida

### 📄 Documentación
- **`README.md`** - Esta documentación
- **`examples/`** - Ejemplos de uso y configuración

## 🚀 Uso Rápido

### 1. Generar Inventario Completo

```bash
# Método más simple
./run_inventory.sh

# O manualmente
python generate_layers_inventory.py geoservers_catalog.json
```

### 2. Filtrar por Categorías

```bash
# Solo servidores gubernamentales
python generate_layers_inventory.py geoservers_catalog.json -c government

# Solo demos y académicos
python generate_layers_inventory.py geoservers_catalog.json -c demo academic
```

### 3. Filtrar por País

```bash
# Solo servidores de Estados Unidos
python generate_layers_inventory.py geoservers_catalog.json --countries "Estados Unidos"

# Múltiples países
python generate_layers_inventory.py geoservers_catalog.json --countries "España" "Argentina"
```

### 4. Configuración Avanzada

```bash
# Procesar solo 3 servidores, sin test de conexión, salida personalizada
python generate_layers_inventory.py geoservers_catalog.json \
    --max-servers 3 \
    --no-test \
    -o mi_inventario_custom.csv
```

## 🗂️ Gestión del Catálogo

### Listar Servidores Actuales

```bash
python manage_catalog.py geoservers_catalog.json list
```

### Añadir Servidor Interactivo

```bash
python manage_catalog.py geoservers_catalog.json add
```

### Añadir Servidor desde Línea de Comandos

```bash
python manage_catalog.py geoservers_catalog.json add-direct \
    "Mi Servidor GIS" \
    "https://mi-servidor.com/geoserver" \
    --category government \
    --country "Mi País" \
    --organization "Mi Organización"
```

## 📊 Estructura del CSV Generado

El CSV resultante incluye las siguientes columnas:

### 🔧 Información del Servidor
- `server_name` - Nombre del servidor
- `server_url` - URL base
- `server_type` - Tipo (geoserver, arcgis, mapserver)
- `server_category` - Categoría (demo, government, academic, etc.)
- `server_country` - País
- `server_organization` - Organización

### 📋 Información del Layer
- `layer_name` - Nombre técnico del layer
- `layer_title` - Título descriptivo
- `layer_abstract` - Descripción/resumen
- `layer_service` - Servicio principal (WMS, WFS, WCS)
- `layer_services` - Todos los servicios disponibles

### 🗺️ Información Espacial
- `bbox_minx`, `bbox_miny`, `bbox_maxx`, `bbox_maxy` - Bounding box
- `crs` - Sistema de coordenadas

### 🔗 URLs de Acceso
- `wms_url` - URL directa para WMS
- `wfs_url` - URL directa para WFS

### 📝 Metadatos Adicionales
- `keywords` - Palabras clave
- `last_modified` - Última modificación
- `feature_count` - Número de features (si disponible)
- `inventory_date` - Fecha del inventario
- `accessible` - Estado de accesibilidad
- `notes` - Notas adicionales

## 🏷️ Categorías de Servidores

### 🎯 **demo**
Servidores de demostración y pruebas
- Ideal para: Testing, aprendizaje, ejemplos
- Ejemplos: GeoServer.org Demo, Ahocevar Demo

### 🏛️ **government**  
Servidores gubernamentales oficiales
- Ideal para: Datos oficiales, cartografía base
- Ejemplos: IGN España, IGN Argentina, USGS

### 🎓 **academic**
Servidores de instituciones académicas
- Ideal para: Datos de investigación, estudios
- Ejemplos: Princeton, Harvard, universidades

### 💼 **commercial**
Servidores de empresas comerciales
- Ideal para: Datos especializados, servicios premium
- Ejemplos: Esri, Google, proveedores comerciales

### 🌐 **international**
Organizaciones internacionales
- Ideal para: Datos globales, estadísticas mundiales
- Ejemplos: World Bank, UN, organizaciones multilaterales

## 📈 Casos de Uso

### 1. 🔍 **Descubrimiento de Datos**
```bash
# Inventario completo para ver qué datos están disponibles
python generate_layers_inventory.py geoservers_catalog.json
```

### 2. 🎯 **Datos Gubernamentales**
```bash
# Solo datos oficiales
python generate_layers_inventory.py geoservers_catalog.json -c government
```

### 3. 🌍 **Datos por Región**
```bash
# Solo datos de América Latina
python generate_layers_inventory.py geoservers_catalog.json \
    --countries "Argentina" "España" "México" "Colombia"
```

### 4. 🚀 **Testing Rápido**
```bash
# Solo demos, máximo 2 servidores
python generate_layers_inventory.py geoservers_catalog.json \
    -c demo --max-servers 2
```

### 5. 📊 **Inventario Empresarial**
```bash
# Datos comerciales y académicos
python generate_layers_inventory.py geoservers_catalog.json \
    -c commercial academic \
    -o inventario_empresarial.csv
```

## ⚙️ Opciones Avanzadas

### Filtros Disponibles
- `--categories` / `-c` - Filtrar por categorías
- `--countries` - Filtrar por países  
- `--server-types` - Filtrar por tipos de servidor
- `--max-servers` - Limitar número de servidores
- `--no-test` - No probar conexión (más rápido)

### Salida Personalizada
- `-o` / `--output` - Archivo CSV de salida personalizado
- El archivo incluye timestamp automático si no se especifica

### Control de Rendimiento
- **Test de conexión**: Por defecto habilitado, usar `--no-test` para acelerar
- **Pausa entre servidores**: 1 segundo automático para no sobrecargar
- **Límite de servidores**: Usar `--max-servers` para pruebas rápidas

## 🔧 Personalización del Catálogo

### Estructura del Catálogo JSON

```json
{
  "@context": { ... },
  "@type": "dcat:Catalog",
  "dcterms:title": "Título del catálogo",
  "geoservers": [
    {
      "id": "identificador_unico",
      "name": "Nombre Descriptivo",
      "description": "Descripción del servidor",
      "url": "https://servidor.com/geoserver",
      "type": "geoserver|arcgis|mapserver|qgis",
      "category": "demo|government|academic|commercial|international|other",
      "country": "País",
      "organization": "Organización",
      "status": "active|unknown|unreachable",
      "public": true|false,
      "authentication": {
        "required": false,
        "type": "none|basic|token"
      },
      "notes": "Notas adicionales"
    }
  ]
}
```

### Añadir Nuevos Tipos de Servidor

Para soportar nuevos tipos de servidores, modifica el plugin GeoServer en:
- `plugins/geoserver_plugin/geoserver_utils.py`
- Añade nuevos tipos en `GEOSERVER_TYPES`

### Añadir Nuevas Categorías

Simplemente usa nuevas categorías en el campo `category`. El sistema las reconocerá automáticamente.

## 🛠️ Solución de Problemas

### ❌ Error de Conexión
```
❌ Error de conexión: Connection timeout
```
**Solución**: Verificar URL, usar `--no-test` para omitir test, o marcar servidor como `unreachable`

### ❌ Sin Layers Encontrados
```
📊 Encontrados 0 layers
```
**Solución**: Verificar que el servidor soporte WMS/WFS, comprobar URL correcta

### ❌ Error de Autenticación  
```
❌ Error: 401 Unauthorized
```
**Solución**: Añadir credenciales al catálogo o usar servidor público

### ❌ CSV Vacío
```
⚠️ No se encontraron layers para exportar
```
**Solución**: Verificar filtros aplicados, probar con menos restricciones

## 📚 Ejemplos Adicionales

### Script Automatizado Diario
```bash
#!/bin/bash
# inventario_diario.sh
DATE=$(date +%Y%m%d)
python generate_layers_inventory.py geoservers_catalog.json \
    -o "inventario_diario_$DATE.csv" \
    --max-servers 5
```

### Inventario por Categorías
```bash
# Generar inventarios separados por categoría
for cat in demo government academic; do
    python generate_layers_inventory.py geoservers_catalog.json \
        -c $cat -o "inventario_${cat}.csv"
done
```

### Verificación de Estado
```bash
# Solo test de conexiones, sin generar CSV
python generate_layers_inventory.py geoservers_catalog.json \
    --max-servers 999 --no-test -o /dev/null
```

## 🎯 Próximas Mejoras

- ✅ **Soporte para autenticación** (básica y tokens)
- ✅ **Filtros por metadatos** (palabras clave, fechas)
- ✅ **Exportación a otros formatos** (Excel, JSON)
- ✅ **Verificación automática periódica** de servidores
- ✅ **Integración con DCAT catalog** principal
- ✅ **Cache de resultados** para acelerar inventarios repetidos

## 💡 Contribuciones

Para añadir nuevos geoservers conocidos al catálogo base:

1. Usa `manage_catalog.py add` para añadir interactivamente
2. O edita `geoservers_catalog.json` directamente
3. Crea pull request con nuevos servidores verificados

**Criterios para inclusión:**
- ✅ Servidor público y estable
- ✅ Datos de calidad y bien documentados  
- ✅ Información de contacto y organización clara
- ✅ Categorización apropiada
