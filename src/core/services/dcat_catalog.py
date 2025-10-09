"""
Módulo para manejo del catálogo extendido con formato DCAT.

Este módulo proporciona funcionalidades para gestionar un catálogo completo
que incluye servicios de datos, datasets, distribuciones y endpoints,
siguiendo el estándar DCAT (Data Catalog Vocabulary).
"""
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


class DCATCatalogManager:
    """Gestor del catálogo extendido con formato DCAT."""
    
    def __init__(self, catalog_file: str = "catalog.json"):
        self.catalog_file = catalog_file
        self.catalog = self._load_catalog()
    
    def _load_catalog(self) -> Dict[str, Any]:
        """Carga el catálogo desde archivo o crea uno nuevo."""
        try:
            with open(self.catalog_file, 'r', encoding='utf-8') as f:
                catalog = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            catalog = {}
        
        # Asegurar estructura DCAT completa
        return self._ensure_dcat_structure(catalog)
    
    def _ensure_dcat_structure(self, catalog: Dict[str, Any]) -> Dict[str, Any]:
        """Asegura que el catálogo tenga la estructura DCAT completa."""
        default_structure = {
            "@context": {
                "dcat": "http://www.w3.org/ns/dcat#",
                "dcterms": "http://purl.org/dc/terms/",
                "foaf": "http://xmlns.com/foaf/0.1/",
                "vcard": "http://www.w3.org/2006/vcard/ns#"
            },
            "@type": "dcat:Catalog",
            "dcterms:title": "Datamesh Client Catalog",
            "dcterms:description": "Catálogo de datos del cliente Datamesh",
            "dcterms:created": datetime.utcnow().isoformat() + "Z",
            "dcterms:modified": datetime.utcnow().isoformat() + "Z",
            "dcat:service": [],        # Servicios de datos
            "dcat:dataset": [],        # Datasets
            "dcat:distribution": [],   # Distribuciones/Assets
            "dcat:endpointURL": [],    # URLs de endpoints
            "custom:sources": [],      # Fuentes de datos rastreadas
            "custom:statistics": {     # Estadísticas del catálogo
                "total_services": 0,
                "total_datasets": 0,
                "total_distributions": 0,
                "total_sources": 0,
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        # Migrar assets existentes a distribuciones
        if "assets" in catalog:
            default_structure["dcat:distribution"] = catalog["assets"]
            # Convertir assets a formato DCAT distribution
            for asset in default_structure["dcat:distribution"]:
                if "@type" not in asset:
                    asset["@type"] = "dcat:Distribution"
                if "dcterms:identifier" not in asset and "id" in asset:
                    asset["dcterms:identifier"] = asset["id"]
                if "dcterms:title" not in asset and "title" in asset:
                    asset["dcterms:title"] = asset["title"]
                if "dcterms:description" not in asset and "description" in asset:
                    asset["dcterms:description"] = asset["description"]
        
        # Merge with existing catalog, keeping DCAT structure
        for key, value in default_structure.items():
            if key not in catalog:
                catalog[key] = value
        
        return catalog
    
    def save_catalog(self):
        """Guarda el catálogo en archivo."""
        self.catalog["dcterms:modified"] = datetime.utcnow().isoformat() + "Z"
        self._update_statistics()
        
        with open(self.catalog_file, 'w', encoding='utf-8') as f:
            json.dump(self.catalog, f, indent=2, ensure_ascii=False)
    
    def _update_statistics(self):
        """Actualiza las estadísticas del catálogo."""
        stats = self.catalog["custom:statistics"]
        stats["total_services"] = len(self.catalog["dcat:service"])
        stats["total_datasets"] = len(self.catalog["dcat:dataset"])
        stats["total_distributions"] = len(self.catalog["dcat:distribution"])
        stats["total_sources"] = len(self.catalog["custom:sources"])
        stats["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    def add_data_service(self, service_info: Dict[str, Any]) -> str:
        """
        Añade un servicio de datos al catálogo.
        
        Args:
            service_info: Información del servicio
            
        Returns:
            ID del servicio creado
        """
        service_id = service_info.get("id", str(uuid.uuid4()))
        
        service = {
            "@type": "dcat:DataService",
            "dcterms:identifier": service_id,
            "dcterms:title": service_info.get("title", "Unknown Service"),
            "dcterms:description": service_info.get("description", ""),
            "dcat:endpointURL": service_info.get("endpoint_url", ""),
            "dcat:servesDataset": service_info.get("serves_dataset", []),
            "dcterms:conformsTo": service_info.get("conforms_to", []),
            "custom:serviceType": service_info.get("service_type", "unknown"),
            "custom:serverType": service_info.get("server_type", "unknown"),
            "custom:authentication": service_info.get("authentication", {}),
            "custom:capabilities": service_info.get("capabilities", {}),
            "custom:metadata": service_info.get("metadata", {}),
            "dcterms:created": datetime.utcnow().isoformat() + "Z",
            "dcterms:modified": datetime.utcnow().isoformat() + "Z",
            "custom:status": service_info.get("status", "active"),
            "custom:lastChecked": service_info.get("last_checked"),
            "custom:tags": service_info.get("tags", [])
        }
        
        # Añadir información específica según el tipo de servicio
        if service_info.get("service_type") == "ogc":
            service["custom:ogcServices"] = service_info.get("ogc_services", [])
            service["custom:layers"] = service_info.get("layers", [])
        
        self.catalog["dcat:service"].append(service)
        self.save_catalog()
        
        return service_id
    
    def add_dataset(self, dataset_info: Dict[str, Any]) -> str:
        """
        Añade un dataset al catálogo.
        
        Args:
            dataset_info: Información del dataset
            
        Returns:
            ID del dataset creado
        """
        dataset_id = dataset_info.get("id", str(uuid.uuid4()))
        
        dataset = {
            "@type": "dcat:Dataset",
            "dcterms:identifier": dataset_id,
            "dcterms:title": dataset_info.get("title", "Unknown Dataset"),
            "dcterms:description": dataset_info.get("description", ""),
            "dcterms:creator": dataset_info.get("creator", ""),
            "dcterms:publisher": dataset_info.get("publisher", ""),
            "dcterms:created": dataset_info.get("created", datetime.utcnow().isoformat() + "Z"),
            "dcterms:modified": datetime.utcnow().isoformat() + "Z",
            "dcterms:spatial": dataset_info.get("spatial", {}),
            "dcterms:temporal": dataset_info.get("temporal", {}),
            "dcat:theme": dataset_info.get("theme", []),
            "dcat:keyword": dataset_info.get("keywords", []),
            "dcat:distribution": dataset_info.get("distributions", []),
            "custom:source": dataset_info.get("source", ""),
            "custom:format": dataset_info.get("format", []),
            "custom:size": dataset_info.get("size", {}),
            "custom:quality": dataset_info.get("quality", {}),
            "custom:tags": dataset_info.get("tags", [])
        }
        
        self.catalog["dcat:dataset"].append(dataset)
        self.save_catalog()
        
        return dataset_id
    
    def add_distribution(self, distribution_info: Dict[str, Any]) -> str:
        """
        Añade una distribución (asset) al catálogo.
        
        Args:
            distribution_info: Información de la distribución
            
        Returns:
            ID de la distribución creada
        """
        dist_id = distribution_info.get("id", str(uuid.uuid4()))
        
        distribution = {
            "@type": "dcat:Distribution",
            "dcterms:identifier": dist_id,
            "dcterms:title": distribution_info.get("title", "Unknown Distribution"),
            "dcterms:description": distribution_info.get("description", ""),
            "dcat:downloadURL": distribution_info.get("download_url", ""),
            "dcat:accessURL": distribution_info.get("access_url", ""),
            "dcat:mediaType": distribution_info.get("media_type", ""),
            "dcterms:format": distribution_info.get("format", ""),
            "dcat:byteSize": distribution_info.get("byte_size"),
            "dcterms:created": distribution_info.get("created", datetime.utcnow().isoformat() + "Z"),
            "dcterms:modified": datetime.utcnow().isoformat() + "Z",
            "custom:source": distribution_info.get("source", ""),
            "custom:filePath": distribution_info.get("file_path", ""),
            "custom:dataDictionary": distribution_info.get("data_dictionary", ""),
            "custom:resultsCount": distribution_info.get("results_count", 0),
            "custom:metadata": distribution_info.get("metadata", {})
        }
        
        self.catalog["dcat:distribution"].append(distribution)
        self.save_catalog()
        
        return dist_id
    
    def add_source(self, source_info: Dict[str, Any]) -> str:
        """
        Añade una fuente de datos rastreada.
        
        Args:
            source_info: Información de la fuente
            
        Returns:
            ID de la fuente creada
        """
        source_id = source_info.get("id", str(uuid.uuid4()))
        
        source = {
            "id": source_id,
            "name": source_info.get("name", "Unknown Source"),
            "description": source_info.get("description", ""),
            "url": source_info.get("url", ""),
            "type": source_info.get("type", "unknown"),
            "category": source_info.get("category", "general"),
            "status": source_info.get("status", "active"),
            "added_date": datetime.utcnow().isoformat() + "Z",
            "last_checked": source_info.get("last_checked"),
            "check_frequency": source_info.get("check_frequency", "manual"),
            "metadata": source_info.get("metadata", {}),
            "tags": source_info.get("tags", []),
            "notes": source_info.get("notes", ""),
            "related_services": source_info.get("related_services", []),
            "related_datasets": source_info.get("related_datasets", [])
        }
        
        self.catalog["custom:sources"].append(source)
        self.save_catalog()
        
        return source_id
    
    def get_services(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene servicios filtrados por tipo."""
        services = self.catalog["dcat:service"]
        if service_type:
            return [s for s in services if s.get("custom:serviceType") == service_type]
        return services
    
    def get_datasets(self, theme: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene datasets filtrados por tema."""
        datasets = self.catalog["dcat:dataset"]
        if theme:
            return [d for d in datasets if theme in d.get("dcat:theme", [])]
        return datasets
    
    def get_distributions(self, format_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene distribuciones filtradas por formato."""
        distributions = self.catalog["dcat:distribution"]
        if format_filter:
            return [d for d in distributions if d.get("dcterms:format") == format_filter]
        return distributions
    
    def get_sources(self, category: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene fuentes filtradas por categoría y estado."""
        sources = self.catalog["custom:sources"]
        if category:
            sources = [s for s in sources if s.get("category") == category]
        if status:
            sources = [s for s in sources if s.get("status") == status]
        return sources
    
    def find_by_id(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Busca un elemento por ID en todas las categorías."""
        # Buscar en servicios
        for service in self.catalog["dcat:service"]:
            if service.get("dcterms:identifier") == item_id:
                return {"type": "service", "item": service}
        
        # Buscar en datasets
        for dataset in self.catalog["dcat:dataset"]:
            if dataset.get("dcterms:identifier") == item_id:
                return {"type": "dataset", "item": dataset}
        
        # Buscar en distribuciones
        for distribution in self.catalog["dcat:distribution"]:
            if distribution.get("dcterms:identifier") == item_id or distribution.get("id") == item_id:
                return {"type": "distribution", "item": distribution}
        
        # Buscar en fuentes
        for source in self.catalog["custom:sources"]:
            if source.get("id") == item_id:
                return {"type": "source", "item": source}
        
        return None
    
    def update_item_status(self, item_id: str, status: str, notes: Optional[str] = None):
        """Actualiza el estado de un elemento."""
        item_info = self.find_by_id(item_id)
        if item_info:
            item = item_info["item"]
            if item_info["type"] == "source":
                item["status"] = status
                item["last_checked"] = datetime.utcnow().isoformat() + "Z"
                if notes:
                    item["notes"] = notes
            else:
                item["custom:status"] = status
                item["custom:lastChecked"] = datetime.utcnow().isoformat() + "Z"
                if notes:
                    if "custom:notes" not in item:
                        item["custom:notes"] = []
                    item["custom:notes"].append({
                        "note": notes,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })
            
            self.save_catalog()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas del catálogo."""
        return self.catalog["custom:statistics"]
    
    def export_dcat_rdf(self, output_file: str):
        """Exporta el catálogo en formato DCAT RDF/TTL."""
        # Implementación básica - se puede extender
        rdf_content = f"""
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

<#catalog> a dcat:Catalog ;
    dcterms:title "{self.catalog['dcterms:title']}" ;
    dcterms:description "{self.catalog['dcterms:description']}" ;
    dcterms:created "{self.catalog['dcterms:created']}" ;
    dcterms:modified "{self.catalog['dcterms:modified']}" .
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(rdf_content)


# Función de conveniencia para obtener el gestor del catálogo
def get_catalog_manager(catalog_file: str = "catalog.json") -> DCATCatalogManager:
    """Obtiene una instancia del gestor de catálogo."""
    return DCATCatalogManager(catalog_file)
