"""Route planner with in-memory cache.

Single-file implementation that supports passing one or multiple network files.
It caches built networks (graph, node index, edge lines, line info) in memory keyed by
the set of network file paths to improve latency on repeated requests.
"""
from typing import Tuple, Optional, Dict, Any, List, Union
from collections import OrderedDict
import os
import json
import tempfile
import uuid
import math
import time

# Simple in-memory LRU cache for built networks
_NETWORK_CACHE_MAX = 4
_network_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _network_cache.get(key)
    if entry is None:
        return None
    # move to end (most recently used)
    _network_cache.move_to_end(key)
    return entry["results"]


def _cache_set(key: str, results: Dict[str, Any]) -> None:
    _network_cache[key] = {"results": results, "timestamp": time.time()}
    _network_cache.move_to_end(key)
    if len(_network_cache) > _NETWORK_CACHE_MAX:
        _network_cache.popitem(last=False)


class RoutePlanner:
    def __init__(self, default_network: Optional[str] = None):
        self.default_network = default_network

    def _haversine_km(self, a: Tuple[float, float], b: Tuple[float, float]) -> float:
        lon1, lat1 = map(math.radians, a)
        lon2, lat2 = map(math.radians, b)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        sa = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(sa))
        return 6371 * c

    def _prepare_network(self, network_param: Optional[Union[str, List[str]]]) -> Tuple[str, str, Optional[str]]:
        """Return (network_path_to_use, cache_key, merged_temp_or_None).

        cache_key is built from the provided network file paths (sorted);
        if multiple files are provided they are merged into a temporary GeoJSON which
        is returned as network_path_to_use. The merged temp will be removed after building.
        """
        if network_param is None:
            raise FileNotFoundError("No network provided")

        if isinstance(network_param, str):
            networks = [network_param]
        else:
            networks = list(network_param)

        # If a single comma-separated string, expand it
        if len(networks) == 1 and isinstance(networks[0], str) and "," in networks[0]:
            networks = [p.strip() for p in networks[0].split(",") if p.strip()]

        for p in networks:
            if not os.path.exists(p):
                raise FileNotFoundError(f"Network file not found: {p}")

        cache_key = "|".join(sorted(networks))

        if len(networks) == 1:
            return networks[0], cache_key, None

        # Merge multiple networks
        merged = {"type": "FeatureCollection", "features": []}
        for net in networks:
            with open(net, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                merged["features"].extend(data.get("features", []))

        tmpf = os.path.join(tempfile.gettempdir(), f"merged_network_{uuid.uuid4().hex}.geojson")
        with open(tmpf, "w", encoding="utf-8") as fh:
            json.dump(merged, fh)
        return tmpf, cache_key, tmpf

    def route_by_coords(
        self,
        src: Tuple[float, float],
        dst: Tuple[float, float],
        network: Optional[Union[str, List[str]]] = None,
        planner: str = "astar",
        **kwargs,
    ) -> Dict[str, Any]:
        """Compute route between src and dst coordinates.

        src and dst are (lon, lat).
        planner: 'astar' (default) or 'plugin'.
        network: single path or list of paths.
        """
        network_param = network or self.default_network
        net_path, cache_key, merged_temp = self._prepare_network(network_param)

        # check cache
        cached = _cache_get(cache_key)
        if cached is not None:
            results = cached
        else:
            try:
                import plugins.graph_compute.shortest_path as gp
            except Exception as e:
                # cleanup merged temp
                if merged_temp and os.path.exists(merged_temp):
                    try:
                        os.remove(merged_temp)
                    except Exception:
                        pass
                raise RuntimeError(f"Failed to import routing plugin: {e}")

            results = gp.build_network_from_lines(net_path)
            _cache_set(cache_key, results)

            # remove merged temp after building (we cached the results)
            if merged_temp and os.path.exists(merged_temp):
                try:
                    os.remove(merged_temp)
                except Exception:
                    pass

        # lazy import of plugin (we expect it to be available)
        try:
            import plugins.graph_compute.shortest_path as gp
        except Exception as e:
            raise RuntimeError(f"Failed to import routing plugin: {e}")

        # create tiny nodes feature collection
        nodes_fc = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [src[0], src[1]]}, "properties": {"id": "SRC"}},
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [dst[0], dst[1]]}, "properties": {"id": "DST"}},
            ],
        }

        if planner == "plugin":
            tmpf = os.path.join(tempfile.gettempdir(), f"nodes_{uuid.uuid4().hex}.geojson")
            try:
                with open(tmpf, "w", encoding="utf-8") as fh:
                    json.dump(nodes_fc, fh)
                result = gp.shortest_path(tmpf, net_path, "SRC", "DST", **kwargs)
                result["requested"] = {"src": list(src), "dst": list(dst), "planner": "plugin"}
                return result
            finally:
                try:
                    os.remove(tmpf)
                except Exception:
                    pass

        # astar/default: reuse cached/built network
        G = results["graph"]
        node_index = results["node_index"]
        edge_lines = results["edge_lines"]
        line_info = results["line_info"]

        try:
            src_nid = gp._find_nearest_node((src[0], src[1]), node_index)
            dst_nid = gp._find_nearest_node((dst[0], dst[1]), node_index)
        except Exception:
            src_nid = min(node_index.keys(), key=lambda nid: self._haversine_km((node_index[nid][0], node_index[nid][1]), src))
            dst_nid = min(node_index.keys(), key=lambda nid: self._haversine_km((node_index[nid][0], node_index[nid][1]), dst))

        path_nodes, route_segments = gp._find_optimal_path(G, edge_lines, line_info, node_index, src_nid, dst_nid)

        # assemble response
        features = []
        lines_used = {}
        total_distance = 0.0
        total_walking = 0.0

        for segment in route_segments:
            if segment.get("type") == "transport":
                line_id = segment.get("line_id")
                if line_id not in lines_used:
                    lines_used[line_id] = {
                        "line_id": line_id,
                        "transport_type": segment.get("transport_type", "unknown"),
                        "name": line_info.get(line_id, {}).get("name", line_id),
                        "layer_type": line_info.get(line_id, {}).get("layer_type", "unknown"),
                        "segments": [],
                        "total_distance": 0,
                    }
                lines_used[line_id]["segments"].append({"coordinates": segment.get("coordinates"), "distance_km": segment.get("distance_km")})
                lines_used[line_id]["total_distance"] += segment.get("distance_km", 0)
                total_distance += segment.get("distance_km", 0)
                features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": segment.get("coordinates")}, "properties": {"source": "transport", "line_id": line_id, "distance_km": segment.get("distance_km")}})
            else:
                total_walking += segment.get("distance_km", 0)
                total_distance += segment.get("distance_km", 0)
                features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": segment.get("coordinates")}, "properties": {"source": "walking", "distance_km": segment.get("distance_km")}})

        route_fc = {"type": "FeatureCollection", "features": features}
        summary = {
            "total_lines": len(lines_used),
            "total_distance_km": round(total_distance, 3),
            "walking_distance_km": round(total_walking, 3),
            "transport_distance_km": round(total_distance - total_walking, 3),
            "transport_types_used": list(set(l.get("transport_type") for l in lines_used.values())),
            "layer_types_used": list(set(l.get("layer_type") for l in lines_used.values())),
        }

        return {"path_node_ids": path_nodes, "route_geojson": route_fc, "lines_used": list(lines_used.values()), "summary": summary, "requested": {"src": list(src), "dst": list(dst), "planner": planner}}
