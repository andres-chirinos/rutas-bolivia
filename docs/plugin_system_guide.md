# Plugin System - Documentación de Uso

El sistema de plugins del Datamesh Client ahora proporciona una abstracción genérica para cualquier plugin de obtención de datos. Esto permite que los plugins sean expuestos tanto a través del CLI como de la API de manera uniforme.

## Arquitectura

### Puertos (Interfaces)
- `IDataFetcherPlugin`: Interfaz base para plugins que obtienen datos de fuentes externas
- Los plugins implementan métodos estandarizados para descubrimiento y ejecución

### Plugin Manager
- Descubre automáticamente plugins que implementan las interfaces
- Proporciona acceso uniforme a todos los tipos de plugins
- Maneja validación de parámetros y métodos

## Uso a través del CLI

### Listar todos los plugins disponibles
```bash
python -m src.adapters.cli.dm_cli plugin list
```

### Obtener información detallada de un plugin
```bash
python -m src.adapters.cli.dm_cli plugin info wikidata
```

### Ejecutar un método de plugin
```bash
# Método sin parámetros
python -m src.adapters.cli.dm_cli plugin execute wikidata list_common_queries

# Método con parámetros JSON
python -m src.adapters.cli.dm_cli plugin execute wikidata execute_query \
  --json '{"query": "SELECT ?item WHERE { ?item wdt:P31 wd:Q515 . ?item wdt:P17 wd:Q750 } LIMIT 5", "title": "Ciudades Bolivia Test"}'

# Método con parámetros desde archivo
echo '{"query_name": "museums_bolivia", "limit": 10}' > query_params.json
python -m src.adapters.cli.dm_cli plugin execute wikidata execute_common_query --json @query_params.json
```

## Uso a través de la API REST

### Endpoints genéricos para cualquier plugin

#### Listar todos los plugins
```http
GET /plugins
```

#### Listar plugins de data fetching
```http
GET /plugins/data-fetchers
```

#### Información de un plugin específico
```http
GET /plugins/data-fetchers/{plugin_name}
```

#### Información de un método específico
```http
GET /plugins/data-fetchers/{plugin_name}/{method_name}
```

#### Ejecutar un método de plugin
```http
POST /plugins/data-fetchers/{plugin_name}/{method_name}
Content-Type: application/json

{
  "parameter1": "value1",
  "parameter2": "value2"
}
```

### Ejemplos específicos para Wikidata

#### Ejecutar query personalizada
```http
POST /plugins/data-fetchers/wikidata/execute_query
Content-Type: application/json

{
  "query": "SELECT ?item ?itemLabel WHERE { ?item wdt:P31 wd:Q3918 . ?item wdt:P17 wd:Q750 } LIMIT 10",
  "title": "Universidades de Bolivia",
  "description": "Lista de universidades bolivianas",
  "output_format": "geojson",
  "limit": 10
}
```

#### Ejecutar query predefinida
```http
POST /plugins/data-fetchers/wikidata/execute_common_query
Content-Type: application/json

{
  "query_name": "cities_bolivia",
  "limit": 20
}
```

#### Listar queries disponibles
```http
POST /plugins/data-fetchers/wikidata/list_common_queries
Content-Type: application/json

{}
```

### Endpoints legacy (retrocompatibilidad)
Los endpoints específicos de Wikidata siguen funcionando:
- `POST /wikidata/query`
- `GET /wikidata/common/{query_name}` 
- `GET /wikidata/queries`

## Creación de nuevos plugins

Para crear un nuevo plugin de data fetching:

1. **Implementar la interfaz `IDataFetcherPlugin`**:
```python
from src.core.ports.data_fetcher_ports import IDataFetcherPlugin

class MiPlugin(IDataFetcherPlugin):
    NAME = "mi_plugin"
    
    def get_available_methods(self):
        return {
            "mi_metodo": {
                "description": "Descripción del método",
                "parameters": {
                    "param1": {
                        "type": "string",
                        "description": "Primer parámetro",
                        "required": True
                    }
                },
                "returns": "Descripción del retorno"
            }
        }
    
    def execute_method(self, method_name, **kwargs):
        if method_name == "mi_metodo":
            # Lógica del método
            return {"success": True, "result": {...}}
```

2. **Crear el archivo `__init__.py` del plugin**:
```python
from .mi_plugin import MiPlugin
__all__ = ['MiPlugin']
```

3. **El plugin será descubierto automáticamente** por el PluginManager.

## Assets y Diccionarios de Datos

Los plugins de data fetching automáticamente:
- Crean assets en el catálogo local
- Generan diccionarios de datos con metadata de las variables
- Manejan firma digital y provenance
- Exponen los datos a través del sistema de assets

### Estructura de un asset creado:
```json
{
  "id": "plugin_generated_id",
  "title": "Título del dataset",
  "description": "Descripción",
  "source": "nombre_del_plugin",
  "results_count": 150,
  "data_uri": "tmp/data_file.json",
  "data_dictionary_uri": "tmp/dictionary_file.json",
  "descriptor_uri": "descriptors/uuid.jsonld"
}
```

### Diccionario de datos:
```json
{
  "source": "nombre_plugin",
  "generated_at": "2025-09-30T...",
  "variables": {
    "variable1": {
      "name": "variable1",
      "description": "Descripción de la variable",
      "data_types": ["uri", "literal"],
      "sample_values": ["valor1", "valor2"],
      "is_uri": true,
      "null_count": 0,
      "total_count": 150
    }
  },
  "total_results": 150
}
```

## Ventajas del sistema genérico

1. **Consistencia**: Todos los plugins siguen la misma interfaz
2. **Autodocumentación**: Los plugins describen sus propios métodos y parámetros
3. **Validación automática**: Parámetros validados antes de la ejecución
4. **Extensibilidad**: Fácil agregar nuevos plugins sin modificar APIs
5. **Retrocompatibilidad**: Endpoints legacy siguen funcionando
6. **Assets automáticos**: Todos los datos se convierten en assets rastreables

Este diseño permite que cualquier plugin (Wikidata, APIs externas, bases de datos, etc.) sea utilizado de manera uniforme tanto desde el CLI como desde la API REST.
