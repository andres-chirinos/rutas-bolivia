"""Small FastAPI server to expose processing and the demo pipeline over HTTP.

Assumptions (reasonable defaults):
- `plugins.wikidata_plugin.wikidata_fetcher.fetch_museums_bolivia()` exists and returns a GeoJSON-like Python dict.
- `plugins.graph_compute.shortest_path.shortest_path(nodes_geojson, lines_geojson, src, dst)` exists and returns a dict with at least a `route_geojson` key or returns a GeoJSON dict directly.
- The repository contains a sensible default network file at `dummy_datasets/rutas_recorridos_2025.geojson` which will be used if no `network` query argument is supplied.

If function signatures differ, adapt the API to call the real signatures (this server aims to be a small adapter layer).

Run with:
    uvicorn src.adapters.api.app:app --reload --host 127.0.0.1 --port 8000

"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, Any, Dict
from datetime import datetime
import importlib
import os
import traceback
import json
import tempfile
import uuid
import re
from math import radians, cos, sin, asin, sqrt

app = FastAPI(title="Datamesh Client API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_NETWORK = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "dummy_datasets", "puma_katari.geojson")

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/plugin/run")
async def plugin_run(payload: dict):
    """Run an arbitrary plugin function by module:function name.

    payload = {
      "plugin": "plugins.utils.echo:echo",
      "args": ...   # optional: dict for kwargs, list for *args, scalar for single arg
    }
    """
    plugin = payload.get("plugin")
    if not plugin:
        raise HTTPException(status_code=400, detail="'plugin' field required")
    args = payload.get("args", None)
    try:
        module_name, func_name = plugin.split(":")
        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot import plugin '{plugin}': {e}")

    try:
        if isinstance(args, dict):
            result = func(**args)
        elif isinstance(args, list):
            result = func(*args)
        elif args is None:
            result = func()
        else:
            result = func(args)
    except Exception as e:
        tb = traceback.format_exc()
        # return structured JSON with error and traceback for easier debugging
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": tb})

    # Ensure result is JSON-serializable when possible
    return JSONResponse(content={"result": result})


@app.get("/museums")
async def get_museums_only():
    """Get museums data only, without any route calculation."""
    try:
        fetcher = importlib.import_module("plugins.wikidata_plugin.wikidata_fetcher")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import museums plugin: {e}")

    # prepare tmp dir and filename
    tmpdir = os.path.join(os.getcwd(), "tmp")
    os.makedirs(tmpdir, exist_ok=True)
    nodes_path = os.path.join(tmpdir, f"nodes_{uuid.uuid4().hex}.geojson")

    try:
        # Fetch museums without any route processing
        fetcher.fetch_museums_bolivia(nodes_path, limit=100)
        
        with open(nodes_path, 'r', encoding='utf-8') as f:
            nodes_geojson = json.load(f)
        
        return JSONResponse(content={
            "nodes": nodes_geojson,
            "success": True
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to fetch museums: {e}",
                "traceback": tb
            }
        )
    finally:
        # Cleanup
        if os.path.exists(nodes_path):
            os.remove(nodes_path)


@app.get("/demo/museums")
async def demo_museums(src: str = Query(...), dst: str = Query(...), network: Optional[str] = None):
    """Run the museums demo pipeline and return JSON with nodes, network (optional) and route.

    This adapter uses temporary files because the existing plugins operate on filesystem paths:
    - `fetch_museums_bolivia(output_geojson, limit=...)` writes to `output_geojson` and returns that path.
    - `shortest_path(nodes_geojson_path, lines_geojson_path, src_id, dst_id)` reads files and returns a dict.
    """
    # Import plugins lazily and call them.
    try:
        fetcher = importlib.import_module("plugins.wikidata_plugin.wikidata_fetcher")
        compute = importlib.import_module("plugins.graph_compute.shortest_path")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import demo plugins: {e}")

    # prepare tmp dir and filenames
    tmpdir = os.path.join(os.getcwd(), "tmp")
    os.makedirs(tmpdir, exist_ok=True)
    nodes_path = os.path.join(tmpdir, f"nodes_{uuid.uuid4().hex}.geojson")

    # 1) Fetch nodes -> writes to nodes_path
    try:
        if hasattr(fetcher, "fetch_museums_bolivia"):
            # signature: fetch_museums_bolivia(output_geojson, limit=...)
            returned = fetcher.fetch_museums_bolivia(nodes_path)
            # plugin returns the path it wrote
            nodes_file = returned or nodes_path
        elif hasattr(fetcher, "fetch_museums"):
            returned = fetcher.fetch_museums(nodes_path)
            nodes_file = returned or nodes_path
        else:
            raise AttributeError("No known fetch function in wikidata plugin (expected fetch_museums_bolivia or fetch_museums)")
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": f"Failed during fetch: {e}", "traceback": tb})

    if not os.path.exists(nodes_file):
        raise HTTPException(status_code=500, detail={"error": "Fetcher did not produce nodes file", "path": nodes_file})

    # 2) Determine network path (we keep it as a path because compute expects a path)
    network_path = network or DEFAULT_NETWORK
    if not os.path.exists(network_path):
        raise HTTPException(status_code=400, detail={"error": f"Network file not found: {network_path}"})

    # 3) Call compute.shortest_path with file paths
    try:
        if hasattr(compute, "shortest_path"):
            route_result = compute.shortest_path(nodes_file, network_path, src, dst)
        else:
            raise AttributeError("Plugin has no function 'shortest_path'")
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": f"Failed during compute: {e}", "traceback": tb})

    # 4) Load nodes and network JSON to return along with route_result
    try:
        with open(nodes_file, "r", encoding="utf-8") as fh:
            nodes_json = json.load(fh)
    except Exception:
        nodes_json = None

    try:
        with open(network_path, "r", encoding="utf-8") as fh:
            network_json = json.load(fh)
    except Exception:
        network_json = None

    # route_result may already contain 'route_geojson' or be a GeoJSON itself
    return JSONResponse(content={"nodes": nodes_json, "network": network_json, "route": route_result})


@app.get("/plugins")
async def list_plugins():
    """List all available plugins and their capabilities."""
    try:
        from src.core.services.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        # Get data fetcher plugins
        data_fetchers = manager.list_data_fetchers()
        
        # Get other plugin types
        formatters = list(manager.formatters.keys())
        compute_drivers = list(manager.compute_drivers.keys())
        persistence_plugins = list(manager.persistence_plugins.keys())
        
        return JSONResponse(content={
            "success": True,
            "plugins": {
                "data_fetchers": data_fetchers,
                "formatters": formatters,
                "compute_drivers": compute_drivers,
                "persistence_plugins": persistence_plugins
            },
            "total_plugins": len(data_fetchers) + len(formatters) + len(compute_drivers) + len(persistence_plugins)
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to list plugins: {e}",
                "traceback": tb
            }
        )


@app.get("/plugins/data-fetchers")
async def list_data_fetcher_plugins():
    """List all data fetcher plugins and their available methods."""
    try:
        from src.core.services.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        data_fetchers = manager.list_data_fetchers()
        
        return JSONResponse(content={
            "success": True,
            "data_fetchers": data_fetchers,
            "total_fetchers": len(data_fetchers)
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to list data fetcher plugins: {e}",
                "traceback": tb
            }
        )


@app.get("/plugins/data-fetchers/{plugin_name}")
async def get_data_fetcher_plugin_info(plugin_name: str):
    """Get detailed information about a specific data fetcher plugin."""
    try:
        from src.core.services.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        plugin = manager.get_data_fetcher(plugin_name)
        if not plugin:
            raise HTTPException(
                status_code=404,
                detail={"error": f"Data fetcher plugin '{plugin_name}' not found"}
            )
        
        methods = plugin.get_available_methods()
        
        return JSONResponse(content={
            "success": True,
            "plugin": {
                "name": plugin_name,
                "class": plugin.__class__.__name__,
                "methods": methods,
                "total_methods": len(methods)
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to get plugin info for '{plugin_name}': {e}",
                "traceback": tb
            }
        )


@app.post("/plugins/data-fetchers/{plugin_name}/{method_name}")
async def execute_plugin_method(
    plugin_name: str,
    method_name: str,
    payload: dict = {}
):
    """
    Execute a specific method of a data fetcher plugin.
    
    The payload should contain the parameters required by the method.
    Use GET /plugins/data-fetchers/{plugin_name} to see available methods and parameters.
    """
    try:
        from src.core.services.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        plugin = manager.get_data_fetcher(plugin_name)
        if not plugin:
            raise HTTPException(
                status_code=404,
                detail={"error": f"Data fetcher plugin '{plugin_name}' not found"}
            )
        
        # Validate method exists
        if method_name not in plugin.get_available_methods():
            available_methods = list(plugin.get_available_methods().keys())
            raise HTTPException(
                status_code=400,
                detail={
                    "error": f"Method '{method_name}' not found in plugin '{plugin_name}'",
                    "available_methods": available_methods
                }
            )
        
        # Execute the method
        result = plugin.execute_method(method_name, **payload)
        
        return JSONResponse(content={
            "success": True,
            "plugin": plugin_name,
            "method": method_name,
            "result": result
        })
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to execute method '{method_name}' on plugin '{plugin_name}': {e}",
                "traceback": tb
            }
        )


@app.get("/plugins/data-fetchers/{plugin_name}/{method_name}")
async def get_plugin_method_info(plugin_name: str, method_name: str):
    """Get detailed information about a specific method of a plugin."""
    try:
        from src.core.services.plugin_manager import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        plugin = manager.get_data_fetcher(plugin_name)
        if not plugin:
            raise HTTPException(
                status_code=404,
                detail={"error": f"Data fetcher plugin '{plugin_name}' not found"}
            )
        
        method_info = plugin.get_method_info(method_name)
        if not method_info:
            available_methods = list(plugin.get_available_methods().keys())
            raise HTTPException(
                status_code=404,
                detail={
                    "error": f"Method '{method_name}' not found in plugin '{plugin_name}'",
                    "available_methods": available_methods
                }
            )
        
        return JSONResponse(content={
            "success": True,
            "plugin": plugin_name,
            "method": method_name,
            "info": method_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to get method info for '{plugin_name}.{method_name}': {e}",
                "traceback": tb
            }
        )


@app.get("/assets")
async def list_assets(
    source: Optional[str] = Query(None, description="Filter by source (e.g., 'wikidata')"),
    limit: int = Query(50, description="Maximum number of assets to return")
):
    """List all available assets in the catalog."""
    try:
        from src.adapters.persistence.local_persistence import LocalPersistence
        
        persistence = LocalPersistence()
        catalog = persistence.load_catalog()
        assets = catalog.get("assets", [])
        
        # Filter by source if specified
        if source:
            assets = [a for a in assets if a.get("source") == source]
        
        # Limit results
        assets = assets[-limit:]  # Get most recent
        
        # Prepare response with essential info
        assets_info = []
        for asset in assets:
            asset_info = {
                "id": asset.get("id"),
                "title": asset.get("title"),
                "description": asset.get("description"),
                "source": asset.get("source"),
                "created_at": asset.get("created_at"),
                "results_count": asset.get("results_count"),
                "data_uri": asset.get("data_uri"),
                "descriptor_uri": asset.get("descriptor_uri")
            }
            
            # Add dictionary URI if available
            if "data_dictionary_uri" in asset:
                asset_info["dictionary_uri"] = asset["data_dictionary_uri"]
                
            assets_info.append(asset_info)
        
        return JSONResponse(content={
            "success": True,
            "assets": assets_info,
            "total_assets": len(assets_info),
            "filtered_by_source": source
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to list assets: {e}",
                "traceback": tb
            }
        )


@app.get("/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Get detailed information about a specific asset including its data."""
    try:
        from src.adapters.persistence.local_persistence import LocalPersistence
        import json
        
        persistence = LocalPersistence()
        catalog = persistence.load_catalog()
        assets = catalog.get("assets", [])
        
        # Find asset by ID
        target_asset = None
        for asset in assets:
            if asset.get("id") == asset_id:
                target_asset = asset
                break
        
        if not target_asset:
            raise HTTPException(
                status_code=404,
                detail={"error": f"Asset '{asset_id}' not found"}
            )
        
        # Load data if available
        data = None
        if target_asset.get("data_uri"):
            try:
                with open(target_asset["data_uri"], 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                data = {"error": "Could not load data file"}
        
        # Load data dictionary if available
        data_dictionary = None
        if target_asset.get("data_dictionary_uri"):
            try:
                with open(target_asset["data_dictionary_uri"], 'r', encoding='utf-8') as f:
                    data_dictionary = json.load(f)
            except Exception:
                data_dictionary = {"error": "Could not load data dictionary"}
        
        return JSONResponse(content={
            "success": True,
            "asset": target_asset,
            "data": data,
            "data_dictionary": data_dictionary
        })
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to get asset '{asset_id}': {e}",
                "traceback": tb
            }
        )


@app.get("/kg/search")
async def search_knowledge_graph(
    query: str = Query(..., description="Search term for entities in the knowledge graph"),
    limit: int = Query(default=20, description="Maximum number of results"),
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type")
):
    """Search entities in the knowledge graph by name, description, or properties."""
    try:
        # Load knowledge graph
        kg_path = os.path.join(os.getcwd(), "data_store", "kg.json")
        
        if not os.path.exists(kg_path):
            raise HTTPException(status_code=404, detail="Knowledge graph not found")
        
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        # Search through entities
        search_results = []
        query_lower = query.lower()
        
        for entity_id, entity_data in kg_data.items():
            # Skip if entity_type filter is specified and doesn't match
            if entity_type and entity_data.get("type") != entity_type:
                continue
            
            # Search in various fields
            searchable_text = ""
            
            # Add title and description
            if "title" in entity_data:
                searchable_text += f" {entity_data['title']}"
            if "description" in entity_data:
                searchable_text += f" {entity_data['description']}"
            if "owner" in entity_data:
                searchable_text += f" {entity_data['owner']}"
            
            # Add metadata fields
            if "metadata" in entity_data and isinstance(entity_data["metadata"], dict):
                for key, value in entity_data["metadata"].items():
                    searchable_text += f" {key} {value}"
            
            # Add properties if they exist
            if "properties" in entity_data and isinstance(entity_data["properties"], dict):
                for key, value in entity_data["properties"].items():
                    searchable_text += f" {key} {value}"
            
            # Check if query matches
            if query_lower in searchable_text.lower():
                result_entity = {
                    "kg_id": entity_id,
                    "entity_data": entity_data,
                    "relevance_score": calculate_relevance_score(query_lower, searchable_text.lower()),
                    "summary": create_entity_summary(entity_data)
                }
                search_results.append(result_entity)
        
        # Sort by relevance and limit results
        search_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        search_results = search_results[:limit]
        
        return JSONResponse(content={
            "query": query,
            "total_results": len(search_results),
            "results": search_results,
            "available_types": list(set(entity.get("type", "unknown") for entity in kg_data.values()))
        })
        
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to search knowledge graph: {e}",
                "traceback": tb
            }
        )


@app.get("/kg/entity/{entity_id}")
async def get_entity_details(entity_id: str, include_related: bool = Query(default=True)):
    """Get detailed information about a specific entity and its relationships."""
    try:
        # Load knowledge graph
        kg_path = os.path.join(os.getcwd(), "data_store", "kg.json")
        
        if not os.path.exists(kg_path):
            raise HTTPException(status_code=404, detail="Knowledge graph not found")
        
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        if entity_id not in kg_data:
            raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in knowledge graph")
        
        entity = kg_data[entity_id]
        
        result = {
            "entity_id": entity_id,
            "entity_data": entity,
            "summary": create_entity_summary(entity),
            "related_entities": [],
            "files_and_datasets": [],
            "processes": []
        }
        
        if include_related:
            # Find related entities
            related_entities = find_related_entities(entity_id, entity, kg_data)
            result["related_entities"] = related_entities
            
            # Extract file references
            if "storage_refs" in entity:
                for ref in entity["storage_refs"]:
                    result["files_and_datasets"].append({
                        "uri": ref.get("uri"),
                        "kind": ref.get("kind"),
                        "exists": check_file_exists(ref.get("uri"))
                    })
            
            # Find processes that used or generated this entity
            processes = find_related_processes(entity_id, entity, kg_data)
            result["processes"] = processes
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to get entity details: {e}",
                "traceback": tb
            }
        )


def calculate_relevance_score(query, text):
    """Calculate relevance score for search results."""
    if query in text:
        # Exact match gets higher score
        score = 100
        # Bonus for title/description matches
        if query in text[:100]:  # Assuming title/description come first
            score += 50
        return score
    
    # Partial word matches
    query_words = query.split()
    text_words = text.split()
    matches = sum(1 for word in query_words if any(word in text_word for text_word in text_words))
    
    return matches * 10


def create_entity_summary(entity):
    """Create a summary description of an entity."""
    summary = {
        "type": entity.get("type", "unknown"),
        "title": entity.get("title", "No title"),
        "description": entity.get("description", "No description")[:200] + "..." if len(entity.get("description", "")) > 200 else entity.get("description", "No description"),
        "created_at": entity.get("created_at"),
        "owner": entity.get("owner")
    }
    
    # Add specific information based on type
    if entity.get("type") == "process_instance":
        summary["process_class"] = entity.get("process_class_id")
        summary["status"] = entity.get("status")
        summary["parameters"] = entity.get("parameters", {})
    
    return summary


def find_related_entities(target_id, target_entity, kg_data):
    """Find entities related to the target entity."""
    related = []
    
    for entity_id, entity in kg_data.items():
        if entity_id == target_id:
            continue
        
        relationship_type = None
        
        # Check if this entity references the target
        if "id" in target_entity and entity.get("id") == target_entity["id"]:
            relationship_type = "same_asset"
        
        # Check process relationships
        if entity.get("type") == "process_instance":
            # Check if target is in parameters
            params = entity.get("parameters", {})
            if target_entity.get("id") in str(params):
                relationship_type = "used_in_process"
            
            # Check if target is in produced datasets
            produced = entity.get("produced_datasets", [])
            if target_entity.get("id") in produced:
                relationship_type = "produced_by_process"
        
        # Check provenance relationships
        if "provenance" in entity:
            prov = entity["provenance"]
            if prov and "derived_from" in prov and target_entity.get("id") in prov.get("derived_from", []):
                relationship_type = "derived_from"
        
        if relationship_type:
            related.append({
                "entity_id": entity_id,
                "relationship": relationship_type,
                "summary": create_entity_summary(entity)
            })
    
    return related


def find_related_processes(target_id, target_entity, kg_data):
    """Find processes that are related to the target entity."""
    processes = []
    
    for entity_id, entity in kg_data.items():
        if entity.get("type") != "process_instance":
            continue
        
        # Check if target entity is used as input
        params = entity.get("parameters", {})
        if target_entity.get("id") in str(params):
            processes.append({
                "process_id": entity_id,
                "relationship": "input_to_process",
                "process_class": entity.get("process_class_id"),
                "status": entity.get("status"),
                "executed_at": entity.get("started_at")
            })
        
        # Check if target entity is produced by this process
        produced = entity.get("produced_datasets", [])
        if target_entity.get("id") in produced:
            processes.append({
                "process_id": entity_id,
                "relationship": "output_of_process",
                "process_class": entity.get("process_class_id"),
                "status": entity.get("status"),
                "executed_at": entity.get("started_at")
            })
    
    return processes


def check_file_exists(uri):
    """Check if a file referenced in the KG actually exists."""
    if not uri:
        return False
    
    try:
        if uri.startswith("file://"):
            # Remove file:// prefix and resolve path
            file_path = uri[7:]
            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)
            return os.path.exists(file_path)
        elif uri.startswith("file:///"):
            # Absolute file path
            file_path = uri[8:]
            return os.path.exists(file_path)
        else:
            # HTTP URLs or other schemes
            return False  # Could implement HTTP HEAD request check
    except:
        return False


def get_kg_path():
    """Get the path to the Knowledge Graph file"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(base_dir, "data_store", "kg.json")


@app.get("/search/entity/{entity_id}")
async def search_by_entity(entity_id: str, radius_km: float = Query(default=50.0), 
                          include_museums: bool = Query(default=True),
                          include_transport: bool = Query(default=True)):
    """Search for all places and features related to a geographic entity.
    
    Args:
        entity_id: Wikidata ID or name of the geographic entity (e.g., Q2882, "La Paz")
        radius_km: Search radius in kilometers from the entity center
        include_museums: Include museums in the search results
        include_transport: Include transport networks in the search results
    """
    try:
        # Import required modules
        import importlib
        import json
        from pathlib import Path
        
        # Entity coordinates mapping (expandable from Wikidata)
        entity_coords = {
            "Q2882": {"name": "La Paz", "lat": -16.5, "lng": -68.15},  # La Paz
            "Q5119": {"name": "Santa Cruz", "lat": -17.78, "lng": -63.18},  # Santa Cruz
            "Q4844": {"name": "Cochabamba", "lat": -17.39, "lng": -66.16},  # Cochabamba
            "Q5138": {"name": "Potosí", "lat": -19.59, "lng": -65.75},  # Potosí
            "Q2874": {"name": "Oruro", "lat": -17.97, "lng": -67.11},  # Oruro
            "Q5117": {"name": "Sucre", "lat": -19.05, "lng": -65.26},  # Sucre
            "Q5146": {"name": "Tarija", "lat": -21.53, "lng": -64.73},  # Tarija
            "Q3902": {"name": "Trinidad", "lat": -14.83, "lng": -64.90},  # Trinidad
            "Q2873": {"name": "Cobija", "lat": -11.03, "lng": -68.77},  # Cobija
        }
        
        # Try to find entity coordinates
        center_coords = None
        entity_name = entity_id
        
        if entity_id in entity_coords:
            center_coords = entity_coords[entity_id]
            entity_name = center_coords["name"]
        else:
            # Try to find by name (case insensitive)
            for eid, data in entity_coords.items():
                if data["name"].lower() == entity_id.lower():
                    center_coords = data
                    entity_name = data["name"]
                    break
        
        if not center_coords:
            raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found in geographic database")
        
        results = {
            "entity": {
                "id": entity_id,
                "name": entity_name,
                "coordinates": [center_coords["lng"], center_coords["lat"]],
                "search_radius_km": radius_km
            },
            "museums": None,
            "transport_networks": [],
            "statistics": {
                "total_museums": 0,
                "total_transport_features": 0,
                "search_area_km2": 3.14159 * radius_km * radius_km
            }
        }
        
        # Search for museums if requested
        if include_museums:
            try:
                fetcher = importlib.import_module("plugins.wikidata_plugin.wikidata_fetcher")
                
                # Create temporary file for museums
                tmpdir = os.path.join(os.getcwd(), "tmp")
                os.makedirs(tmpdir, exist_ok=True)
                museums_path = os.path.join(tmpdir, f"museums_search_{uuid.uuid4().hex}.geojson")
                
                # Fetch museums
                fetcher.fetch_museums_bolivia(museums_path, limit=200)
                
                with open(museums_path, 'r', encoding='utf-8') as f:
                    all_museums = json.load(f)
                
                # Filter museums within radius
                filtered_museums = filter_features_by_distance(
                    all_museums, center_coords["lat"], center_coords["lng"], radius_km
                )
                
                results["museums"] = filtered_museums
                results["statistics"]["total_museums"] = len(filtered_museums.get("features", []))
                
                # Cleanup
                os.remove(museums_path)
                
            except Exception as e:
                results["museums"] = {"error": f"Failed to fetch museums: {e}"}
        
        # Search for transport networks if requested
        if include_transport:
            try:
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                datasets_dir = os.path.join(base_dir, "dummy_datasets")
                
                transport_files = [
                    {"file": "rutas_recorridos_2025.geojson", "name": "Rutas de Transporte Público"},
                    {"file": "puma_katari.geojson", "name": "Red Puma Katari"},
                    {"file": "lineasteleferico.geojson", "name": "Líneas de Teleférico"},
                    {"file": "vias_gamlp_catastro.geojson", "name": "Vías GAMLP"},
                    {"file": "caminos_igm250000.geojson", "name": "Caminos IGM"}
                ]
                
                for transport_info in transport_files:
                    file_path = os.path.join(datasets_dir, transport_info["file"])
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                transport_data = json.load(f)
                            
                            # Filter transport features within radius
                            filtered_transport = filter_features_by_distance(
                                transport_data, center_coords["lat"], center_coords["lng"], radius_km
                            )
                            
                            if filtered_transport.get("features"):
                                results["transport_networks"].append({
                                    "name": transport_info["name"],
                                    "file": transport_info["file"],
                                    "data": filtered_transport,
                                    "feature_count": len(filtered_transport["features"])
                                })
                                
                                results["statistics"]["total_transport_features"] += len(filtered_transport["features"])
                        
                        except Exception as e:
                            results["transport_networks"].append({
                                "name": transport_info["name"],
                                "file": transport_info["file"],
                                "error": f"Failed to load: {e}"
                            })
            
            except Exception as e:
                results["transport_networks"] = [{"error": f"Failed to search transport: {e}"}]
        
        return JSONResponse(content=results)
        
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Failed to search entity '{entity_id}': {e}",
                "traceback": tb
            }
        )


def filter_features_by_distance(geojson_data, center_lat, center_lng, radius_km):
    """Filter GeoJSON features within a certain distance from a center point."""
    import math
    
    def haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate the great circle distance between two points on Earth."""
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def get_feature_center(feature):
        """Get the center coordinates of a feature."""
        geom = feature.get("geometry", {})
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])
        
        if geom_type == "Point":
            return coords[1], coords[0]  # lat, lng
        elif geom_type == "LineString":
            if coords:
                # Use the middle point of the line
                mid_idx = len(coords) // 2
                return coords[mid_idx][1], coords[mid_idx][0]
        elif geom_type == "Polygon":
            if coords and coords[0]:
                # Use the first point of the polygon
                return coords[0][0][1], coords[0][0][0]
        elif geom_type == "MultiLineString":
            if coords and coords[0]:
                mid_idx = len(coords[0]) // 2
                return coords[0][mid_idx][1], coords[0][mid_idx][0]
        
        return None, None
    
    if not geojson_data or "features" not in geojson_data:
        return {"type": "FeatureCollection", "features": []}
    
    filtered_features = []
    
    for feature in geojson_data["features"]:
        feat_lat, feat_lng = get_feature_center(feature)
        
        if feat_lat is not None and feat_lng is not None:
            distance = haversine_distance(center_lat, center_lng, feat_lat, feat_lng)
            
            if distance <= radius_km:
                # Add distance to feature properties
                if "properties" not in feature:
                    feature["properties"] = {}
                feature["properties"]["distance_from_center_km"] = round(distance, 2)
                filtered_features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": filtered_features,
        "metadata": {
            "center": [center_lng, center_lat],
            "radius_km": radius_km,
            "total_features": len(filtered_features)
        }
    }


@app.get("/search/entities")
async def list_available_entities():
    """List all available geographic entities for search."""
    entities = {
        "Q2882": {"name": "La Paz", "type": "city", "coordinates": [-68.15, -16.5]},
        "Q5119": {"name": "Santa Cruz", "type": "city", "coordinates": [-63.18, -17.78]},
        "Q4844": {"name": "Cochabamba", "type": "city", "coordinates": [-66.16, -17.39]},
        "Q5138": {"name": "Potosí", "type": "city", "coordinates": [-65.75, -19.59]},
        "Q2874": {"name": "Oruro", "type": "city", "coordinates": [-67.11, -17.97]},
        "Q5117": {"name": "Sucre", "type": "city", "coordinates": [-65.26, -19.05]},
        "Q5146": {"name": "Tarija", "type": "city", "coordinates": [-64.73, -21.53]},
        "Q3902": {"name": "Trinidad", "type": "city", "coordinates": [-64.90, -14.83]},
        "Q2873": {"name": "Cobija", "type": "city", "coordinates": [-68.77, -11.03]},
    }
    
    return JSONResponse(content={
        "entities": entities,
        "total": len(entities),
        "usage": "Use /search/entity/{entity_id} to search for places related to an entity"
    })


@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serve static files from dummy_datasets directory for layer loading."""
    import os
    
    # Security: Only allow certain file extensions
    allowed_extensions = ['.geojson', '.json', '.csv']
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="File type not allowed")
    
    # Check in dummy_datasets directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    file_path = os.path.join(base_dir, "dummy_datasets", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


# ============================================================================
# ENHANCED KNOWLEDGE GRAPH ENDPOINTS - Generalista como Wikidata propio
# ============================================================================

@app.get("/kg/entities/external")
async def search_external_entities(
    query: str = Query(..., description="Término de búsqueda"),
    source: str = Query("wikidata", description="Fuente externa (wikidata, dbpedia, etc.)"),
    limit: int = Query(10, description="Límite de resultados")
):
    """Buscar entidades en knowledge graphs externos (Wikidata, DBpedia, etc.)"""
    try:
        if source == "wikidata":
            results = await search_wikidata_entities(query, limit)
        elif source == "dbpedia":
            results = await search_dbpedia_entities(query, limit)
        else:
            raise HTTPException(status_code=400, detail=f"Fuente no soportada: {source}")
        
        return JSONResponse(content={
            "query": query,
            "source": source,
            "results": results,
            "count": len(results)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error buscando entidades externas: {e}")

@app.post("/kg/entities/{entity_id}/link")
async def link_external_entity(
    entity_id: str,
    external_link: dict
):
    """Vincular una entidad local con una entidad externa"""
    try:
        # Validar estructura del link externo
        required_fields = ["external_id", "source", "confidence", "relation_type"]
        if not all(field in external_link for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Link externo debe contener: {required_fields}")
        
        # Cargar KG
        kg_path = get_kg_path()
        if not os.path.exists(kg_path):
            raise HTTPException(status_code=404, detail="Knowledge Graph no encontrado")
        
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        # Verificar que la entidad existe
        if entity_id not in kg_data:
            raise HTTPException(status_code=404, detail="Entidad no encontrada")
        
        # Agregar/actualizar links externos
        if "external_links" not in kg_data[entity_id]:
            kg_data[entity_id]["external_links"] = []
        
        # Evitar duplicados
        existing_link = next(
            (link for link in kg_data[entity_id]["external_links"] 
             if link["external_id"] == external_link["external_id"] and link["source"] == external_link["source"]),
            None
        )
        
        if existing_link:
            existing_link.update(external_link)
        else:
            kg_data[entity_id]["external_links"].append(external_link)
        
        # Agregar timestamp
        kg_data[entity_id]["_updated_at"] = datetime.now().isoformat()
        
        # Guardar KG actualizado
        with open(kg_path, 'w', encoding='utf-8') as f:
            json.dump(kg_data, f, indent=2, ensure_ascii=False)
        
        return JSONResponse(content={
            "entity_id": entity_id,
            "external_link": external_link,
            "status": "linked"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error vinculando entidad externa: {e}")

@app.post("/kg/describe/dataset")
async def describe_dataset_columns(
    dataset_info: dict
):
    """Describir automáticamente las columnas de un dataset usando el KG"""
    try:
        # Validar entrada
        if "dataset_path" not in dataset_info and "columns" not in dataset_info:
            raise HTTPException(status_code=400, detail="Se requiere dataset_path o columns")
        
        columns = dataset_info.get("columns", [])
        
        # Si se proporciona un path, extraer columnas
        if "dataset_path" in dataset_info and not columns:
            dataset_path = dataset_info["dataset_path"]
            columns = extract_columns_from_dataset(dataset_path)
        
        # Describir columnas usando KG
        descriptions = await describe_columns_with_kg(columns)
        
        # Buscar entidades relacionadas en KG externo si es necesario
        enhanced_descriptions = await enhance_descriptions_with_external_kg(descriptions)
        
        return JSONResponse(content={
            "dataset_path": dataset_info.get("dataset_path"),
            "columns": columns,
            "descriptions": enhanced_descriptions,
            "analysis_timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error describiendo dataset: {e}")

@app.post("/kg/entities/create")
async def create_enhanced_entity(
    entity_data: dict
):
    """Crear una nueva entidad en el KG con estructura generalista"""
    try:
        # Validar estructura mínima
        required_fields = ["title", "type", "description"]
        if not all(field in entity_data for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Entidad debe contener: {required_fields}")
        
        # Generar ID único
        entity_id = str(uuid.uuid4())
        
        # Estructura generalista de entidad
        new_entity = {
            "id": entity_id,
            "title": entity_data["title"],
            "type": entity_data["type"],  # ej: "Person", "Place", "Organization", "Dataset", "Concept"
            "description": entity_data["description"],
            "aliases": entity_data.get("aliases", []),
            "properties": entity_data.get("properties", {}),
            "external_links": entity_data.get("external_links", []),
            "relationships": entity_data.get("relationships", []),
            "provenance": {
                "created_by": entity_data.get("created_by", "system"),
                "created_at": datetime.now().isoformat(),
                "source": entity_data.get("source", "manual"),
                "confidence": entity_data.get("confidence", 1.0)
            },
            "metadata": entity_data.get("metadata", {}),
            "tags": entity_data.get("tags", []),
            "_indexed_at": datetime.now().isoformat()
        }
        
        # Cargar KG existente
        kg_path = get_kg_path()
        kg_data = {}
        if os.path.exists(kg_path):
            with open(kg_path, 'r', encoding='utf-8') as f:
                kg_data = json.load(f)
        
        # Agregar nueva entidad
        kg_data[entity_id] = new_entity
        
        # Guardar KG actualizado
        with open(kg_path, 'w', encoding='utf-8') as f:
            json.dump(kg_data, f, indent=2, ensure_ascii=False)
        
        return JSONResponse(content={
            "entity_id": entity_id,
            "entity": new_entity,
            "status": "created"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando entidad: {e}")

@app.get("/kg/analyze/dataset/{dataset_id}")
async def analyze_dataset_context(
    dataset_id: str,
    auto_enhance: bool = Query(False, description="Mejorar automáticamente con KG externo")
):
    """Analizar el contexto de un dataset usando el KG propio y externo"""
    try:
        # Buscar dataset en el KG
        kg_path = get_kg_path()
        if not os.path.exists(kg_path):
            raise HTTPException(status_code=404, detail="Knowledge Graph no encontrado")
        
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
        
        # Buscar el dataset
        dataset_entity = None
        for entity_id, entity_data in kg_data.items():
            if entity_id == dataset_id or entity_data.get("id") == dataset_id:
                dataset_entity = entity_data
                break
        
        if not dataset_entity:
            raise HTTPException(status_code=404, detail="Dataset no encontrado en KG")
        
        # Analizar contexto
        context_analysis = {
            "dataset_info": dataset_entity,
            "related_entities": find_related_entities(kg_data, dataset_id),
            "column_analysis": None,
            "semantic_context": None,
            "external_enrichment": None
        }
        
        # Si tiene archivos, analizar columnas
        storage_refs = dataset_entity.get("storage_refs", [])
        if storage_refs:
            for ref in storage_refs:
                if ref.get("kind") == "local" and ref.get("uri"):
                    file_path = ref["uri"].replace("file://", "")
                    if file_path.endswith(".csv"):
                        try:
                            columns = extract_columns_from_dataset(file_path)
                            context_analysis["column_analysis"] = await describe_columns_with_kg(columns)
                        except Exception as e:
                            context_analysis["column_analysis"] = {"error": str(e)}
                        break
        
        # Auto-enhancement con KG externo
        if auto_enhance:
            context_analysis["external_enrichment"] = await enhance_dataset_with_external_kg(dataset_entity)
        
        return JSONResponse(content=context_analysis)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analizando dataset: {e}")


# ============================================================================
# FUNCIONES AUXILIARES PARA KG GENERALISTA
# ============================================================================

async def search_wikidata_entities(query: str, limit: int = 10):
    """Buscar entidades en Wikidata"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # API de búsqueda de Wikidata
            url = f"https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbsearchentities",
                "search": query,
                "language": "es",
                "format": "json",
                "limit": limit
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    
                    for item in data.get("search", []):
                        result = {
                            "external_id": item.get("id"),
                            "title": item.get("label"),
                            "description": item.get("description"),
                            "url": item.get("concepturi"),
                            "source": "wikidata",
                            "match_score": 1.0
                        }
                        results.append(result)
                    
                    return results
                else:
                    return []
    except Exception as e:
        print(f"Error buscando en Wikidata: {e}")
        return []

async def search_dbpedia_entities(query: str, limit: int = 10):
    """Buscar entidades en DBpedia"""
    # Implementación básica para DBpedia
    return [{
        "external_id": f"dbpedia:{query}",
        "title": query,
        "description": f"Entidad DBpedia para {query}",
        "url": f"http://dbpedia.org/resource/{query}",
        "source": "dbpedia",
        "match_score": 0.8
    }]

def extract_columns_from_dataset(file_path: str):
    """Extraer nombres de columnas de un dataset"""
    try:
        if file_path.startswith("file://"):
            file_path = file_path[7:]
        
        # Resolver path relativo
        if not os.path.isabs(file_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            file_path = os.path.join(base_dir, file_path)
        
        if file_path.endswith('.csv'):
            import pandas as pd
            df = pd.read_csv(file_path, nrows=0)  # Solo headers
            return list(df.columns)
        elif file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return list(data[0].keys())
                elif isinstance(data, dict):
                    return list(data.keys())
        
        return []
    except Exception as e:
        print(f"Error extrayendo columnas: {e}")
        return []

async def describe_columns_with_kg(columns: list):
    """Describir columnas usando el KG local"""
    descriptions = {}
    
    # Cargar KG
    kg_path = get_kg_path()
    kg_data = {}
    if os.path.exists(kg_path):
        with open(kg_path, 'r', encoding='utf-8') as f:
            kg_data = json.load(f)
    
    for column in columns:
        description = {
            "column_name": column,
            "inferred_type": infer_column_type(column),
            "semantic_meaning": infer_semantic_meaning(column, kg_data),
            "related_entities": find_entities_for_column(column, kg_data),
            "suggested_description": generate_column_description(column, kg_data)
        }
        descriptions[column] = description
    
    return descriptions

def infer_column_type(column_name: str):
    """Inferir el tipo de una columna por su nombre"""
    column_lower = column_name.lower()
    
    # Patrones comunes
    if any(pattern in column_lower for pattern in ['id', '_id', 'uuid', 'key']):
        return "identifier"
    elif any(pattern in column_lower for pattern in ['name', 'nombre', 'title', 'titulo']):
        return "text/name"
    elif any(pattern in column_lower for pattern in ['date', 'fecha', 'time', 'timestamp']):
        return "temporal"
    elif any(pattern in column_lower for pattern in ['lat', 'lon', 'latitude', 'longitude', 'coord']):
        return "geographic"
    elif any(pattern in column_lower for pattern in ['price', 'cost', 'amount', 'value', 'precio']):
        return "numeric/monetary"
    elif any(pattern in column_lower for pattern in ['email', 'mail']):
        return "contact/email"
    elif any(pattern in column_lower for pattern in ['phone', 'tel', 'telefono']):
        return "contact/phone"
    elif any(pattern in column_lower for pattern in ['url', 'link', 'website']):
        return "web/url"
    else:
        return "general"

def infer_semantic_meaning(column_name: str, kg_data: dict):
    """Inferir el significado semántico usando el KG"""
    column_lower = column_name.lower()
    semantic_matches = []
    
    # Buscar en títulos y descripciones del KG
    for entity_id, entity_data in kg_data.items():
        title = (entity_data.get("title") or "").lower()
        description = (entity_data.get("description") or "").lower()
        
        if column_lower in title or title in column_lower:
            semantic_matches.append({
                "entity_id": entity_id,
                "match_type": "title",
                "confidence": 0.9,
                "entity_title": entity_data.get("title")
            })
        elif column_lower in description or any(word in description for word in column_lower.split('_')):
            semantic_matches.append({
                "entity_id": entity_id,
                "match_type": "description",
                "confidence": 0.6,
                "entity_title": entity_data.get("title")
            })
    
    return semantic_matches

def find_entities_for_column(column_name: str, kg_data: dict):
    """Encontrar entidades relacionadas con una columna"""
    related = []
    column_words = set(re.findall(r'\w+', column_name.lower()))
    
    for entity_id, entity_data in kg_data.items():
        entity_words = set()
        
        # Extraer palabras de la entidad
        if entity_data.get("title"):
            entity_words.update(re.findall(r'\w+', entity_data["title"].lower()))
        if entity_data.get("description"):
            entity_words.update(re.findall(r'\w+', entity_data["description"].lower()))
        
        # Calcular intersección
        common_words = column_words.intersection(entity_words)
        if common_words:
            similarity = len(common_words) / len(column_words.union(entity_words))
            if similarity > 0.3:
                related.append({
                    "entity_id": entity_id,
                    "entity_title": entity_data.get("title"),
                    "similarity": similarity,
                    "common_words": list(common_words)
                })
    
    return sorted(related, key=lambda x: x["similarity"], reverse=True)[:5]

def generate_column_description(column_name: str, kg_data: dict):
    """Generar descripción sugerida para una columna"""
    column_type = infer_column_type(column_name)
    semantic_matches = infer_semantic_meaning(column_name, kg_data)
    
    base_descriptions = {
        "identifier": f"Identificador único para {column_name}",
        "text/name": f"Nombre o título relacionado con {column_name}",
        "temporal": f"Información temporal (fecha/hora) de {column_name}",
        "geographic": f"Coordenada geográfica para {column_name}",
        "numeric/monetary": f"Valor numérico o monetario de {column_name}",
        "contact/email": f"Dirección de correo electrónico",
        "contact/phone": f"Número de teléfono",
        "web/url": f"Enlace web o URL",
        "general": f"Campo de datos relacionado con {column_name}"
    }
    
    description = base_descriptions.get(column_type, f"Campo de datos: {column_name}")
    
    # Mejorar con contexto del KG
    if semantic_matches:
        best_match = semantic_matches[0]
        entity_title = best_match.get("entity_title", "")
        if entity_title:
            description += f". Relacionado con la entidad: {entity_title}"
    
    return description

async def enhance_descriptions_with_external_kg(descriptions: dict):
    """Mejorar descripciones con información de KG externos"""
    enhanced = descriptions.copy()
    
    for column_name, desc in descriptions.items():
        # Buscar en Wikidata para contexto adicional
        if desc["inferred_type"] in ["text/name", "geographic", "general"]:
            try:
                external_results = await search_wikidata_entities(column_name, limit=3)
                if external_results:
                    enhanced[column_name]["external_context"] = external_results
            except Exception as e:
                enhanced[column_name]["external_context"] = {"error": str(e)}
    
    return enhanced

async def enhance_dataset_with_external_kg(dataset_entity: dict):
    """Mejorar información del dataset con KG externo"""
    enhancements = {
        "wikidata_matches": [],
        "suggested_links": [],
        "contextual_entities": []
    }
    
    # Buscar coincidencias en Wikidata
    title = dataset_entity.get("title", "")
    if title:
        try:
            wikidata_results = await search_wikidata_entities(title, limit=5)
            enhancements["wikidata_matches"] = wikidata_results
        except Exception as e:
            enhancements["wikidata_matches"] = {"error": str(e)}
    
    return enhancements


# ============================================================================
# WIKIDATA-COMPATIBLE KNOWLEDGE GRAPH ENDPOINTS
# ============================================================================

@app.get("/wikidata/entities/{entity_id}")
async def get_wikidata_entity(entity_id: str):
    """Obtener una entidad en formato Wikidata desde el KG local"""
    try:
        wikidata_path = get_wikidata_format_path()
        entity_file = os.path.join(wikidata_path, "items", f"{entity_id}.json")
        
        if not os.path.exists(entity_file):
            raise HTTPException(status_code=404, detail=f"Entidad {entity_id} no encontrada")
        
        with open(entity_file, 'r', encoding='utf-8') as f:
            entity_data = json.load(f)
        
        return JSONResponse(content=entity_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo entidad: {e}")

@app.get("/wikidata/properties/{property_id}")
async def get_wikidata_property(property_id: str):
    """Obtener una propiedad en formato Wikidata desde el KG local"""
    try:
        wikidata_path = get_wikidata_format_path()
        property_file = os.path.join(wikidata_path, "properties", f"{property_id}.json")
        
        if not os.path.exists(property_file):
            raise HTTPException(status_code=404, detail=f"Propiedad {property_id} no encontrada")
        
        with open(property_file, 'r', encoding='utf-8') as f:
            property_data = json.load(f)
        
        return JSONResponse(content=property_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo propiedad: {e}")

@app.post("/wikidata/entities")
async def create_wikidata_entity(entity_data: dict):
    """Crear una nueva entidad en formato Wikidata"""
    try:
        # Validar estructura mínima Wikidata
        required_fields = ["id", "type", "labels"]
        if not all(field in entity_data for field in required_fields):
            raise HTTPException(status_code=400, detail=f"Entidad Wikidata debe contener: {required_fields}")
        
        entity_id = entity_data["id"]
        if not entity_id.startswith("Q"):
            raise HTTPException(status_code=400, detail="ID de entidad debe comenzar con 'Q'")
        
        # Completar estructura Wikidata si faltan campos
        wikidata_entity = {
            "id": entity_id,
            "type": entity_data.get("type", "item"),
            "labels": entity_data["labels"],
            "descriptions": entity_data.get("descriptions", {}),
            "aliases": entity_data.get("aliases", {}),
            "claims": entity_data.get("claims", {}),
            "sitelinks": entity_data.get("sitelinks", {}),
            "lastrevid": entity_data.get("lastrevid", 1),
            "modified": entity_data.get("modified", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")),
            "ns": entity_data.get("ns", 0),
            "pageid": entity_data.get("pageid", int(entity_id[1:]) if entity_id[1:].isdigit() else 1),
            "title": entity_id
        }
        
        # Agregar metadatos de interoperabilidad
        if "external_refs" in entity_data:
            wikidata_entity["external_refs"] = entity_data["external_refs"]
        
        # Guardar entidad
        wikidata_path = get_wikidata_format_path()
        os.makedirs(os.path.join(wikidata_path, "items"), exist_ok=True)
        
        entity_file = os.path.join(wikidata_path, "items", f"{entity_id}.json")
        with open(entity_file, 'w', encoding='utf-8') as f:
            json.dump(wikidata_entity, f, indent=2, ensure_ascii=False)
        
        return JSONResponse(content={
            "entity_id": entity_id,
            "status": "created",
            "entity": wikidata_entity
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando entidad Wikidata: {e}")

@app.post("/wikidata/import/{source}")
async def import_external_entity(
    source: str,
    external_id: str = Query(..., description="ID de la entidad externa"),
    create_local_id: bool = Query(True, description="Crear ID local automáticamente")
):
    """Importar una entidad de un KG externo y convertirla a formato Wikidata local"""
    try:
        if source == "wikidata":
            imported_entity = await import_from_wikidata(external_id, create_local_id)
        elif source == "dbpedia":
            imported_entity = await import_from_dbpedia(external_id, create_local_id)
        else:
            raise HTTPException(status_code=400, detail=f"Fuente no soportada: {source}")
        
        return JSONResponse(content={
            "external_id": external_id,
            "source": source,
            "local_id": imported_entity["id"],
            "status": "imported",
            "entity": imported_entity
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importando entidad: {e}")

@app.get("/wikidata/search")
async def search_wikidata_local(
    query: str = Query(..., description="Término de búsqueda"),
    lang: str = Query("es", description="Idioma de búsqueda"),
    limit: int = Query(10, description="Límite de resultados")
):
    """Buscar entidades en el KG local con formato Wikidata"""
    try:
        wikidata_path = get_wikidata_format_path()
        items_path = os.path.join(wikidata_path, "items")
        
        if not os.path.exists(items_path):
            return JSONResponse(content={"query": query, "results": [], "count": 0})
        
        results = []
        query_lower = query.lower()
        
        # Buscar en todos los archivos de entidades
        for filename in os.listdir(items_path):
            if not filename.endswith('.json'):
                continue
                
            entity_file = os.path.join(items_path, filename)
            try:
                with open(entity_file, 'r', encoding='utf-8') as f:
                    entity = json.load(f)
                
                # Buscar en labels
                labels = entity.get("labels", {})
                descriptions = entity.get("descriptions", {})
                aliases = entity.get("aliases", {})
                
                match_score = 0
                matched_text = ""
                
                # Buscar en labels del idioma especificado
                if lang in labels and query_lower in labels[lang]["value"].lower():
                    match_score = 100
                    matched_text = labels[lang]["value"]
                
                # Buscar en descripciones
                elif lang in descriptions and query_lower in descriptions[lang]["value"].lower():
                    match_score = 80
                    matched_text = descriptions[lang]["value"]
                
                # Buscar en aliases
                elif lang in aliases:
                    for alias in aliases[lang]:
                        if query_lower in alias["value"].lower():
                            match_score = 60
                            matched_text = alias["value"]
                            break
                
                # Buscar en cualquier idioma si no se encuentra en el especificado
                if match_score == 0:
                    for l, label_data in labels.items():
                        if query_lower in label_data["value"].lower():
                            match_score = 40
                            matched_text = label_data["value"]
                            break
                
                if match_score > 0:
                    result = {
                        "id": entity["id"],
                        "label": labels.get(lang, {}).get("value", ""),
                        "description": descriptions.get(lang, {}).get("value", ""),
                        "match_score": match_score,
                        "matched_text": matched_text,
                        "url": f"/wikidata/entities/{entity['id']}"
                    }
                    results.append(result)
                    
            except Exception as e:
                print(f"Error procesando {filename}: {e}")
                continue
        
        # Ordenar por score y limitar
        results.sort(key=lambda x: x["match_score"], reverse=True)
        results = results[:limit]
        
        return JSONResponse(content={
            "query": query,
            "language": lang,
            "results": results,
            "count": len(results)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda Wikidata: {e}")

@app.get("/wikidata/entities/{entity_id}/claims/{property_id}")
async def get_entity_claims(entity_id: str, property_id: str):
    """Obtener los claims específicos de una entidad para una propiedad"""
    try:
        entity_data = await get_wikidata_entity(entity_id)
        entity_json = entity_data.body.decode('utf-8')
        entity = json.loads(entity_json)
        
        claims = entity.get("claims", {}).get(property_id, [])
        
        return JSONResponse(content={
            "entity_id": entity_id,
            "property_id": property_id,
            "claims": claims,
            "count": len(claims)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo claims: {e}")

@app.post("/wikidata/convert/legacy")
async def convert_legacy_kg_to_wikidata():
    """Convertir el KG legado al nuevo formato Wikidata"""
    try:
        # Cargar KG legado
        kg_path = get_kg_path()
        if not os.path.exists(kg_path):
            raise HTTPException(status_code=404, detail="KG legado no encontrado")
        
        with open(kg_path, 'r', encoding='utf-8') as f:
            legacy_kg = json.load(f)
        
        converted_entities = []
        next_q_number = await get_next_q_number()
        
        for entity_id, entity_data in legacy_kg.items():
            try:
                # Convertir entidad legada a formato Wikidata
                wikidata_entity = convert_legacy_entity_to_wikidata(entity_data, next_q_number)
                
                # Guardar entidad convertida
                entity_file = os.path.join(get_wikidata_format_path(), "items", f"{wikidata_entity['id']}.json")
                os.makedirs(os.path.dirname(entity_file), exist_ok=True)
                
                with open(entity_file, 'w', encoding='utf-8') as f:
                    json.dump(wikidata_entity, f, indent=2, ensure_ascii=False)
                
                converted_entities.append({
                    "legacy_id": entity_id,
                    "wikidata_id": wikidata_entity['id'],
                    "title": wikidata_entity.get('labels', {}).get('es', {}).get('value', 'Sin título')
                })
                
                next_q_number += 1
                
            except Exception as e:
                print(f"Error convirtiendo entidad {entity_id}: {e}")
                continue
        
        return JSONResponse(content={
            "status": "converted",
            "converted_count": len(converted_entities),
            "entities": converted_entities
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error convirtiendo KG legado: {e}")


# ============================================================================
# FUNCIONES AUXILIARES PARA FORMATO WIKIDATA
# ============================================================================

def get_wikidata_format_path():
    """Obtener la ruta del directorio con formato Wikidata"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    return os.path.join(base_dir, "data_store", "wikidata_format")

async def import_from_wikidata(external_id: str, create_local_id: bool = True):
    """Importar entidad desde Wikidata real"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            # API de entidades de Wikidata
            url = f"https://www.wikidata.org/w/api.php"
            params = {
                "action": "wbgetentities",
                "ids": external_id,
                "format": "json",
                "languages": "es|en"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    entities = data.get("entities", {})
                    
                    if external_id in entities:
                        external_entity = entities[external_id]
                        
                        # Convertir a formato local
                        if create_local_id:
                            local_id = f"Q{await get_next_q_number()}"
                        else:
                            local_id = external_id
                        
                        # Adaptar estructura
                        local_entity = {
                            "id": local_id,
                            "type": "item",
                            "labels": external_entity.get("labels", {}),
                            "descriptions": external_entity.get("descriptions", {}),
                            "aliases": external_entity.get("aliases", {}),
                            "claims": external_entity.get("claims", {}),
                            "sitelinks": external_entity.get("sitelinks", {}),
                            "external_refs": {
                                "wikidata": external_id,
                                "imported_from": "wikidata",
                                "confidence": 1.0,
                                "import_date": datetime.now().isoformat()
                            },
                            "lastrevid": 1,
                            "modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "ns": 0,
                            "pageid": int(local_id[1:]) if local_id[1:].isdigit() else 1,
                            "title": local_id
                        }
                        
                        # Guardar entidad importada
                        entity_file = os.path.join(get_wikidata_format_path(), "items", f"{local_id}.json")
                        os.makedirs(os.path.dirname(entity_file), exist_ok=True)
                        
                        with open(entity_file, 'w', encoding='utf-8') as f:
                            json.dump(local_entity, f, indent=2, ensure_ascii=False)
                        
                        return local_entity
                    else:
                        raise HTTPException(status_code=404, detail=f"Entidad {external_id} no encontrada en Wikidata")
                else:
                    raise HTTPException(status_code=500, detail="Error consultando Wikidata")
                    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importando desde Wikidata: {e}")

async def import_from_dbpedia(external_id: str, create_local_id: bool = True):
    """Importar entidad desde DBpedia (implementación básica)"""
    # Para este ejemplo, crear una entidad básica
    if create_local_id:
        local_id = f"Q{await get_next_q_number()}"
    else:
        local_id = external_id.replace("dbpedia:", "Q")
    
    local_entity = {
        "id": local_id,
        "type": "item",
        "labels": {
            "en": {"value": external_id.replace("dbpedia:", ""), "language": "en"}
        },
        "descriptions": {
            "en": {"value": f"Entity imported from DBpedia: {external_id}", "language": "en"}
        },
        "aliases": {},
        "claims": {},
        "sitelinks": {},
        "external_refs": {
            "dbpedia": external_id,
            "imported_from": "dbpedia",
            "confidence": 0.8,
            "import_date": datetime.now().isoformat()
        },
        "lastrevid": 1,
        "modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ns": 0,
        "pageid": int(local_id[1:]) if local_id[1:].isdigit() else 1,
        "title": local_id
    }
    
    # Guardar entidad importada
    entity_file = os.path.join(get_wikidata_format_path(), "items", f"{local_id}.json")
    os.makedirs(os.path.dirname(entity_file), exist_ok=True)
    
    with open(entity_file, 'w', encoding='utf-8') as f:
        json.dump(local_entity, f, indent=2, ensure_ascii=False)
    
    return local_entity

async def get_next_q_number():
    """Obtener el próximo número Q disponible"""
    wikidata_path = get_wikidata_format_path()
    items_path = os.path.join(wikidata_path, "items")
    
    if not os.path.exists(items_path):
        return 200001  # Empezar con Q200001 para entidades locales
    
    max_q = 200000
    for filename in os.listdir(items_path):
        if filename.startswith("Q") and filename.endswith(".json"):
            try:
                q_number = int(filename[1:-5])  # Extraer número sin Q y .json
                if q_number > max_q:
                    max_q = q_number
            except ValueError:
                continue
    
    return max_q + 1

def convert_legacy_entity_to_wikidata(legacy_entity, q_number):
    """Convertir una entidad del formato legado al formato Wikidata"""
    
    # Determinar el tipo de entidad
    entity_type = legacy_entity.get("type", "item")
    title = legacy_entity.get("title", "Sin título")
    description = legacy_entity.get("description", "")
    
    # Crear estructura Wikidata
    wikidata_entity = {
        "id": f"Q{q_number}",
        "type": "item",
        "labels": {
            "es": {"value": title, "language": "es"}
        },
        "descriptions": {
            "es": {"value": description, "language": "es"}
        },
        "aliases": {},
        "claims": {},
        "sitelinks": {},
        "external_refs": {
            "legacy_id": legacy_entity.get("id", str(q_number)),
            "converted_from": "legacy_kg",
            "conversion_date": datetime.now().isoformat()
        },
        "lastrevid": 1,
        "modified": legacy_entity.get("_indexed_at", datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")),
        "ns": 0,
        "pageid": q_number,
        "title": f"Q{q_number}"
    }
    
    # Convertir campos específicos
    if entity_type == "process_instance":
        wikidata_entity["claims"]["P31"] = [
            {
                "mainsnak": {
                    "snaktype": "value",
                    "property": "P31",
                    "datavalue": {
                        "value": {"id": "Q1914636"},  # proceso
                        "type": "wikibase-entityid"
                    }
                },
                "type": "statement",
                "rank": "normal"
            }
        ]
    
    # Agregar propiedades de storage refs si existen
    storage_refs = legacy_entity.get("storage_refs", [])
    if storage_refs:
        wikidata_entity["claims"]["P856"] = []  # URL oficial
        for ref in storage_refs:
            if ref.get("uri") and ref.get("uri").startswith("http"):
                wikidata_entity["claims"]["P856"].append({
                    "mainsnak": {
                        "snaktype": "value",
                        "property": "P856",
                        "datavalue": {
                            "value": ref["uri"],
                            "type": "string"
                        }
                    },
                    "type": "statement",
                    "rank": "normal"
                })
    
    return wikidata_entity


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
