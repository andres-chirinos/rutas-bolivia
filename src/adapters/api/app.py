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
import importlib
import os
import traceback
import json
import tempfile
import uuid

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
