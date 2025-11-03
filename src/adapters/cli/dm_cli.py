import typer
from typing import Optional, Any
from pathlib import Path

from ...core.services.plugin_manager import PluginManager
from ..persistence.file_adapter import FileAdapter
from ..crypto.signature_adapter import SignatureAdapter
from ...core.services.prov_generator import generate_prov_for_asset
from ..persistence.local_persistence import LocalPersistence
from ...core.services.prov_generator import generate_asset_descriptor_jsonld
from ..network.simple_network import SimpleNetworkAdapter
from ..crypto.signature_adapter import SignatureAdapter
import os


app = typer.Typer()


@app.callback()
def main():
    """dm - Data Mesh lightweight node CLI"""


node_app = typer.Typer()
asset_app = typer.Typer()
compute_app = typer.Typer()
index_app = typer.Typer()
lineage_app = typer.Typer()
plugin_app = typer.Typer()

app.add_typer(node_app, name="node")
app.add_typer(asset_app, name="asset")
app.add_typer(compute_app, name="compute")
app.add_typer(index_app, name="index")
app.add_typer(lineage_app, name="lineage")
app.add_typer(plugin_app, name="plugin")


demo_app = typer.Typer()
app.add_typer(demo_app, name="demo")


@demo_app.command("museums")
def demo_museums(
    nodes: str = typer.Option("museos_bo.geojson", help="Path to nodes GeoJSON (museums)"),
    lines: str = typer.Option("lineaspuma.geojson", help="Path to lines GeoJSON (network)"),
    src: str = typer.Option(..., help="Source node id (properties.id)"),
    dst: str = typer.Option(..., help="Destination node id (properties.id)"),
    out: str = typer.Option("museos_demo.html", help="Output HTML file"),
    fetch: bool = typer.Option(False, help="Fetch latest museums from Wikidata before computing"),
):
    """Demo pipeline: optional fetch -> compute shortest path on lines -> visualize HTML with route."""

    # optional fetch
    if fetch:
        try:
            from plugins.wikidata_plugin.wikidata_fetcher import fetch_museums_bolivia

            typer.echo("Fetching museums from Wikidata...")
            fetch_museums_bolivia(nodes)
        except Exception as e:
            typer.echo(f"Failed to fetch museums: {e}")
            raise typer.Exit(code=2)

    # compute shortest path
    try:
        from plugins.graph_compute.shortest_path import shortest_path

        typer.echo("Computing shortest path on network...")
        res = shortest_path(nodes, lines, src, dst)
        # write route geojson
        import json

        route_file = "route_demo.json"
        with open(route_file, "w", encoding="utf-8") as f:
            json.dump(res["route_geojson"], f, ensure_ascii=False, indent=2)
    except Exception as e:
        typer.echo(f"Failed to compute route: {e}")
        raise typer.Exit(code=3)

    # visualize
    try:
        from plugins.geo_visualizer.visualize import visualize_geojson

        typer.echo("Generating HTML visualization...")
        visualize_geojson(nodes, out, path=None, network_geojson=lines, route_geojson=route_file)
        typer.echo(f"Wrote {out}")
    except Exception as e:
        typer.echo(f"Failed to visualize: {e}")
        raise typer.Exit(code=4)


# --- node commands
@node_app.command("create")
def node_create(base_url: str = typer.Option("http://localhost:8000")):
    fa = FileAdapter()
    node = {"did": "did:example:1234", "base_url": base_url}
    fa.write_json("dcat-fed.json", node)
    typer.echo("Node created: " + node["did"])


@node_app.command("list")
def node_list():
    typer.echo("Discovery not implemented in simple adapter. Use 'dm plugin list' for installed plugins.")


@node_app.command("info")
def node_info():
    fa = FileAdapter()
    info = fa.read_json("dcat-fed.json")
    typer.echo(info)


# --- asset commands
@asset_app.command("publish")
def asset_publish(file: str):
    # extract basic metadata
    # id will be the filename, uuid will be generated for canonical identifier
    asset_path = Path(file)
    asset = {"id": asset_path.name, "title": asset_path.stem}

    # generate prov-o
    prov = generate_prov_for_asset(asset)
    asset["prov"] = prov

    # sign asset
    sig = SignatureAdapter()
    signed = sig.sign(asset)

    # persist via persistence port (local by default)
    persistence = LocalPersistence()
    catalog = persistence.load_catalog()
    catalog.setdefault("assets", []).append(signed)
    persistence.save_catalog(catalog)

    # create and save asset descriptor (JSON-LD) next to the data file
    # store data file under a predictable path inside storage; for the local adapter
    # we treat the provided path as relative to base, and store descriptor alongside it.
    data_rel = str(asset_path)
    # descriptor filename uses uuid
    descriptor = generate_asset_descriptor_jsonld(asset, data_uri=data_rel)
    desc_rel_path = f"descriptors/{asset['uuid']}.jsonld"
    # save in descriptors/ (catalog index)
    persistence.save_asset_descriptor(desc_rel_path, descriptor)

    # also save descriptor next to the data if the data is a local file path
    try:
        if asset_path.exists():
            local_desc_path = asset_path.with_suffix('.jsonld')
            # write using persistence (will resolve relative into base dir)
            persistence.save_asset_descriptor(str(local_desc_path), descriptor)
    except Exception:
        # ignore local-save errors
        pass

    # update catalog entry to reference both data_uri and descriptor_uri
    signed["data_uri"] = data_rel
    # prefer a local-relative descriptor URI when we saved the descriptor locally
    signed["descriptor_uri"] = desc_rel_path
    # replace last catalog entry with these updated references
    catalog["assets"][-1] = signed
    persistence.save_catalog(catalog)

    typer.echo(f"Published asset {asset['id']} and added to local catalog")


@asset_app.command("validate")
def asset_validate(asset_id: str):
    typer.echo(f"Validate not implemented: {asset_id}")


@asset_app.command("verify")
def asset_verify(asset_ref: str):
    """Verify an asset by id or uuid: checks signature and descriptor->data relation.

    Supports local file descriptors, HTTP(S) descriptors (fetched), and leaves
    external schemes (gdrive:...) to plugin implementations (reports as unable to fetch).
    """
    persistence = LocalPersistence()
    catalog = persistence.load_catalog()
    assets = catalog.get("assets", [])

    # find asset by id or uuid
    target = None
    for a in assets:
        if a.get("id") == asset_ref or a.get("uuid") == asset_ref:
            target = a
            break

    if not target:
        typer.echo(f"Asset {asset_ref} not found in local catalog")
        raise typer.Exit(code=2)

    signer = SignatureAdapter()
    sig_ok = signer.verify(target)
    typer.echo(f"Signature valid: {sig_ok}")

    desc_uri = target.get("descriptor_uri")
    data_uri = target.get("data_uri")
    if not desc_uri:
        typer.echo("No descriptor URI found for asset")
        raise typer.Exit(code=3)

    # attempt to load descriptor
    descriptor = None
    # if descriptor looks like http(s) fetch via network adapter
    if str(desc_uri).startswith("http://") or str(desc_uri).startswith("https://"):
        try:
            net = SimpleNetworkAdapter()
            descriptor = net.fetch_json(desc_uri)
        except Exception:
            typer.echo(f"Failed to fetch descriptor from {desc_uri}")
    elif ":" in str(desc_uri) and not os.path.exists(desc_uri):
        # has a scheme like gdrive:... which we don't handle here
        typer.echo(f"Descriptor uses external scheme ({desc_uri}); use plugin to fetch/verify")
    else:
        # assume local path or repository-relative
        descriptor = persistence.load_asset_descriptor(desc_uri)

    if descriptor:
        # basic check: descriptor dcat:distribution should point to data_uri
        dist = descriptor.get("dcat:distribution")
        dist_id = None
        if isinstance(dist, dict):
            dist_id = dist.get("@id")
        elif isinstance(dist, str):
            dist_id = dist

        relation_ok = (dist_id == data_uri)
        typer.echo(f"Descriptor links to data: {relation_ok}")
    else:
        typer.echo("Descriptor unavailable for checking relation")


@asset_app.command("version")
def asset_version(asset_id: str):
    typer.echo(f"Create version not implemented: {asset_id}")


@asset_app.command("export")
def asset_export(asset_id: str):
    typer.echo(f"Export not implemented: {asset_id}")


@asset_app.command("import")
def asset_import(asset_id: str):
    typer.echo(f"Import not implemented: {asset_id}")


# --- compute commands
@compute_app.command("run")
def compute_run(asset_id: str):
    typer.echo(f"Compute run for {asset_id} (not implemented)")


@compute_app.command("schedule")
def compute_schedule(asset_id: str):
    typer.echo(f"Compute schedule for {asset_id} (not implemented)")


@compute_app.command("status")
def compute_status(job_id: str):
    typer.echo(f"Compute status for {job_id} (not implemented)")


# --- index commands
@index_app.command("register")
def index_register():
    fa = FileAdapter()
    catalog = fa.read_json("catalog.json")
    fa.write_json("dcat-fed.json", catalog or {})
    typer.echo("Registered local catalog as dcat-fed.json")


@index_app.command("search")
def index_search(query: str):
    typer.echo(f"Search not implemented: {query}")


@index_app.command("export-format")
def index_export_format(asset_id: str):
    typer.echo(f"Export format not implemented: {asset_id}")


# --- lineage commands
@lineage_app.command("show")
def lineage_show(asset_id: str):
    typer.echo(f"Lineage show not implemented: {asset_id}")


@lineage_app.command("verify")
def lineage_verify(asset_id: str):
    typer.echo(f"Lineage verify not implemented: {asset_id}")


# --- plugin commands
@plugin_app.command("install")
def plugin_install(uri: str):
    typer.echo(f"Plugin install not implemented: {uri}")


@plugin_app.command("list")
def plugin_list():
    """List all available plugins categorized by type."""
    from ...core.services.plugin_manager import PluginManager
    
    manager = PluginManager()
    manager.discover("src.adapters.base_plugins")
    manager.discover("plugins")
    
    typer.echo("🔌 Available Plugins:")
    
    # List data fetcher plugins
    data_fetchers = manager.list_data_fetchers()
    if data_fetchers:
        typer.echo("\n📊 Data Fetcher Plugins:")
        for name, info in data_fetchers.items():
            typer.echo(f"  - {name}: {len(info.get('methods', {}))} methods available")
            if "error" in info:
                typer.echo(f"    ⚠️  Error: {info['error']}")
    
    # List other plugin types
    formatters = list(manager.formatters.keys())
    if formatters:
        typer.echo(f"\n🎨 Formatters: {', '.join(formatters)}")
    
    compute_drivers = list(manager.compute_drivers.keys())
    if compute_drivers:
        typer.echo(f"\n⚙️  Compute Drivers: {', '.join(compute_drivers)}")
    
    persistence_plugins = list(manager.persistence_plugins.keys())
    if persistence_plugins:
        typer.echo(f"\n💾 Persistence Plugins: {', '.join(persistence_plugins)}")


@plugin_app.command("info")
def plugin_info(plugin_name: str):
    """Get detailed information about a specific data fetcher plugin."""
    from ...core.services.plugin_manager import PluginManager
    
    manager = PluginManager()
    manager.discover("plugins")
    
    plugin = manager.get_data_fetcher(plugin_name)
    if not plugin:
        typer.echo(f"❌ Data fetcher plugin '{plugin_name}' not found")
        
        # Show available plugins
        data_fetchers = manager.list_data_fetchers()
        if data_fetchers:
            typer.echo("\n📊 Available data fetcher plugins:")
            for name in data_fetchers.keys():
                typer.echo(f"  - {name}")
        
        raise typer.Exit(code=1)
    
    typer.echo(f"📊 Plugin: {plugin_name}")
    typer.echo(f"Class: {plugin.__class__.__name__}")
    
    methods = plugin.get_available_methods()
    typer.echo(f"\n🔧 Available methods ({len(methods)}):")
    
    for method_name, method_info in methods.items():
        typer.echo(f"\n  📋 {method_name}")
        typer.echo(f"     Description: {method_info.get('description', 'N/A')}")
        typer.echo(f"     Returns: {method_info.get('returns', 'N/A')}")
        
        params = method_info.get('parameters', {})
        if params:
            typer.echo("     Parameters:")
            for param_name, param_info in params.items():
                required = "required" if param_info.get('required', False) else "optional"
                param_type = param_info.get('type', 'any')
                default = param_info.get('default', 'N/A')
                typer.echo(f"       • {param_name} ({param_type}, {required})")
                typer.echo(f"         {param_info.get('description', 'No description')}")
                if not param_info.get('required', False) and 'default' in param_info:
                    typer.echo(f"         Default: {default}")


@plugin_app.command("execute")
def plugin_execute(
    plugin_name: str,
    method_name: str,
    json_args: Optional[str] = typer.Option(None, "--json", help="JSON string or @file with method arguments")
):
    """Execute a method of a data fetcher plugin."""
    from ...core.services.plugin_manager import PluginManager
    import json
    
    manager = PluginManager()
    manager.discover("plugins")
    
    plugin = manager.get_data_fetcher(plugin_name)
    if not plugin:
        typer.echo(f"❌ Data fetcher plugin '{plugin_name}' not found")
        raise typer.Exit(code=1)
    
    # Validate method exists
    if method_name not in plugin.get_available_methods():
        typer.echo(f"❌ Method '{method_name}' not found in plugin '{plugin_name}'")
        
        available = list(plugin.get_available_methods().keys())
        typer.echo(f"\n🔧 Available methods: {', '.join(available)}")
        raise typer.Exit(code=1)
    
    # Parse arguments
    args = {}
    if json_args:
        try:
            if json_args.startswith("@"):
                with open(json_args[1:], "r", encoding="utf-8") as f:
                    args = json.load(f)
            else:
                args = json.loads(json_args)
        except Exception as e:
            typer.echo(f"❌ Failed to parse JSON arguments: {e}")
            raise typer.Exit(code=2)
    
    # Execute method
    typer.echo(f"🚀 Executing {plugin_name}.{method_name}...")
    
    try:
        result = plugin.execute_method(method_name, **args)
        
        if result.get("success", False):
            typer.echo("✅ Method executed successfully!")
            
            # Show result summary
            method_result = result.get("result", {})
            if "asset" in method_result:
                asset = method_result["asset"]
                typer.echo(f"\n📦 Asset created:")
                typer.echo(f"   ID: {asset.get('id', 'N/A')}")
                typer.echo(f"   Title: {asset.get('title', 'N/A')}")
                typer.echo(f"   Results: {asset.get('results_count', 'N/A')}")
                
                if "data_uri" in asset:
                    typer.echo(f"   Data: {asset['data_uri']}")
                if "data_dictionary_uri" in asset:
                    typer.echo(f"   Dictionary: {asset['data_dictionary_uri']}")
            
            # Show additional result info
            if "output_path" in method_result:
                typer.echo(f"\n📄 Output: {method_result['output_path']}")
            
        else:
            typer.echo("❌ Method execution failed!")
            typer.echo(f"Error: {result.get('error', 'Unknown error')}")
            
            if "errors" in result:
                typer.echo("Validation errors:")
                for error in result["errors"]:
                    typer.echo(f"  • {error}")
            
            raise typer.Exit(code=3)
    
    except Exception as e:
        typer.echo(f"❌ Exception during execution: {e}")
        raise typer.Exit(code=4)


@plugin_app.command("run")
def plugin_run(
    plugin_name: str,
    raw: Optional[str] = typer.Option(None, help="Raw string argument passed to plugin"),
    json_arg: Optional[str] = typer.Option(None, "--json", help="JSON string or @file path with JSON array/object"),
    yaml_arg: Optional[str] = typer.Option(None, "--yaml", help="YAML string or @file path with YAML content"),
):
    """Run a plugin function. `plugin_name` should be `module.path:func` or `module.path.func`.

    Arguments can be provided as:
    - raw string via --raw
    - JSON via --json (string or @file)
    - YAML via --yaml (string or @file)
    The parsed value will be dispatched as: list -> *args, dict -> **kwargs, else single arg.
    """
    # resolve module and function
    try:
        if ":" in plugin_name:
            mod_path, func = plugin_name.split(":", 1)
        elif "." in plugin_name:
            mod_path, func = plugin_name.rsplit(".", 1)
        else:
            typer.echo("Invalid plugin specifier. Use module:function or module.path.func")
            raise typer.Exit(code=2)

        mod = __import__(mod_path, fromlist=[func])
        fn = getattr(mod, func)
    except Exception as e:
        typer.echo(f"Failed to import plugin function: {e}")
        raise typer.Exit(code=3)

    # parse argument source (json > yaml > raw)
    parsed: Any = None
    try:
        if json_arg:
            import json

            if json_arg.startswith("@"):
                with open(json_arg[1:], "r", encoding="utf-8") as f:
                    parsed = json.load(f)
            else:
                parsed = json.loads(json_arg)
        elif yaml_arg:
            try:
                import yaml
            except Exception:
                typer.echo("PyYAML not installed; cannot parse YAML")
                raise typer.Exit(code=4)

            if yaml_arg.startswith("@"):
                with open(yaml_arg[1:], "r", encoding="utf-8") as f:
                    parsed = yaml.safe_load(f)
            else:
                parsed = yaml.safe_load(yaml_arg)
        elif raw is not None:
            parsed = raw
    except Exception as e:
        typer.echo(f"Failed to parse arguments: {e}")
        raise typer.Exit(code=5)

    # dispatch
    try:
        if isinstance(parsed, list):
            res = fn(*parsed)
        elif isinstance(parsed, dict):
            res = fn(**parsed)
        elif parsed is None:
            res = fn()
        else:
            res = fn(parsed)

        typer.echo(f"Plugin run result: {res}")
    except TypeError as te:
        # try passing the parsed as single arg if signature mismatches
        try:
            res = fn(parsed)
            typer.echo(f"Plugin run result: {res}")
        except Exception as e:
            typer.echo(f"Plugin invocation failed: {e}")
            raise typer.Exit(code=6)
    except Exception as e:
        typer.echo(f"Plugin invocation failed: {e}")
        raise typer.Exit(code=7)

