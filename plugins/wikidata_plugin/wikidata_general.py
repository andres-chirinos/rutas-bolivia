"""
Plugin generalizado para ejecutar queries SPARQL en Wikidata y guardar como assets.

Este plugin permite:
1. Ejecutar cualquier query SPARQL personalizada en Wikidata
2. Guardar automáticamente los resultados como assets con su diccionario de datos
3. Exponer los datos a través del sistema de assets del datamesh
"""

from src.adapters.crypto.signature_adapter import SignatureAdapter
from src.core.services.prov_generator import (
    generate_prov_for_asset,
    generate_asset_descriptor_jsonld,
)
from src.adapters.persistence.local_persistence import LocalPersistence
import requests
import json
import re
import uuid
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import sys
import os

# Add the project root to Python path
project_root = os.path.join(os.path.dirname(__file__), "..", "..")
if project_root not in sys.path:
    sys.path.insert(0, project_root)


SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"


class WikidataQueryExecutor:
    """Ejecutor de queries SPARQL generalizadas para Wikidata."""

    def __init__(self, persistence: Optional[LocalPersistence] = None):
        self.persistence = persistence or LocalPersistence()

    def execute_sparql_query(
        self,
        query: str,
        title: str,
        description: str = "",
        limit: int = 500,
        timeout: int = 30,
        output_format: str = "geojson",
    ) -> Dict[str, Any]:
        """
        Ejecuta una query SPARQL en Wikidata y retorna los resultados.

        Args:
            query: Query SPARQL a ejecutar
            title: Título descriptivo para el asset
            description: Descripción del dataset
            limit: Límite de resultados (se añade automáticamente si no está en la query)
            timeout: Timeout para la request
            output_format: Formato de salida ('geojson', 'json', 'csv')

        Returns:
            Dict con los datos procesados y metadata del asset
        """
        # Añadir LIMIT si no está presente en la query
        if "LIMIT" not in query.upper():
            query = query.strip()
            if not query.endswith("."):
                query += f" LIMIT {limit}"
            else:
                query = query[:-1] + f" LIMIT {limit}"

        # Ejecutar query
        headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": "DatameshClient/1.0 (https://github.com/example/datamesh-client; admin@example.com)"
        }
        response = requests.get(
            SPARQL_ENDPOINT, params={"query": query}, headers=headers, timeout=timeout
        )
        response.raise_for_status()

        raw_data = response.json()

        # Procesar resultados según el formato solicitado
        processed_data = self._process_sparql_results(raw_data, output_format)

        # Generar diccionario de datos
        data_dictionary = self._generate_data_dictionary(raw_data, query)

        # Crear asset
        asset_info = self._create_asset(
            data=processed_data,
            data_dictionary=data_dictionary,
            title=title,
            description=description,
            query=query,
            raw_results_count=len(raw_data.get(
                "results", {}).get("bindings", [])),
        )

        return asset_info

    def _process_sparql_results(
        self, raw_data: Dict[str, Any], output_format: str
    ) -> Any:
        """Procesa los resultados SPARQL según el formato solicitado."""
        bindings = raw_data.get("results", {}).get("bindings", [])

        if output_format.lower() == "geojson":
            return self._convert_to_geojson(bindings)
        elif output_format.lower() == "json":
            return self._convert_to_structured_json(bindings)
        elif output_format.lower() == "csv":
            return self._convert_to_csv_data(bindings)
        else:
            # Formato por defecto: JSON estructurado
            return self._convert_to_structured_json(bindings)

    def _convert_to_geojson(self, bindings: List[Dict]) -> Dict[str, Any]:
        """Convierte resultados SPARQL a GeoJSON si contienen coordenadas."""
        features = []

        for row in bindings:
            feature_properties = {}
            geometry = None
            wikidata_id = None

            # Extraer todas las propiedades
            for var, value_info in row.items():
                value = value_info.get("value", "")

                # Buscar coordenadas
                if var == "coord" or "coord" in var.lower():
                    coord_match = re.match(
                        r"Point\(([-0-9\.]+) ([-0-9\.]+)\)", value)
                    if coord_match:
                        lon, lat = float(coord_match.group(1)), float(
                            coord_match.group(2)
                        )
                        geometry = {"type": "Point", "coordinates": [lon, lat]}
                        continue

                # Extraer ID de URIs de Wikidata para compatibilidad
                if var == "item" and value.startswith(
                    "http://www.wikidata.org/entity/"
                ):
                    wikidata_id = value.split("/")[-1]
                    feature_properties["source"] = value
                elif var == "itemLabel":
                    feature_properties["label"] = value
                elif value.startswith("http://www.wikidata.org/entity/"):
                    feature_properties[f"{var}_id"] = value.split("/")[-1]
                    feature_properties[f"{var}_uri"] = value
                else:
                    feature_properties[var] = value

            # Solo crear feature si tiene geometría válida
            if geometry and wikidata_id:
                # Usar el formato esperado por shortest_path: "id" en lugar de "item_id"
                feature_properties["id"] = wikidata_id

                feature = {
                    "type": "Feature",
                    "properties": feature_properties,
                    "geometry": geometry,
                }
                features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "total_features": len(features),
                "total_bindings": len(bindings),
                "has_geometry": len(features) > 0,
            },
        }

    def _convert_to_structured_json(self, bindings: List[Dict]) -> Dict[str, Any]:
        """Convierte resultados SPARQL a JSON estructurado."""
        records = []

        for row in bindings:
            record = {}
            for var, value_info in row.items():
                value = value_info.get("value", "")
                datatype = value_info.get("datatype", "")

                # Extraer ID de URIs de Wikidata
                if value.startswith("http://www.wikidata.org/entity/"):
                    record[f"{var}_id"] = value.split("/")[-1]
                    record[f"{var}_uri"] = value
                else:
                    record[var] = value

                if datatype:
                    record[f"{var}_datatype"] = datatype

            records.append(record)

        return {
            "data": records,
            "metadata": {"total_records": len(records), "source": "wikidata_sparql"},
        }

    def _convert_to_csv_data(self, bindings: List[Dict]) -> Dict[str, Any]:
        """Convierte resultados SPARQL a estructura compatible con CSV."""
        if not bindings:
            return {"headers": [], "rows": []}

        # Obtener todas las columnas únicas
        all_vars = set()
        for row in bindings:
            all_vars.update(row.keys())

        headers = sorted(list(all_vars))
        rows = []

        for row in bindings:
            csv_row = []
            for header in headers:
                value = row.get(header, {}).get("value", "")
                csv_row.append(value)
            rows.append(csv_row)

        return {
            "headers": headers,
            "rows": rows,
            "metadata": {"total_rows": len(rows), "total_columns": len(headers)},
        }

    def _generate_data_dictionary(
        self, raw_data: Dict[str, Any], query: str
    ) -> Dict[str, Any]:
        """Genera un diccionario de datos basado en los resultados SPARQL."""
        vars_info = raw_data.get("head", {}).get("vars", [])
        bindings = raw_data.get("results", {}).get("bindings", [])

        # Analizar tipos de datos y valores únicos por variable
        var_analysis = {}

        for var in vars_info:
            var_analysis[var] = {
                "name": var,
                "description": f"Variable SPARQL: {var}",
                "data_types": set(),
                "sample_values": [],
                "is_uri": False,
                "is_coordinate": False,
                "null_count": 0,
                "total_count": 0,
            }

        # Analizar cada binding
        for binding in bindings:
            for var in vars_info:
                var_analysis[var]["total_count"] += 1

                if var in binding:
                    value_info = binding[var]
                    value = value_info.get("value", "")
                    datatype = value_info.get("datatype", "")
                    value_type = value_info.get("type", "")

                    # Registrar tipo de dato
                    if datatype:
                        var_analysis[var]["data_types"].add(datatype)
                    if value_type:
                        var_analysis[var]["data_types"].add(value_type)

                    # Detectar URIs
                    if value.startswith("http://"):
                        var_analysis[var]["is_uri"] = True

                    # Detectar coordenadas
                    if re.match(r"Point\([-0-9\.\s]+\)", value):
                        var_analysis[var]["is_coordinate"] = True

                    # Guardar valores de muestra (primeros 5)
                    if len(var_analysis[var]["sample_values"]) < 5:
                        var_analysis[var]["sample_values"].append(value)
                else:
                    var_analysis[var]["null_count"] += 1

        # Convertir sets a listas para serialización JSON
        for var in var_analysis:
            var_analysis[var]["data_types"] = list(
                var_analysis[var]["data_types"])

        return {
            "source": "wikidata",
            "query": query,
            "endpoint": SPARQL_ENDPOINT,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "variables": var_analysis,
            "total_results": len(bindings),
            "sparql_vars": vars_info,
        }

    def _create_asset(
        self,
        data: Any,
        data_dictionary: Dict[str, Any],
        title: str,
        description: str,
        query: str,
        raw_results_count: int,
    ) -> Dict[str, Any]:
        """Crea y guarda un asset con los datos y su diccionario."""

        # Generar ID único para el asset
        asset_id = f"wikidata_query_{uuid.uuid4().hex[:8]}"

        # Crear estructura del asset
        asset = {
            "id": asset_id,
            "title": title,
            "description": description,
            "source": "wikidata",
            "query": query,
            "results_count": raw_results_count,
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        # Generar provenance
        prov = generate_prov_for_asset(asset, actor="wikidata_plugin")
        asset["prov"] = prov

        # Firmar asset
        signer = SignatureAdapter()
        signed_asset = signer.sign(asset)

        # Guardar datos en archivo temporal
        data_filename = f"{asset_id}_data.json"
        data_path = Path("tmp") / data_filename
        data_path.parent.mkdir(exist_ok=True)

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Guardar diccionario de datos
        dict_filename = f"{asset_id}_dictionary.json"
        dict_path = Path("tmp") / dict_filename

        with open(dict_path, "w", encoding="utf-8") as f:
            json.dump(data_dictionary, f, ensure_ascii=False, indent=2)

        # Actualizar catálogo local
        catalog = self.persistence.load_catalog()
        catalog.setdefault("assets", []).append(signed_asset)

        # Generar descriptor JSON-LD
        descriptor = generate_asset_descriptor_jsonld(
            signed_asset, data_uri=str(data_path)
        )

        # Añadir referencia al diccionario de datos en el descriptor
        descriptor["datamesh:dataDictionary"] = {"@id": str(dict_path)}

        # Guardar descriptor
        desc_rel_path = f"descriptors/{signed_asset['uuid']}.jsonld"
        self.persistence.save_asset_descriptor(desc_rel_path, descriptor)

        # Actualizar referencias en el asset
        signed_asset["data_uri"] = str(data_path)
        signed_asset["descriptor_uri"] = desc_rel_path
        signed_asset["data_dictionary_uri"] = str(dict_path)

        # Actualizar catálogo con las referencias
        catalog["assets"][-1] = signed_asset
        self.persistence.save_catalog(catalog)

        return {
            "asset": signed_asset,
            "data_path": str(data_path),
            "dictionary_path": str(dict_path),
            "descriptor_path": desc_rel_path,
            "data": data,
            "data_dictionary": data_dictionary,
        }


# Funciones de conveniencia para mantener compatibilidad
def fetch_wikidata_query(
    query: str,
    title: str,
    description: str = "",
    output_format: str = "geojson",
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Función de conveniencia para ejecutar una query SPARQL en Wikidata.

    Args:
        query: Query SPARQL a ejecutar
        title: Título para el asset
        description: Descripción del dataset
        output_format: Formato de salida ('geojson', 'json', 'csv')
        limit: Límite de resultados

    Returns:
        Dict con información del asset creado
    """
    executor = WikidataQueryExecutor()
    return executor.execute_sparql_query(
        query=query,
        title=title,
        description=description,
        limit=limit,
        output_format=output_format,
    )


def fetch_museums_bolivia_generalized(
    output_geojson: str = None, limit: int = 500
) -> str:
    """
    Versión generalizada de la función original que mantiene compatibilidad.
    Ahora usa el sistema de assets.
    """
    query = """
    SELECT DISTINCT ?item ?itemLabel ?coord ?typeLabel WHERE {
        SERVICE wikibase:around {
            ?item wdt:P625 ?coord .
            bd:serviceParam wikibase:center "Point(-68.1305956 -16.5044756)"^^geo:wktLiteral .
            bd:serviceParam wikibase:radius "25" .
        }

        ?item wdt:P31 ?type .
        FILTER(?type IN (
            wd:Q22698, wd:Q33506, wd:Q570116, wd:Q4989906, wd:Q174782, wd:Q839954,
            wd:Q8514, wd:Q16970, wd:Q16560, wd:Q124757, wd:Q166118,
            wd:Q46169, wd:Q8502
        )).
        ?item wdt:P17 wd:Q750 .

        SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
    }
    """

    result = fetch_wikidata_query(
        query=query,
        title="Museos de Bolivia",
        description="Museos en Bolivia obtenidos de Wikidata",
        output_format="geojson",
        limit=limit,
    )

    # Si se especifica un archivo de salida, escribir ahí también
    if output_geojson:
        with open(output_geojson, "w", encoding="utf-8") as f:
            json.dump(result["data"], f, ensure_ascii=False, indent=2)
        return output_geojson

    return result["data_path"]


# Queries predefinidas comunes
COMMON_QUERIES = {
    "museums_bolivia": {
        "query": """
    SELECT ?item ?itemLabel ?coord ?typeLabel ?image WHERE {
      VALUES ?type {
        wd:Q33506        # Museo
        wd:Q4989906      # Estatua
        wd:Q174782        # Plaza
        wd:Q570116        # Monumento
        wd:Q839954        # Sitio arqueológico
        wd:Q35112127        # Edificio histórico
        wd:Q597526         # Iglesia
        wd:Q166118        # Sitio Patrimonio de la Humanidad
        wd:Q46169         # Parque nacional
        wd:Q22698 # Parque
        #wd:Q8502          # Montaña
      }
      ?item wdt:P31/wdt:P279* ?type .
      ?item wdt:P17 wd:Q750 .  # Bolivia
      ?item wdt:P625 ?coord .
      OPTIONAL { ?item wdt:P18 ?image . }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
      OPTIONAL { ?item wdt:P31 ?type . }
    }
    """,
        "title": "Lugares turísticos de Bolivia",
        "description": "Listado completo de museos, monumentos, plazas, estatuas y otros sitios de interés turístico en Bolivia con coordenadas y tipo",
    },
    "universities_bolivia": {
        "query": """
        SELECT ?item ?itemLabel ?coord ?founded WHERE {
          ?item wdt:P31/wdt:P279* wd:Q3918 .
          ?item wdt:P17 wd:Q750 .
          OPTIONAL { ?item wdt:P625 ?coord }
          OPTIONAL { ?item wdt:P571 ?founded }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
        }
        """,
        "title": "Universidades de Bolivia",
        "description": "Universidades en Bolivia con coordenadas y fechas de fundación",
    },
    "cities_bolivia": {
        "query": """
        SELECT ?item ?itemLabel ?coord ?population WHERE {
          ?item wdt:P31/wdt:P279* wd:Q515 .
          ?item wdt:P17 wd:Q750 .
          ?item wdt:P625 ?coord .
          OPTIONAL { ?item wdt:P1082 ?population }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". }
        }
        """,
        "title": "Ciudades de Bolivia",
        "description": "Ciudades en Bolivia con coordenadas y población",
    },
}


def fetch_common_query(query_name: str, limit: int = 500) -> Dict[str, Any]:
    """
    Ejecuta una query predefinida común.

    Args:
        query_name: Nombre de la query predefinida
        limit: Límite de resultados

    Returns:
        Dict con información del asset creado
    """
    if query_name not in COMMON_QUERIES:
        available = ", ".join(COMMON_QUERIES.keys())
        raise ValueError(
            f"Query '{query_name}' no encontrada. Disponibles: {available}"
        )

    query_info = COMMON_QUERIES[query_name]

    return fetch_wikidata_query(
        query=query_info["query"],
        title=query_info["title"],
        description=query_info["description"],
        limit=limit,
        output_format="geojson",
    )
