"""
Utilidades para trabajar con diferentes tipos de geoservers y servicios OGC.

Este módulo proporciona funciones para:
- Conectar con diferentes tipos de geoservers
- Obtener capabilidades de servicios WMS, WFS, WCS
- Descargar layers en diferentes formatos
- Manejar autenticación básica y por tokens
- Integrar servicios en catálogo DCAT
"""
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
import requests
from xml.etree import ElementTree as ET
import csv

# Importar el gestor de catálogo DCAT
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
try:
    from core.services.dcat_catalog import get_catalog_manager
except ImportError:
    # Fallback si no está disponible
    def get_catalog_manager(*args, **kwargs):
        return None


# Configuración de tipos de geoserver soportados
GEOSERVER_TYPES = {
    "geoserver": {
        "name": "GeoServer",
        "description": "Open source server for sharing geospatial data",
        "capabilities_path": "/wms?service=WMS&version=1.3.0&request=GetCapabilities",
        "wfs_path": "/wfs?service=WFS&version=2.0.0&request=GetCapabilities",
        "wcs_path": "/wcs?service=WCS&version=2.0.1&request=GetCapabilities"
    },
    "mapserver": {
        "name": "MapServer",
        "description": "Platform for publishing spatial data and interactive mapping applications",
        "capabilities_path": "?service=WMS&version=1.3.0&request=GetCapabilities",
        "wfs_path": "?service=WFS&version=2.0.0&request=GetCapabilities",
        "wcs_path": "?service=WCS&version=2.0.1&request=GetCapabilities"
    },
    "arcgis": {
        "name": "ArcGIS Server",
        "description": "Esri's server software for sharing geospatial services",
        "rest_endpoint": "/rest/services",
        "capabilities_path": "/MapServer?f=json"
    },
    "qgis": {
        "name": "QGIS Server",
        "description": "QGIS Server provides a web service using the same libraries as the QGIS desktop",
        "capabilities_path": "?service=WMS&version=1.3.0&request=GetCapabilities",
        "wfs_path": "?service=WFS&version=2.0.0&request=GetCapabilities"
    }
}

# Formatos de salida soportados
OUTPUT_FORMATS = {
    "geojson": {
        "mime_type": "application/json",
        "extension": ".geojson",
        "service": "WFS",
        "format_param": "outputFormat=application/json"
    },
    "shapefile": {
        "mime_type": "application/zip",
        "extension": ".zip",
        "service": "WFS",
        "format_param": "outputFormat=SHAPE-ZIP"
    },
    "gml": {
        "mime_type": "application/gml+xml",
        "extension": ".gml",
        "service": "WFS",
        "format_param": "outputFormat=GML3"
    },
    "kml": {
        "mime_type": "application/vnd.google-earth.kml+xml",
        "extension": ".kml",
        "service": "WFS",
        "format_param": "outputFormat=KML"
    },
    "csv": {
        "mime_type": "text/csv",
        "extension": ".csv",
        "service": "WFS",
        "format_param": "outputFormat=csv"
    },
    "json": {
        "mime_type": "application/json",
        "extension": ".json",
        "service": "WFS",
        "format_param": "outputFormat=application/json"
    }
}


class GeoServerConnector:
    """Conector genérico para diferentes tipos de geoservers."""
    
    def __init__(self, base_url: str, server_type: str = "geoserver", 
                 username: str = None, password: str = None, token: str = None):
        """
        Inicializa el conector.
        
        Args:
            base_url: URL base del geoserver
            server_type: Tipo de servidor (geoserver, mapserver, arcgis, qgis)
            username: Usuario para autenticación básica
            password: Contraseña para autenticación básica
            token: Token de autenticación (para ArcGIS)
        """
        self.base_url = base_url.rstrip('/')
        self.server_type = server_type.lower()
        self.username = username
        self.password = password
        self.token = token
        
        # Configurar autenticación
        self.session = requests.Session()
        if username and password:
            self.session.auth = (username, password)
        elif token:
            self.session.headers.update({'Authorization': f'Bearer {token}'})
    
    def get_capabilities(self, service: str = "WMS") -> Dict[str, Any]:
        """
        Obtiene las capacidades del servicio especificado.
        
        Args:
            service: Tipo de servicio (WMS, WFS, WCS)
            
        Returns:
            Dict con información de capabilidades
        """
        try:
            if self.server_type == "arcgis":
                return self._get_arcgis_capabilities()
            else:
                return self._get_ogc_capabilities(service)
        except Exception as e:
            return {"error": f"Failed to get capabilities: {e}"}
    
    def _get_ogc_capabilities(self, service: str) -> Dict[str, Any]:
        """Obtiene capabilidades para servicios OGC estándar."""
        config = GEOSERVER_TYPES.get(self.server_type, GEOSERVER_TYPES["geoserver"])
        
        if service.upper() == "WFS":
            path = config.get("wfs_path", config["capabilities_path"].replace("WMS", "WFS"))
        elif service.upper() == "WCS":
            path = config.get("wcs_path", config["capabilities_path"].replace("WMS", "WCS"))
        else:  # WMS
            path = config["capabilities_path"]
        
        url = self.base_url + path
        
        response = self.session.get(url)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # Extract layers information
        layers = []
        if service.upper() == "WMS":
            layers = self._parse_wms_layers(root)
        elif service.upper() == "WFS":
            layers = self._parse_wfs_layers(root)
        elif service.upper() == "WCS":
            layers = self._parse_wcs_layers(root)
        
        return {
            "service": service.upper(),
            "server_type": self.server_type,
            "server_config": config,
            "layers": layers,
            "total_layers": len(layers),
            "capabilities_url": url
        }
    
    def _get_arcgis_capabilities(self) -> Dict[str, Any]:
        """Obtiene capabilidades para ArcGIS Server."""
        config = GEOSERVER_TYPES["arcgis"]
        url = self.base_url + config["rest_endpoint"]
        
        response = self.session.get(url, params={"f": "json"})
        response.raise_for_status()
        
        data = response.json()
        
        # Extract services information
        services = []
        for service in data.get("services", []):
            service_info = {
                "name": service["name"],
                "type": service["type"],
                "url": f"{self.base_url}/rest/services/{service['name']}/{service['type']}"
            }
            services.append(service_info)
        
        return {
            "service": "REST",
            "server_type": "arcgis",
            "server_config": config,
            "services": services,
            "total_services": len(services),
            "capabilities_url": url
        }
    
    def _parse_wms_layers(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse layers from WMS capabilities."""
        layers = []
        
        # Find namespace
        namespaces = {
            'wms': 'http://www.opengis.net/wms',
            '': 'http://www.opengis.net/wms'
        }
        
        # Try to find layers with different namespace approaches
        layer_elements = (root.findall('.//Layer') or 
                         root.findall('.//wms:Layer', namespaces) or
                         root.findall('.//{http://www.opengis.net/wms}Layer'))
        
        for layer in layer_elements:
            name_elem = (layer.find('Name') or 
                        layer.find('wms:Name', namespaces) or
                        layer.find('.//{http://www.opengis.net/wms}Name'))
            
            title_elem = (layer.find('Title') or 
                         layer.find('wms:Title', namespaces) or
                         layer.find('.//{http://www.opengis.net/wms}Title'))
            
            abstract_elem = (layer.find('Abstract') or 
                           layer.find('wms:Abstract', namespaces) or
                           layer.find('.//{http://www.opengis.net/wms}Abstract'))
            
            if name_elem is not None and name_elem.text:
                layer_info = {
                    "name": name_elem.text,
                    "title": title_elem.text if title_elem is not None else name_elem.text,
                    "abstract": abstract_elem.text if abstract_elem is not None else "",
                    "service": "WMS"
                }
                layers.append(layer_info)
        
        return layers
    
    def _parse_wfs_layers(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse feature types from WFS capabilities."""
        layers = []
        
        # Find namespace
        namespaces = {
            'wfs': 'http://www.opengis.net/wfs/2.0',
            'wfs20': 'http://www.opengis.net/wfs/2.0',
            'wfs11': 'http://www.opengis.net/wfs',
            '': 'http://www.opengis.net/wfs/2.0'
        }
        
        # Try to find feature types with different namespace approaches
        feature_elements = (root.findall('.//FeatureType') or 
                           root.findall('.//wfs:FeatureType', namespaces) or
                           root.findall('.//{http://www.opengis.net/wfs/2.0}FeatureType') or
                           root.findall('.//{http://www.opengis.net/wfs}FeatureType'))
        
        for feature in feature_elements:
            name_elem = (feature.find('Name') or 
                        feature.find('wfs:Name', namespaces) or
                        feature.find('.//{http://www.opengis.net/wfs/2.0}Name') or
                        feature.find('.//{http://www.opengis.net/wfs}Name'))
            
            title_elem = (feature.find('Title') or 
                         feature.find('wfs:Title', namespaces) or
                         feature.find('.//{http://www.opengis.net/wfs/2.0}Title') or
                         feature.find('.//{http://www.opengis.net/wfs}Title'))
            
            abstract_elem = (feature.find('Abstract') or 
                           feature.find('wfs:Abstract', namespaces) or
                           feature.find('.//{http://www.opengis.net/wfs/2.0}Abstract') or
                           feature.find('.//{http://www.opengis.net/wfs}Abstract'))
            
            if name_elem is not None and name_elem.text:
                layer_info = {
                    "name": name_elem.text,
                    "title": title_elem.text if title_elem is not None else name_elem.text,
                    "abstract": abstract_elem.text if abstract_elem is not None else "",
                    "service": "WFS"
                }
                layers.append(layer_info)
        
        return layers
    
    def _parse_wcs_layers(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Parse coverages from WCS capabilities."""
        layers = []
        
        # WCS uses different structure - coverages instead of layers
        namespaces = {
            'wcs': 'http://www.opengis.net/wcs/2.0',
            '': 'http://www.opengis.net/wcs/2.0'
        }
        
        coverage_elements = (root.findall('.//CoverageSummary') or 
                           root.findall('.//wcs:CoverageSummary', namespaces) or
                           root.findall('.//{http://www.opengis.net/wcs/2.0}CoverageSummary'))
        
        for coverage in coverage_elements:
            coverage_id_elem = (coverage.find('CoverageId') or 
                              coverage.find('wcs:CoverageId', namespaces) or
                              coverage.find('.//{http://www.opengis.net/wcs/2.0}CoverageId'))
            
            if coverage_id_elem is not None and coverage_id_elem.text:
                layer_info = {
                    "name": coverage_id_elem.text,
                    "title": coverage_id_elem.text,
                    "abstract": "",
                    "service": "WCS"
                }
                layers.append(layer_info)
        
        return layers
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Obtiene información general del servidor.
        
        Returns:
            Dict con información del servidor
        """
        try:
            # Obtener información básica desde las capacidades WMS
            capabilities = self.get_capabilities("WMS")
            
            if "error" in capabilities:
                return {
                    "title": f"{self.server_type.title()} Server",
                    "version": "unknown",
                    "contact": {},
                    "fees": "",
                    "access_constraints": "",
                    "error": capabilities["error"]
                }
            
            server_config = capabilities.get("server_config", {})
            
            return {
                "title": server_config.get("title", f"{self.server_type.title()} Server"),
                "version": server_config.get("version", "unknown"),
                "contact": {
                    "organization": server_config.get("contact_organization", ""),
                    "person": server_config.get("contact_person", ""),
                    "email": server_config.get("contact_email", ""),
                    "phone": server_config.get("contact_phone", "")
                },
                "fees": server_config.get("fees", ""),
                "access_constraints": server_config.get("access_constraints", ""),
                "abstract": server_config.get("abstract", ""),
                "keywords": server_config.get("keywords", []),
                "online_resource": server_config.get("online_resource", self.base_url),
                "server_type": self.server_type,
                "base_url": self.base_url
            }
            
        except Exception as e:
            return {
                "title": f"{self.server_type.title()} Server",
                "version": "unknown",
                "contact": {},
                "fees": "",
                "access_constraints": "",
                "error": f"Failed to get server info: {e}",
                "server_type": self.server_type,
                "base_url": self.base_url
            }
    
    def list_layers(self) -> Dict[str, Any]:
        """
        Lista todos los layers disponibles en el servidor.
        
        Returns:
            Dict con la lista de layers y metadatos
        """
        try:
            # Obtener layers de WMS
            wms_capabilities = self.get_capabilities("WMS")
            layers = []
            
            if "error" not in wms_capabilities:
                layers.extend(wms_capabilities.get("layers", []))
            
            # Intentar obtener layers de WFS si está disponible
            try:
                wfs_capabilities = self.get_capabilities("WFS")
                if "error" not in wfs_capabilities:
                    wfs_layers = wfs_capabilities.get("layers", [])
                    # Marcar layers WFS
                    for layer in wfs_layers:
                        layer["services"] = layer.get("services", []) + ["WFS"]
                    layers.extend(wfs_layers)
            except:
                pass
            
            # Intentar obtener layers de WCS si está disponible
            try:
                wcs_capabilities = self.get_capabilities("WCS")
                if "error" not in wcs_capabilities:
                    wcs_layers = wcs_capabilities.get("layers", [])
                    # Marcar layers WCS
                    for layer in wcs_layers:
                        layer["services"] = layer.get("services", []) + ["WCS"]
                    layers.extend(wcs_layers)
            except:
                pass
            
            # Eliminar duplicados por nombre
            unique_layers = {}
            for layer in layers:
                name = layer.get("name", "")
                if name and name not in unique_layers:
                    unique_layers[name] = layer
                elif name in unique_layers:
                    # Combinar servicios disponibles
                    existing_services = set(unique_layers[name].get("services", []))
                    new_services = set(layer.get("services", []))
                    unique_layers[name]["services"] = list(existing_services.union(new_services))
            
            final_layers = list(unique_layers.values())
            
            return {
                "layers": final_layers,
                "total_layers": len(final_layers),
                "server_type": self.server_type,
                "base_url": self.base_url
            }
            
        except Exception as e:
            return {
                "error": f"Failed to list layers: {e}",
                "layers": [],
                "total_layers": 0,
                "server_type": self.server_type,
                "base_url": self.base_url
            }
    
    def download_layer(self, layer_name: str, output_format: str = "geojson", 
                      service: str = "WFS", **kwargs) -> str:
        """
        Descarga un layer en el formato especificado.
        
        Args:
            layer_name: Nombre del layer
            output_format: Formato de salida (geojson, shapefile, gml, etc.)
            service: Servicio a usar (WFS, WMS, WCS)
            **kwargs: Parámetros adicionales (bbox, crs, maxFeatures, etc.)
            
        Returns:
            Path al archivo descargado
        """
        if self.server_type == "arcgis":
            return self._download_arcgis_layer(layer_name, output_format, **kwargs)
        else:
            return self._download_ogc_layer(layer_name, output_format, service, **kwargs)
    
    def _download_ogc_layer(self, layer_name: str, output_format: str, 
                           service: str, **kwargs) -> str:
        """Descarga layer usando servicios OGC estándar."""
        format_config = OUTPUT_FORMATS.get(output_format.lower())
        if not format_config:
            raise ValueError(f"Unsupported output format: {output_format}")
        
        # Construir URL de descarga
        if service.upper() == "WFS":
            url = self._build_wfs_url(layer_name, format_config, **kwargs)
        elif service.upper() == "WMS":
            url = self._build_wms_url(layer_name, output_format, **kwargs)
        elif service.upper() == "WCS":
            url = self._build_wcs_url(layer_name, output_format, **kwargs)
        else:
            raise ValueError(f"Unsupported service: {service}")
        
        # Descargar datos
        response = self.session.get(url)
        response.raise_for_status()
        
        # Guardar archivo temporal
        temp_dir = tempfile.gettempdir()
        filename = f"{layer_name}_{uuid.uuid4().hex[:8]}{format_config['extension']}"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        return file_path
    
    def _build_wfs_url(self, layer_name: str, format_config: Dict[str, Any], **kwargs) -> str:
        """Construye URL para descarga WFS."""
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": layer_name,
            "outputFormat": format_config["format_param"].split("=")[1]
        }
        
        # Parámetros opcionales
        if "bbox" in kwargs:
            params["bbox"] = kwargs["bbox"]
        if "crs" in kwargs:
            params["srsName"] = kwargs["crs"]
        if "maxFeatures" in kwargs:
            params["maxFeatures"] = kwargs["maxFeatures"]
        if "filter" in kwargs:
            params["filter"] = kwargs["filter"]
        
        # Construir URL
        config = GEOSERVER_TYPES.get(self.server_type, GEOSERVER_TYPES["geoserver"])
        base_path = config.get("wfs_path", "/wfs").split("?")[0]
        url = f"{self.base_url}{base_path}?{urlencode(params)}"
        
        return url
    
    def _build_wms_url(self, layer_name: str, output_format: str, **kwargs) -> str:
        """Construye URL para descarga WMS (GetMap)."""
        params = {
            "service": "WMS",
            "version": "1.3.0",
            "request": "GetMap",
            "layers": layer_name,
            "format": "image/png",
            "width": kwargs.get("width", 800),
            "height": kwargs.get("height", 600),
            "crs": kwargs.get("crs", "EPSG:4326"),
            "bbox": kwargs.get("bbox", "-180,-90,180,90")
        }
        
        # Construir URL
        config = GEOSERVER_TYPES.get(self.server_type, GEOSERVER_TYPES["geoserver"])
        base_path = config["capabilities_path"].split("?")[0]
        url = f"{self.base_url}{base_path}?{urlencode(params)}"
        
        return url
    
    def _build_wcs_url(self, layer_name: str, output_format: str, **kwargs) -> str:
        """Construye URL para descarga WCS (GetCoverage)."""
        params = {
            "service": "WCS",
            "version": "2.0.1",
            "request": "GetCoverage",
            "coverageId": layer_name,
            "format": "image/tiff"
        }
        
        # Parámetros opcionales
        if "subset" in kwargs:
            params["subset"] = kwargs["subset"]
        if "resolution" in kwargs:
            params["resolution"] = kwargs["resolution"]
        
        # Construir URL
        config = GEOSERVER_TYPES.get(self.server_type, GEOSERVER_TYPES["geoserver"])
        base_path = config.get("wcs_path", "/wcs").split("?")[0]
        url = f"{self.base_url}{base_path}?{urlencode(params)}"
        
        return url
    
    def _download_arcgis_layer(self, layer_name: str, output_format: str, **kwargs) -> str:
        """Descarga layer de ArcGIS Server."""
        # Para ArcGIS, usar REST API
        service_url = f"{self.base_url}/rest/services/{layer_name}/MapServer/0/query"
        
        params = {
            "where": kwargs.get("where", "1=1"),
            "outFields": "*",
            "f": "geojson" if output_format.lower() == "geojson" else "json"
        }
        
        if "bbox" in kwargs:
            params["geometry"] = kwargs["bbox"]
            params["geometryType"] = "esriGeometryEnvelope"
        
        response = self.session.get(service_url, params=params)
        response.raise_for_status()
        
        # Guardar archivo temporal
        temp_dir = tempfile.gettempdir()
        ext = ".geojson" if output_format.lower() == "geojson" else ".json"
        filename = f"{layer_name}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(temp_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if output_format.lower() == "geojson":
                f.write(response.text)
            else:
                json.dump(response.json(), f, indent=2)
        
        return file_path


def create_asset_from_layer(layer_data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """
    Crea un asset en el catálogo local a partir de datos de layer descargados.
    
    Args:
        layer_data: Información del layer (nombre, título, descripción, etc.)
        file_path: Path al archivo de datos descargado
        
    Returns:
        Dict con información del asset creado
    """
    try:
        # Leer datos para análisis
        data_analysis = analyze_layer_data(file_path)
        
        # Generar IDs únicos
        asset_id = str(uuid.uuid4())
        
        # Crear descriptor del asset
        asset = {
            "id": asset_id,
            "title": layer_data.get("title", layer_data.get("name", "Unknown Layer")),
            "description": layer_data.get("abstract", "Layer data from geoserver"),
            "source": "geoserver_plugin",
            "server_type": layer_data.get("server_type", "unknown"),
            "service": layer_data.get("service", "unknown"),
            "layer_name": layer_data.get("name"),
            "results_count": data_analysis.get("feature_count", 0),
            "data_uri": file_path,
            "data_dictionary_uri": create_data_dictionary(data_analysis, asset_id),
            "descriptor_uri": f"descriptors/{asset_id}.jsonld",
            "created_at": datetime.utcnow().isoformat(),
            "bbox": data_analysis.get("bbox"),
            "crs": data_analysis.get("crs")
        }
        
        # Guardar en catálogo
        save_asset_to_catalog(asset)
        
        return asset
        
    except Exception as e:
        return {"error": f"Failed to create asset: {e}"}


def analyze_layer_data(file_path: str) -> Dict[str, Any]:
    """
    Analiza los datos del layer para extraer metadatos.
    
    Args:
        file_path: Path al archivo de datos
        
    Returns:
        Dict con análisis de los datos
    """
    analysis = {
        "feature_count": 0,
        "geometry_types": [],
        "properties": {},
        "bbox": None,
        "crs": None
    }
    
    try:
        # Determinar tipo de archivo por extensión
        _, ext = os.path.splitext(file_path)
        
        if ext.lower() == '.geojson':
            analysis.update(analyze_geojson(file_path))
        elif ext.lower() == '.json':
            analysis.update(analyze_json(file_path))
        elif ext.lower() == '.csv':
            analysis.update(analyze_csv(file_path))
        else:
            # Para otros formatos, análisis básico
            file_size = os.path.getsize(file_path)
            analysis["file_size"] = file_size
            
    except Exception as e:
        analysis["error"] = str(e)
    
    return analysis


def analyze_geojson(file_path: str) -> Dict[str, Any]:
    """Analiza archivo GeoJSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data.get("features", [])
    
    analysis = {
        "feature_count": len(features),
        "geometry_types": list(set([f.get("geometry", {}).get("type") for f in features if f.get("geometry")])),
        "properties": {},
        "crs": data.get("crs", {}).get("properties", {}).get("name", "EPSG:4326")
    }
    
    # Analizar propiedades
    if features:
        sample_properties = features[0].get("properties", {})
        for prop, value in sample_properties.items():
            analysis["properties"][prop] = {
                "type": type(value).__name__,
                "sample_value": str(value)[:100]  # Truncar valores largos
            }
    
    # Calcular bbox básico
    if features:
        coords = []
        for feature in features:
            geom = feature.get("geometry", {})
            if geom.get("coordinates"):
                # Simplificado - solo para Point por ahora
                if geom.get("type") == "Point":
                    coords.append(geom["coordinates"])
        
        if coords:
            lons = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            analysis["bbox"] = [min(lons), min(lats), max(lons), max(lats)]
    
    return analysis


def analyze_json(file_path: str) -> Dict[str, Any]:
    """Analiza archivo JSON general."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    analysis = {
        "feature_count": 1,  # Archivo único
        "data_type": "json",
        "keys": list(data.keys()) if isinstance(data, dict) else [],
        "properties": {}
    }
    
    # Si es una lista, analizar elementos
    if isinstance(data, list):
        analysis["feature_count"] = len(data)
        if data and isinstance(data[0], dict):
            sample = data[0]
            for key, value in sample.items():
                analysis["properties"][key] = {
                    "type": type(value).__name__,
                    "sample_value": str(value)[:100]
                }
    
    return analysis


def analyze_csv(file_path: str) -> Dict[str, Any]:
    """Analiza archivo CSV."""
    analysis = {
        "feature_count": 0,
        "properties": {},
        "data_type": "csv"
    }
    
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        
        # Contar filas
        row_count = sum(1 for _ in reader)
        analysis["feature_count"] = row_count
        
        # Analizar headers
        for header in headers:
            analysis["properties"][header] = {
                "type": "string",  # CSV siempre strings inicialmente
                "sample_value": ""
            }
    
    return analysis


def create_data_dictionary(analysis: Dict[str, Any], asset_id: str) -> str:
    """
    Crea diccionario de datos a partir del análisis.
    
    Args:
        analysis: Análisis de los datos
        asset_id: ID del asset
        
    Returns:
        Path al archivo de diccionario de datos
    """
    dictionary = {
        "source": "geoserver_plugin",
        "generated_at": datetime.utcnow().isoformat(),
        "asset_id": asset_id,
        "variables": {},
        "total_results": analysis.get("feature_count", 0),
        "geometry_types": analysis.get("geometry_types", []),
        "spatial_info": {
            "bbox": analysis.get("bbox"),
            "crs": analysis.get("crs")
        }
    }
    
    # Convertir propiedades a variables del diccionario
    for prop_name, prop_info in analysis.get("properties", {}).items():
        dictionary["variables"][prop_name] = {
            "name": prop_name,
            "description": f"Property {prop_name} from geoserver layer",
            "data_types": [prop_info.get("type", "string")],
            "sample_values": [prop_info.get("sample_value", "")],
            "is_uri": False,
            "null_count": 0,
            "total_count": analysis.get("feature_count", 0)
        }
    
    # Guardar diccionario
    temp_dir = "tmp"
    os.makedirs(temp_dir, exist_ok=True)
    dict_file = os.path.join(temp_dir, f"data_dict_{asset_id}.json")
    
    with open(dict_file, 'w', encoding='utf-8') as f:
        json.dump(dictionary, f, indent=2, ensure_ascii=False)
    
    return dict_file


def save_asset_to_catalog(asset: Dict[str, Any]):
    """
    Guarda el asset en el catálogo local.
    
    Args:
        asset: Información del asset
    """
    catalog_file = "catalog.json"
    
    # Leer catálogo existente
    try:
        with open(catalog_file, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        catalog = {"assets": []}
    
    # Añadir nuevo asset
    catalog["assets"].append(asset)
    
    # Guardar catálogo actualizado
    with open(catalog_file, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)


def register_geoserver_service(connector: GeoServerConnector, 
                             service_name: str = None,
                             description: str = None) -> str:
    """
    Registra un geoserver como servicio de datos en el catálogo DCAT.
    
    Args:
        connector: Conector del geoserver
        service_name: Nombre personalizado del servicio
        description: Descripción personalizada
        
    Returns:
        ID del servicio registrado
    """
    catalog_manager = get_catalog_manager()
    if not catalog_manager:
        print("Warning: DCAT catalog manager not available")
        return None
    
    # Obtener información del servidor
    capabilities = connector.get_capabilities("WMS")
    server_info = connector.get_server_info()
    
    # Determinar servicios OGC disponibles
    ogc_services = []
    for service in ["WMS", "WFS", "WCS"]:
        try:
            caps = connector.get_capabilities(service)
            if "error" not in caps:
                ogc_services.append(service)
        except:
            pass
    
    # Preparar información del servicio
    service_info = {
        "title": service_name or f"{server_info.get('title', 'Geoserver')} ({connector.server_type})",
        "description": description or f"Servicio OGC {connector.server_type} con servicios: {', '.join(ogc_services)}",
        "endpoint_url": connector.base_url,
        "service_type": "ogc",
        "server_type": connector.server_type,
        "conforms_to": [f"OGC {service}" for service in ogc_services],
        "ogc_services": ogc_services,
        "capabilities": capabilities,
        "metadata": {
            "base_url": connector.base_url,
            "version": server_info.get("version", "unknown"),
            "contact": server_info.get("contact", {}),
            "fees": server_info.get("fees", ""),
            "access_constraints": server_info.get("access_constraints", "")
        },
        "authentication": {
            "type": "basic" if connector.username else "token" if connector.token else "none",
            "required": bool(connector.username or connector.token)
        },
        "status": "active",
        "last_checked": datetime.utcnow().isoformat() + "Z",
        "tags": ["gis", "ogc", connector.server_type, "spatial-data"]
    }
    
    # Añadir layers disponibles
    layers = connector.list_layers()
    if layers and "layers" in layers:
        service_info["layers"] = [layer.get("name", "") for layer in layers["layers"]]
        service_info["layer_count"] = len(layers["layers"])
    
    return catalog_manager.add_data_service(service_info)


def register_layer_as_dataset(connector: GeoServerConnector, 
                            layer_name: str,
                            service_id: str = None) -> str:
    """
    Registra un layer como dataset en el catálogo DCAT.
    
    Args:
        connector: Conector del geoserver
        layer_name: Nombre del layer
        service_id: ID del servicio que contiene este dataset
        
    Returns:
        ID del dataset registrado
    """
    catalog_manager = get_catalog_manager()
    if not catalog_manager:
        print("Warning: DCAT catalog manager not available")
        return None
    
    # Obtener información del layer
    layers = connector.list_layers()
    layer_info = None
    
    if layers and "layers" in layers:
        for layer in layers["layers"]:
            if layer.get("name") == layer_name:
                layer_info = layer
                break
    
    if not layer_info:
        print(f"Warning: Layer {layer_name} not found")
        return None
    
    # Preparar información del dataset
    dataset_info = {
        "title": layer_info.get("title", layer_name),
        "description": layer_info.get("abstract", f"Dataset geoespacial {layer_name}"),
        "creator": layer_info.get("attribution", ""),
        "publisher": connector.base_url,
        "spatial": {
            "bbox": layer_info.get("bbox", {}),
            "crs": layer_info.get("crs", "EPSG:4326")
        },
        "theme": ["geospatial", "geography"],
        "keywords": [layer_name, "gis", "spatial", connector.server_type],
        "source": f"{connector.base_url}/layer/{layer_name}",
        "format": ["WMS", "WFS", "GeoJSON", "Shapefile", "GML", "KML"],
        "size": {
            "estimated_features": layer_info.get("feature_count", "unknown")
        },
        "quality": {
            "last_updated": layer_info.get("last_modified", "unknown"),
            "source_system": connector.server_type
        },
        "tags": ["layer", layer_name, connector.server_type, "ogc"]
    }
    
    # Añadir referencia al servicio si está disponible
    if service_id:
        dataset_info["served_by_service"] = service_id
    
    return catalog_manager.add_dataset(dataset_info)


def register_distribution_from_download(layer_data: Dict[str, Any], 
                                       file_path: str,
                                       dataset_id: str = None) -> str:
    """
    Registra una distribución descargada en el catálogo DCAT.
    
    Args:
        layer_data: Datos del layer descargado
        file_path: Ruta del archivo descargado
        dataset_id: ID del dataset al que pertenece esta distribución
        
    Returns:
        ID de la distribución registrada
    """
    catalog_manager = get_catalog_manager()
    if not catalog_manager:
        print("Warning: DCAT catalog manager not available")
        # Fallback al método original
        asset = create_asset_from_layer(layer_data, file_path)
        save_asset_to_catalog(asset)
        return asset.get("id")
    
    # Obtener información del archivo
    file_size = 0
    if os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
    
    file_ext = os.path.splitext(file_path)[1].lower()
    media_types = {
        ".geojson": "application/geo+json",
        ".json": "application/json",
        ".shp": "application/x-shapefile",
        ".gml": "application/gml+xml",
        ".kml": "application/vnd.google-earth.kml+xml",
        ".csv": "text/csv"
    }
    
    # Preparar información de la distribución
    distribution_info = {
        "title": f"{layer_data.get('layer_name', 'Unknown')} - {layer_data.get('format', 'Data')}",
        "description": f"Distribución en formato {layer_data.get('format', 'unknown')} del layer {layer_data.get('layer_name', 'unknown')}",
        "download_url": layer_data.get("download_url", ""),
        "access_url": layer_data.get("source_url", ""),
        "media_type": media_types.get(file_ext, "application/octet-stream"),
        "format": layer_data.get("format", file_ext.replace(".", "").upper()),
        "byte_size": file_size,
        "source": layer_data.get("source", ""),
        "file_path": file_path,
        "results_count": layer_data.get("results_count", 0),
        "metadata": {
            "layer_name": layer_data.get("layer_name"),
            "server_type": layer_data.get("server_type"),
            "bbox": layer_data.get("bbox", {}),
            "crs": layer_data.get("crs", "EPSG:4326"),
            "download_params": layer_data.get("download_params", {})
        }
    }
    
    # Añadir referencia al dataset si está disponible
    if dataset_id:
        distribution_info["belongs_to_dataset"] = dataset_id
    
    # Crear diccionario de datos si es posible
    try:
        # Análisis básico del archivo
        analysis = {"file_path": file_path, "file_size": file_size}
        dict_file = create_data_dictionary(analysis, distribution_info.get("id", str(uuid.uuid4())))
        distribution_info["data_dictionary"] = dict_file
    except Exception as e:
        print(f"Warning: Could not create data dictionary: {e}")
    
    return catalog_manager.add_distribution(distribution_info)


def register_interesting_source(url: str, 
                               name: str,
                               description: str = "",
                               source_type: str = "geoserver",
                               category: str = "geospatial",
                               tags: List[str] = None) -> str:
    """
    Registra una fuente de datos interesante para seguimiento.
    
    Args:
        url: URL de la fuente
        name: Nombre de la fuente
        description: Descripción
        source_type: Tipo de fuente
        category: Categoría
        tags: Tags asociados
        
    Returns:
        ID de la fuente registrada
    """
    catalog_manager = get_catalog_manager()
    if not catalog_manager:
        print("Warning: DCAT catalog manager not available")
        return None
    
    source_info = {
        "name": name,
        "description": description,
        "url": url,
        "type": source_type,
        "category": category,
        "status": "discovered",
        "check_frequency": "manual",
        "tags": tags or [],
        "notes": f"Fuente descubierta automáticamente - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
        "metadata": {
            "discovered_date": datetime.utcnow().isoformat() + "Z",
            "discovered_method": "manual_registration"
        }
    }
    
    return catalog_manager.add_source(source_info)


def get_catalog_summary() -> Dict[str, Any]:
    """
    Obtiene un resumen del estado actual del catálogo DCAT.
    
    Returns:
        Resumen con estadísticas y conteos
    """
    catalog_manager = get_catalog_manager()
    if not catalog_manager:
        return {"error": "DCAT catalog manager not available"}
    
    stats = catalog_manager.get_statistics()
    
    # Obtener información adicional
    services = catalog_manager.get_services()
    datasets = catalog_manager.get_datasets()
    distributions = catalog_manager.get_distributions()
    sources = catalog_manager.get_sources()
    
    return {
        "statistics": stats,
        "services": {
            "total": len(services),
            "by_type": {},
            "active": len([s for s in services if s.get("custom:status") == "active"])
        },
        "datasets": {
            "total": len(datasets),
            "themes": {},
            "recent": len([d for d in datasets if "2024" in d.get("dcterms:created", "")])
        },
        "distributions": {
            "total": len(distributions),
            "formats": {},
            "total_size": sum([d.get("dcat:byteSize", 0) for d in distributions if d.get("dcat:byteSize")])
        },
        "sources": {
            "total": len(sources),
            "by_category": {},
            "active": len([s for s in sources if s.get("status") == "active"])
        }
    }
