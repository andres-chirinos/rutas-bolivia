"""
Plugin de Wikidata que implementa la interfaz IDataFetcherPlugin.

Este plugin proporciona una abstracción completa para ejecutar queries SPARQL
en Wikidata y manejar los resultados como assets del datamesh.
"""
import sys
import os
from typing import Dict, Any, Optional

# Add the project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.ports.data_fetcher_ports import IDataFetcherPlugin
from .wikidata_general import (
    WikidataQueryExecutor, 
    fetch_wikidata_query, 
    fetch_common_query,
    COMMON_QUERIES
)


class WikidataPlugin(IDataFetcherPlugin):
    """Plugin de Wikidata que implementa la interfaz estándar de data fetching."""
    
    NAME = "wikidata"
    
    def __init__(self):
        self.executor = WikidataQueryExecutor()
    
    def get_available_methods(self) -> Dict[str, Dict[str, Any]]:
        """Retorna todos los métodos disponibles del plugin de Wikidata."""
        methods = {
            "execute_query": {
                "description": "Execute a custom SPARQL query on Wikidata",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "SPARQL query to execute",
                        "required": True
                    },
                    "title": {
                        "type": "string", 
                        "description": "Title for the resulting asset",
                        "required": True
                    },
                    "description": {
                        "type": "string",
                        "description": "Description for the dataset",
                        "required": False,
                        "default": ""
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format: geojson, json, or csv",
                        "required": False,
                        "default": "geojson"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results",
                        "required": False,
                        "default": 500
                    }
                },
                "returns": "Asset with SPARQL query results and data dictionary"
            },
            
            "execute_common_query": {
                "description": "Execute a predefined common query",
                "parameters": {
                    "query_name": {
                        "type": "string",
                        "description": f"Name of predefined query. Available: {', '.join(COMMON_QUERIES.keys())}",
                        "required": True
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results",
                        "required": False,
                        "default": 500
                    }
                },
                "returns": "Asset with predefined query results"
            },
            
            "list_common_queries": {
                "description": "List all available predefined queries",
                "parameters": {},
                "returns": "Dictionary of available predefined queries with descriptions"
            },
            
            "museums_bolivia": {
                "description": "Get museums in Bolivia (legacy compatibility method)",
                "parameters": {
                    "output_geojson": {
                        "type": "string",
                        "description": "Path to output GeoJSON file",
                        "required": False,
                        "default": None
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results",
                        "required": False,
                        "default": 500
                    }
                },
                "returns": "Path to generated GeoJSON file or asset information"
            }
        }
        
        # Add dynamic methods for each common query
        for query_name, query_info in COMMON_QUERIES.items():
            methods[f"get_{query_name}"] = {
                "description": f"Get {query_info['title']} - {query_info['description']}",
                "parameters": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results", 
                        "required": False,
                        "default": 500
                    }
                },
                "returns": f"Asset with {query_info['title']} data"
            }
        
        return methods
    
    def execute_method(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """Ejecuta un método específico del plugin."""
        
        # Validar parámetros
        validation = self.validate_method_parameters(method_name, **kwargs)
        if not validation["valid"]:
            return {
                "success": False,
                "error": "Parameter validation failed",
                "errors": validation["errors"]
            }
        
        # Usar parámetros sanitizados
        params = validation["sanitized_params"]
        
        try:
            if method_name == "execute_query":
                result = self._execute_custom_query(**params)
                
            elif method_name == "execute_common_query":
                result = self._execute_common_query(**params)
                
            elif method_name == "list_common_queries":
                result = self._list_common_queries()
                
            elif method_name == "museums_bolivia":
                result = self._museums_bolivia_legacy(**params)
                
            elif method_name.startswith("get_") and method_name[4:] in COMMON_QUERIES:
                # Dynamic methods for common queries
                query_name = method_name[4:]
                result = self._execute_common_query(query_name=query_name, **params)
                
            else:
                return {
                    "success": False,
                    "error": f"Unknown method '{method_name}'"
                }
            
            return {
                "success": True,
                "method": method_name,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "method": method_name
            }
    
    def _execute_custom_query(self, query: str, title: str, description: str = "", 
                            output_format: str = "geojson", limit: int = 500) -> Dict[str, Any]:
        """Ejecuta una query SPARQL personalizada."""
        return fetch_wikidata_query(
            query=query,
            title=title,
            description=description,
            output_format=output_format,
            limit=limit
        )
    
    def _execute_common_query(self, query_name: str, limit: int = 500) -> Dict[str, Any]:
        """Ejecuta una query predefinida."""
        return fetch_common_query(query_name, limit=limit)
    
    def _list_common_queries(self) -> Dict[str, Any]:
        """Lista todas las queries predefinidas disponibles."""
        return {
            "available_queries": COMMON_QUERIES,
            "total_queries": len(COMMON_QUERIES)
        }
    
    def _museums_bolivia_legacy(self, output_geojson: Optional[str] = None, 
                              limit: int = 500) -> Dict[str, Any]:
        """Método de compatibilidad para la función original."""
        from .wikidata_general import fetch_museums_bolivia_generalized
        
        result_path = fetch_museums_bolivia_generalized(output_geojson, limit)
        
        return {
            "output_path": result_path,
            "legacy_mode": True
        }


# Create a global instance for easy access
wikidata_plugin = WikidataPlugin()
