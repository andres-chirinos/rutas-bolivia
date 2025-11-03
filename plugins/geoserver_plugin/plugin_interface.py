"""
Plugin de GeoServer que implementa la interfaz IDataFetcherPlugin.

Este plugin proporciona una abstracción completa para conectar con diferentes
tipos de geoservers y obtener layers en diversos formatos.
"""
import sys
import os
from typing import Dict, Any, Optional

# Add the project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.ports.data_fetcher_ports import IDataFetcherPlugin
from .geoserver_utils import (
    GeoServerConnector, 
    GEOSERVER_TYPES, 
    OUTPUT_FORMATS,
    create_asset_from_layer,
    register_geoserver_service,
    register_layer_as_dataset,
    register_distribution_from_download,
    register_interesting_source,
    get_catalog_summary
)


class GeoServerPlugin(IDataFetcherPlugin):
    """Plugin de GeoServer que implementa la interfaz estándar de data fetching."""
    
    NAME = "geoserver"
    
    def __init__(self):
        self.connectors = {}  # Cache de conectores por URL
    
    def get_available_methods(self) -> Dict[str, Dict[str, Any]]:
        """Retorna todos los métodos disponibles del plugin de GeoServer."""
        
        # Lista de tipos de geoserver soportados
        server_types = list(GEOSERVER_TYPES.keys())
        output_formats = list(OUTPUT_FORMATS.keys())
        
        methods = {
            "get_capabilities": {
                "description": "Get capabilities from a geoserver (WMS, WFS, WCS services)",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver. Supported: {', '.join(server_types)}",
                        "required": False,
                        "default": "geoserver"
                    },
                    "service": {
                        "type": "string",
                        "description": "OGC service type (WMS, WFS, WCS)",
                        "required": False,
                        "default": "WMS"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    },
                    "token": {
                        "type": "string",
                        "description": "Authentication token (for ArcGIS)",
                        "required": False
                    }
                },
                "returns": "Capabilities information including available layers/services"
            },
            
            "list_layers": {
                "description": "List all available layers from a geoserver",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver. Supported: {', '.join(server_types)}",
                        "required": False,
                        "default": "geoserver"
                    },
                    "service": {
                        "type": "string",
                        "description": "OGC service type (WMS, WFS, WCS)",
                        "required": False,
                        "default": "WFS"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    }
                },
                "returns": "List of available layers with metadata"
            },
            
            "download_layer": {
                "description": "Download a specific layer from a geoserver",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer to download",
                        "required": True
                    },
                    "output_format": {
                        "type": "string",
                        "description": f"Output format. Supported: {', '.join(output_formats)}",
                        "required": False,
                        "default": "geojson"
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver. Supported: {', '.join(server_types)}",
                        "required": False,
                        "default": "geoserver"
                    },
                    "service": {
                        "type": "string",
                        "description": "OGC service type (WFS, WMS, WCS)",
                        "required": False,
                        "default": "WFS"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title for the resulting asset",
                        "required": False
                    },
                    "description": {
                        "type": "string",
                        "description": "Description for the resulting asset",
                        "required": False
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    },
                    "token": {
                        "type": "string",
                        "description": "Authentication token (for ArcGIS)",
                        "required": False
                    },
                    "bbox": {
                        "type": "string",
                        "description": "Bounding box (minx,miny,maxx,maxy)",
                        "required": False
                    },
                    "crs": {
                        "type": "string",
                        "description": "Coordinate reference system (e.g., EPSG:4326)",
                        "required": False,
                        "default": "EPSG:4326"
                    },
                    "maxFeatures": {
                        "type": "number",
                        "description": "Maximum number of features to download",
                        "required": False
                    },
                    "filter": {
                        "type": "string",
                        "description": "CQL or OGC filter expression",
                        "required": False
                    }
                },
                "returns": "Asset with downloaded layer data and metadata"
            },
            
            "batch_download": {
                "description": "Download multiple layers from a geoserver",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "layer_names": {
                        "type": "object",
                        "description": "List of layer names to download",
                        "required": True
                    },
                    "output_format": {
                        "type": "string",
                        "description": f"Output format. Supported: {', '.join(output_formats)}",
                        "required": False,
                        "default": "geojson"
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver. Supported: {', '.join(server_types)}",
                        "required": False,
                        "default": "geoserver"
                    },
                    "service": {
                        "type": "string",
                        "description": "OGC service type (WFS, WMS, WCS)",
                        "required": False,
                        "default": "WFS"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    },
                    "maxFeatures": {
                        "type": "number",
                        "description": "Maximum number of features per layer",
                        "required": False
                    }
                },
                "returns": "List of assets with downloaded layer data"
            },
            
            "get_server_info": {
                "description": "Get information about supported geoserver types and formats",
                "parameters": {},
                "returns": "Information about supported geoserver types and output formats"
            },
            
            "test_connection": {
                "description": "Test connection to a geoserver",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver. Supported: {', '.join(server_types)}",
                        "required": False,
                        "default": "geoserver"
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    }
                },
                "returns": "Connection test results and basic server information"
            },
            
            "register_service": {
                "description": "Register a geoserver as a data service in DCAT catalog",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver ({', '.join(server_types)})",
                        "required": False,
                        "default": "geoserver",
                        "options": server_types
                    },
                    "service_name": {
                        "type": "string",
                        "description": "Custom name for the service",
                        "required": False
                    },
                    "description": {
                        "type": "string",
                        "description": "Custom description for the service",
                        "required": False
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    }
                },
                "returns": "Service ID in DCAT catalog"
            },
            
            "register_layer_dataset": {
                "description": "Register a layer as a dataset in DCAT catalog",
                "parameters": {
                    "base_url": {
                        "type": "string",
                        "description": "Base URL of the geoserver",
                        "required": True
                    },
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer to register",
                        "required": True
                    },
                    "server_type": {
                        "type": "string",
                        "description": f"Type of geoserver ({', '.join(server_types)})",
                        "required": False,
                        "default": "geoserver",
                        "options": server_types
                    },
                    "service_id": {
                        "type": "string",
                        "description": "ID of the service that contains this dataset",
                        "required": False
                    },
                    "username": {
                        "type": "string",
                        "description": "Username for authentication",
                        "required": False
                    },
                    "password": {
                        "type": "string",
                        "description": "Password for authentication",
                        "required": False
                    }
                },
                "returns": "Dataset ID in DCAT catalog"
            },
            
            "register_source": {
                "description": "Register an interesting data source for tracking",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "URL of the data source",
                        "required": True
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the source",
                        "required": True
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the source",
                        "required": False
                    },
                    "source_type": {
                        "type": "string",
                        "description": "Type of source",
                        "required": False,
                        "default": "geoserver"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category of the source",
                        "required": False,
                        "default": "geospatial"
                    },
                    "tags": {
                        "type": "array",
                        "description": "Tags associated with the source",
                        "required": False
                    }
                },
                "returns": "Source ID in catalog"
            },
            
            "get_catalog_summary": {
                "description": "Get a summary of the current DCAT catalog state",
                "parameters": {},
                "returns": "Summary with statistics and counts"
            }
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
            if method_name == "get_capabilities":
                result = self._get_capabilities(**params)
                
            elif method_name == "list_layers":
                result = self._list_layers(**params)
                
            elif method_name == "download_layer":
                result = self._download_layer(**params)
                
            elif method_name == "batch_download":
                result = self._batch_download(**params)
                
            elif method_name == "get_server_info":
                result = self._get_server_info()
                
            elif method_name == "test_connection":
                result = self._test_connection(**params)
                
            elif method_name == "register_service":
                result = self._register_service(**params)
                
            elif method_name == "register_layer_dataset":
                result = self._register_layer_dataset(**params)
                
            elif method_name == "register_source":
                result = self._register_source(**params)
                
            elif method_name == "get_catalog_summary":
                result = self._get_catalog_summary(**params)
                
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
    
    def _get_connector(self, base_url: str, server_type: str = "geoserver", 
                      username: str = None, password: str = None, 
                      token: str = None) -> GeoServerConnector:
        """Obtiene o crea un conector para el geoserver."""
        # Crear clave única para el conector
        auth_key = f"{username}:{password}" if username and password else token or "no_auth"
        connector_key = f"{base_url}_{server_type}_{auth_key}"
        
        if connector_key not in self.connectors:
            self.connectors[connector_key] = GeoServerConnector(
                base_url=base_url,
                server_type=server_type,
                username=username,
                password=password,
                token=token
            )
        
        return self.connectors[connector_key]
    
    def _get_capabilities(self, base_url: str, server_type: str = "geoserver",
                         service: str = "WMS", username: str = None, 
                         password: str = None, token: str = None) -> Dict[str, Any]:
        """Obtiene las capacidades del geoserver."""
        connector = self._get_connector(base_url, server_type, username, password, token)
        return connector.get_capabilities(service)
    
    def _list_layers(self, base_url: str, server_type: str = "geoserver",
                    service: str = "WFS", username: str = None, 
                    password: str = None) -> Dict[str, Any]:
        """Lista los layers disponibles."""
        connector = self._get_connector(base_url, server_type, username, password)
        
        # Usar el nuevo método list_layers del conector
        result = connector.list_layers()
        
        if "error" in result:
            return result
        
        return result
    
    def _download_layer(self, base_url: str, layer_name: str, 
                       output_format: str = "geojson", server_type: str = "geoserver",
                       service: str = "WFS", title: str = None, 
                       description: str = None, username: str = None,
                       password: str = None, token: str = None, 
                       dataset_id: str = None, **kwargs) -> Dict[str, Any]:
        """Descarga un layer específico y registra la distribución en DCAT."""
        connector = self._get_connector(base_url, server_type, username, password, token)
        
        # Descargar layer
        file_path = connector.download_layer(
            layer_name=layer_name,
            output_format=output_format,
            service=service,
            **kwargs
        )
        
        # Crear información del layer para DCAT
        layer_data = {
            "layer_name": layer_name,
            "title": title or layer_name,
            "description": description or f"Layer {layer_name} from {server_type}",
            "server_type": server_type,
            "service": service,
            "source": base_url,
            "source_url": f"{base_url}/layer/{layer_name}",
            "format": output_format.upper(),
            "download_params": kwargs,
            "bbox": kwargs.get("bbox", {}),
            "crs": kwargs.get("crs", "EPSG:4326")
        }
        
        # Registrar en catálogo DCAT como distribución
        try:
            distribution_id = register_distribution_from_download(layer_data, file_path, dataset_id)
            dcat_info = {"distribution_id": distribution_id} if distribution_id else {}
        except Exception as e:
            print(f"Warning: Could not register in DCAT catalog: {e}")
            # Fallback al método original
            asset = create_asset_from_layer({
                "name": layer_name,
                "title": title or layer_name,
                "abstract": description or f"Layer {layer_name} from {server_type}",
                "server_type": server_type,
                "service": service,
                "base_url": base_url,
                "output_format": output_format
            }, file_path)
            dcat_info = {"legacy_asset": asset}
        
        return {
            "file_path": file_path,
            "layer_name": layer_name,
            "output_format": output_format,
            "download_info": {
                "base_url": base_url,
                "server_type": server_type,
                "service": service
            },
            "dcat_info": dcat_info
        }
    
    def _batch_download(self, base_url: str, layer_names: list, 
                       output_format: str = "geojson", server_type: str = "geoserver",
                       service: str = "WFS", username: str = None,
                       password: str = None, **kwargs) -> Dict[str, Any]:
        """Descarga múltiples layers."""
        connector = self._get_connector(base_url, server_type, username, password)
        
        results = []
        errors = []
        
        for layer_name in layer_names:
            try:
                # Descargar layer
                file_path = connector.download_layer(
                    layer_name=layer_name,
                    output_format=output_format,
                    service=service,
                    **kwargs
                )
                
                # Crear información del layer
                layer_data = {
                    "name": layer_name,
                    "title": layer_name,
                    "abstract": f"Layer {layer_name} from {server_type}",
                    "server_type": server_type,
                    "service": service,
                    "base_url": base_url,
                    "output_format": output_format
                }
                
                # Crear asset
                asset = create_asset_from_layer(layer_data, file_path)
                
                results.append({
                    "layer_name": layer_name,
                    "asset": asset,
                    "file_path": file_path,
                    "success": True
                })
                
            except Exception as e:
                errors.append({
                    "layer_name": layer_name,
                    "error": str(e),
                    "success": False
                })
        
        return {
            "results": results,
            "errors": errors,
            "total_requested": len(layer_names),
            "successful_downloads": len(results),
            "failed_downloads": len(errors),
            "download_info": {
                "base_url": base_url,
                "server_type": server_type,
                "service": service,
                "output_format": output_format
            }
        }
    
    def _get_server_info(self) -> Dict[str, Any]:
        """Retorna información sobre tipos de geoserver y formatos soportados."""
        return {
            "supported_servers": GEOSERVER_TYPES,
            "supported_formats": OUTPUT_FORMATS,
            "services": ["WMS", "WFS", "WCS"],
            "plugin_version": "1.0.0",
            "description": "Plugin for downloading layers from various geoserver types"
        }
    
    def _test_connection(self, base_url: str, server_type: str = "geoserver",
                        username: str = None, password: str = None) -> Dict[str, Any]:
        """Prueba la conexión con el geoserver."""
        try:
            connector = self._get_connector(base_url, server_type, username, password)
            
            # Intentar obtener capacidades WMS como test básico
            capabilities = connector.get_capabilities("WMS")
            
            if "error" in capabilities:
                return {
                    "connection_status": "failed",
                    "error": capabilities["error"],
                    "base_url": base_url,
                    "server_type": server_type
                }
            
            # Contar layers disponibles
            layer_count = len(capabilities.get("layers", []))
            
            return {
                "connection_status": "success",
                "base_url": base_url,
                "server_type": server_type,
                "server_info": capabilities.get("server_config", {}),
                "available_layers": layer_count,
                "services_tested": ["WMS"],
                "capabilities_url": capabilities.get("capabilities_url")
            }
            
        except Exception as e:
            return {
                "connection_status": "failed",
                "error": str(e),
                "base_url": base_url,
                "server_type": server_type
            }
    
    def _register_service(self, base_url: str, server_type: str = "geoserver",
                         service_name: str = None, description: str = None,
                         username: str = None, password: str = None) -> Dict[str, Any]:
        """Registra un geoserver como servicio de datos en el catálogo DCAT."""
        try:
            connector = self._get_connector(base_url, server_type, username, password)
            service_id = register_geoserver_service(connector, service_name, description)
            
            if service_id:
                return {
                    "service_id": service_id,
                    "message": f"Service registered successfully in DCAT catalog",
                    "base_url": base_url,
                    "server_type": server_type
                }
            else:
                return {
                    "error": "Failed to register service - DCAT catalog not available",
                    "base_url": base_url,
                    "server_type": server_type
                }
                
        except Exception as e:
            return {
                "error": f"Failed to register service: {e}",
                "base_url": base_url,
                "server_type": server_type
            }
    
    def _register_layer_dataset(self, base_url: str, layer_name: str,
                              server_type: str = "geoserver", service_id: str = None,
                              username: str = None, password: str = None) -> Dict[str, Any]:
        """Registra un layer como dataset en el catálogo DCAT."""
        try:
            connector = self._get_connector(base_url, server_type, username, password)
            dataset_id = register_layer_as_dataset(connector, layer_name, service_id)
            
            if dataset_id:
                return {
                    "dataset_id": dataset_id,
                    "message": f"Layer '{layer_name}' registered successfully as dataset in DCAT catalog",
                    "layer_name": layer_name,
                    "base_url": base_url,
                    "server_type": server_type
                }
            else:
                return {
                    "error": "Failed to register dataset - DCAT catalog not available",
                    "layer_name": layer_name,
                    "base_url": base_url,
                    "server_type": server_type
                }
                
        except Exception as e:
            return {
                "error": f"Failed to register dataset: {e}",
                "layer_name": layer_name,
                "base_url": base_url,
                "server_type": server_type
            }
    
    def _register_source(self, url: str, name: str, description: str = "",
                        source_type: str = "geoserver", category: str = "geospatial",
                        tags: list = None) -> Dict[str, Any]:
        """Registra una fuente de datos interesante para seguimiento."""
        try:
            source_id = register_interesting_source(url, name, description, source_type, category, tags)
            
            if source_id:
                return {
                    "source_id": source_id,
                    "message": f"Source '{name}' registered successfully for tracking",
                    "name": name,
                    "url": url,
                    "category": category
                }
            else:
                return {
                    "error": "Failed to register source - DCAT catalog not available",
                    "name": name,
                    "url": url
                }
                
        except Exception as e:
            return {
                "error": f"Failed to register source: {e}",
                "name": name,
                "url": url
            }
    
    def _get_catalog_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del estado actual del catálogo DCAT."""
        try:
            summary = get_catalog_summary()
            return summary
                
        except Exception as e:
            return {
                "error": f"Failed to get catalog summary: {e}"
            }


# Create a global instance for easy access
geoserver_plugin = GeoServerPlugin()
