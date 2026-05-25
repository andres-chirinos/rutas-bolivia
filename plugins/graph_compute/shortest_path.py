"""Compute shortest path between nodes by using a lines GeoJSON as network.

Optimizes for transport efficiency considering:
- Minimum number of transport lines used
- Transport type preferences (teleférico > bus > minibus > taxi)
- Walking distance vs transport changes trade-offs
- Detailed route breakdown by transport line

Functions:
- build_network_from_lines(lines_geojson): builds a weighted NetworkX graph optimized for transport routing
- shortest_path(nodes_geojson, lines_geojson, src_id, dst_id): computes optimal path with detailed breakdown
"""

import json
from typing import List, Dict, Any, Tuple
import math
import os
import hashlib
import time
import networkx as nx
from shapely.geometry import LineString, Point


# ─── Spatial Tile Index ────────────────────────────────────────────────────────
# Pre-splits large GeoJSON files into ~1km spatial tiles on disk.
# Route requests only load the tiles near src/dst, keeping RAM low.

TILE_SIZE = 0.01          # ~1.1 km grid cells
LARGE_FILE_THRESHOLD = 500  # files with more features than this get tiled


class _SpatialTileIndex:
    """Pre-processes large GeoJSON files into spatial tiles for fast bbox queries."""

    def __init__(self):
        self._tile_dir = os.path.join(os.path.dirname(__file__), ".graph_tiles")
        os.makedirs(self._tile_dir, exist_ok=True)

    # ── helpers ──────────────────────────────────────────────────────────────
    def _dir_for(self, geojson_path: str) -> str:
        name = hashlib.md5(os.path.abspath(geojson_path).encode()).hexdigest()[:12]
        d = os.path.join(self._tile_dir, name)
        os.makedirs(d, exist_ok=True)
        return d

    def _manifest_path(self, geojson_path: str) -> str:
        return os.path.join(self._dir_for(geojson_path), "manifest.json")

    def _is_preprocessed(self, geojson_path: str) -> bool:
        mp = self._manifest_path(geojson_path)
        if not os.path.exists(mp):
            return False
        return os.path.getmtime(mp) >= os.path.getmtime(geojson_path)

    # ── preprocess ───────────────────────────────────────────────────────────
    def preprocess(self, geojson_path: str):
        """Split a large GeoJSON into spatial tile files (one-time operation)."""
        from collections import defaultdict

        tile_dir = self._dir_for(geojson_path)
        mp = self._manifest_path(geojson_path)

        if self._is_preprocessed(geojson_path):
            with open(mp) as f:
                manifest = json.load(f)
            print(f"  ✅ Tiles ya preprocesados para {os.path.basename(geojson_path)} ({len(manifest)} tiles)")
            return manifest

        print(f"  🔪 Dividiendo {os.path.basename(geojson_path)} en tiles espaciales...")
        t0 = time.time()

        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tiles = defaultdict(list)  # (gx, gy) -> [features]

        for feat in data.get("features", []):
            geom = feat.get("geometry")
            if not geom:
                continue
            gtype = geom.get("type")
            coords = geom.get("coordinates", [])
            if gtype == "MultiLineString":
                flat = [c for line in coords for c in line]
            elif gtype == "LineString":
                flat = coords
            else:
                continue

            # Find all tiles this feature touches
            seen = set()
            for c in flat:
                gx = int(c[0] / TILE_SIZE)
                gy = int(c[1] / TILE_SIZE)
                seen.add((gx, gy))
            for key in seen:
                tiles[key].append(feat)

        # Purge old tiles
        for old in os.listdir(tile_dir):
            os.remove(os.path.join(tile_dir, old))

        # Write each tile as a small JSON
        manifest = {}
        for (gx, gy), feats in tiles.items():
            tile_file = os.path.join(tile_dir, f"{gx}_{gy}.json")
            with open(tile_file, "w", encoding="utf-8") as f:
                json.dump(feats, f)
            manifest[f"{gx},{gy}"] = len(feats)

        with open(mp, "w") as f:
            json.dump(manifest, f)

        del data  # free memory immediately
        elapsed = time.time() - t0
        print(f"    → {len(manifest)} tiles creados en {elapsed:.1f}s")
        return manifest

    # ── bbox query ───────────────────────────────────────────────────────────
    def load_features_in_bbox(self, geojson_path: str, bbox: Tuple[float, float, float, float]) -> List[Dict]:
        """Load only features from tiles that intersect the bounding box."""
        tile_dir = self._dir_for(geojson_path)

        if not self._is_preprocessed(geojson_path):
            self.preprocess(geojson_path)

        min_lon, min_lat, max_lon, max_lat = bbox
        min_gx = int(min_lon / TILE_SIZE)
        max_gx = int(max_lon / TILE_SIZE)
        min_gy = int(min_lat / TILE_SIZE)
        max_gy = int(max_lat / TILE_SIZE)

        features = []
        tiles_loaded = 0
        for gx in range(min_gx, max_gx + 1):
            for gy in range(min_gy, max_gy + 1):
                tile_file = os.path.join(tile_dir, f"{gx}_{gy}.json")
                if os.path.exists(tile_file):
                    with open(tile_file, "r", encoding="utf-8") as f:
                        features.extend(json.load(f))
                    tiles_loaded += 1

        print(f"    📍 {os.path.basename(geojson_path)}: cargados {tiles_loaded} tiles, {len(features)} features (de bbox)")
        return features


class _SubgraphCache:
    """Lightweight in-memory cache for recently computed subgraphs, keyed by bbox hash."""

    def __init__(self, max_entries: int = 8):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max = max_entries

    def _key(self, network_paths: str, bbox: Tuple) -> str:
        raw = f"{network_paths}|{bbox}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, network_paths: str, bbox: Tuple) -> Dict[str, Any] | None:
        k = self._key(network_paths, bbox)
        if k in self._cache:
            print("⚡ Usando subgrafo en caché (misma zona)")
            return self._cache[k]
        return None

    def put(self, network_paths: str, bbox: Tuple, results: Dict[str, Any]):
        k = self._key(network_paths, bbox)
        # Evict oldest if at capacity
        if len(self._cache) >= self._max and k not in self._cache:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[k] = results


_tile_index = _SpatialTileIndex()
_subgraph_cache = _SubgraphCache()

# Transport type weights (lower = better preference)
TRANSPORT_WEIGHTS = {
    "teleferico": 1.0,    # Most preferred
    "bus": 2.0,           # Good option
    "minibus": 3.0,       # Standard option
    "taxi": 4.0,          # Less preferred
    "walking": 8.0,       # Walking on streets
    "default": 3.0        # Unknown transport type
}

# Layer types for multi-modal transport
LAYER_TYPES = {
    "street": "walking",      # Can walk anywhere on streets
    "free_line": "boarding",  # Can board/alight anywhere on line
    "station_line": "station" # Can only board/alight at designated stops
}

# Cost constants
TRANSFER_PENALTY = 2.0        # Penalty to enter/exit transit or change networks
WALKING_COST_PER_KM = 3.0     # Cost per km of walking (cheap, but transit is faster)
MAX_WALKING_DISTANCE_KM = 2.0 # Allow walking up to 2km if needed


def _get_transport_type(feature: Dict[str, Any]) -> str:
    """Extract transport type from feature properties."""
    props = feature.get("properties", {})
    
    # Check various property names that might indicate transport type
    for key in ["tipo", "type", "transport_type", "mode", "linea_tipo", "layer_type"]:
        if key in props:
            transport_type = str(props[key]).lower()
            if transport_type in TRANSPORT_WEIGHTS:
                return transport_type
    
    # Try to infer from line name/id
    line_name = str(feature.get("id", "")).lower()
    if "teleferico" in line_name or "cable" in line_name:
        return "teleferico"
    elif "bus" in line_name:
        return "bus"
    elif "mini" in line_name:
        return "minibus"
    elif "taxi" in line_name:
        return "taxi"
    elif "street" in line_name or "calle" in line_name:
        return "walking"
    
    return "default"


def _get_layer_type(feature: Dict[str, Any]) -> str:
    """Determine layer type: street, free_line, or station_line."""
    props = feature.get("properties", {})
    
    # Check explicit layer type
    layer_type = props.get("layer_type", "").lower()
    if layer_type in LAYER_TYPES:
        return layer_type
    
    # Infer from properties
    if props.get("type") == "street" or "street" in str(feature.get("id", "")).lower() or "tipovia" in props or "nombrevia" in props:
        return "street"
    elif props.get("stations") or props.get("stops"):
        return "station_line"
    else:
        return "free_line"


def _calculate_distance_km(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate approximate distance in kilometers using Haversine formula."""
    lat1, lon1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lon2 = math.radians(coord2[1]), math.radians(coord2[0])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in km
    r = 6371
    return c * r


def get_transport_config() -> Dict[str, Any]:
    """Get current transport configuration and available options."""
    return {
        "transport_weights": TRANSPORT_WEIGHTS.copy(),
        "layer_types": LAYER_TYPES.copy(),
        "transfer_penalty": TRANSFER_PENALTY,
        "max_walking_distance_km": MAX_WALKING_DISTANCE_KM,
        "walking_cost_per_km": WALKING_COST_PER_KM,
        "boarding_penalty": BOARDING_PENALTY,
        "description": {
            "transport_weights": "Lower values = more preferred transport type",
            "layer_types": "Available layer types for multi-modal routing",
            "transfer_penalty": "Cost penalty for changing lines",
            "max_walking_distance_km": "Maximum reasonable walking distance",
            "walking_cost_per_km": "Cost per kilometer of walking",
            "boarding_penalty": "Small penalty for boarding transport"
        }
    }


def update_transport_config(**kwargs) -> None:
    """Update transport configuration parameters."""
    global TRANSPORT_WEIGHTS, TRANSFER_PENALTY, MAX_WALKING_DISTANCE_KM, WALKING_COST_PER_KM, BOARDING_PENALTY
    
    if "transport_weights" in kwargs:
        TRANSPORT_WEIGHTS.update(kwargs["transport_weights"])
    if "transfer_penalty" in kwargs:
        TRANSFER_PENALTY = kwargs["transfer_penalty"]
    if "max_walking_distance_km" in kwargs:
        MAX_WALKING_DISTANCE_KM = kwargs["max_walking_distance_km"]
    if "walking_cost_per_km" in kwargs:
        WALKING_COST_PER_KM = kwargs["walking_cost_per_km"]
    if "boarding_penalty" in kwargs:
        BOARDING_PENALTY = kwargs["boarding_penalty"]


def test_multilayer_network(lines_geojson: str) -> Dict[str, Any]:
    """Test the multi-layer network construction and return statistics."""
    try:
        results = build_network_from_lines(lines_geojson)
        G = results["graph"]
        line_info = results["line_info"]
        stations = results["stations"]
        
        # Analyze network composition
        layer_stats = {}
        transport_stats = {}
        
        for line_id, info in line_info.items():
            layer_type = info["layer_type"]
            transport_type = info["transport_type"]
            
            layer_stats[layer_type] = layer_stats.get(layer_type, 0) + 1
            transport_stats[transport_type] = transport_stats.get(transport_type, 0) + 1
        
        return {
            "network_stats": {
                "total_nodes": G.number_of_nodes(),
                "total_edges": G.number_of_edges(),
                "total_lines": len(line_info),
                "stations": len(stations)
            },
            "layer_composition": layer_stats,
            "transport_composition": transport_stats,
            "connected_components": nx.number_connected_components(G),
            "largest_component_size": len(max(nx.connected_components(G), key=len)) if G.number_of_nodes() > 0 else 0
        }
    except Exception as e:
        return {"error": str(e)}


def build_network_from_lines(
    lines_geojson_path: str = None,
    bbox: Tuple[float, float, float, float] = None,
    features_list: List[Dict] = None
) -> Dict[str, Any]:
    """Build a multi-layer graph supporting streets, free lines, and station lines.
    
    Can be called with either:
    - lines_geojson_path: comma-separated paths to GeoJSON files (legacy)
    - features_list: pre-loaded list of GeoJSON features (from tile system)
    
    Returns:
    - graph: NetworkX graph with multi-modal routing
    - node_index: maps node_id -> (lon, lat)
    - edge_lines: maps (node_id1, node_id2) -> list of line info dicts
    - line_info: maps line_id -> transport type and properties
    - stations: maps line_id -> list of station coordinates (for station_lines)
    """
    if features_list is None:
        features_list = []
        for path in lines_geojson_path.split(","):
            path = path.strip()
            if not path: continue
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                features_list.extend(data.get("features", []))

    G = nx.Graph()
    node_index: Dict[str, Tuple[float, float]] = {}
    edge_lines: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    line_info: Dict[str, Dict[str, Any]] = {}
    stations: Dict[str, List[Tuple[float, float]]] = {}

    def coord_id(coord: Tuple[float, float]) -> str:
        # Optimization: Use 4 decimal places (approx 11m precision) to snap nearby nodes
        return f"{coord[0]:.4f},{coord[1]:.4f}"

    def add_node(coord: Tuple[float, float]) -> str:
        """Add node to graph and index."""
        node_id = coord_id(coord)
        if node_id not in node_index:
            node_index[node_id] = coord
            G.add_node(node_id, coord=coord)
        return node_id

    def add_edge(node1: str, node2: str, weight: float, distance: float, line_data: Dict[str, Any]):
        """Add edge with proper weight and line information."""
        edge_key = tuple(sorted((node1, node2)))
        edge_lines.setdefault(edge_key, []).append(line_data)
        
        # Use minimum weight if edge already exists
        if G.has_edge(node1, node2):
            current_weight = G[node1][node2]["weight"]
            if weight < current_weight:
                G[node1][node2]["weight"] = weight
                G[node1][node2]["distance_km"] = distance
        else:
            G.add_edge(node1, node2, weight=weight, distance_km=distance)

    # Process each feature
    features_total = len(features_list)
    features_processed = 0
    features_filtered = 0
    print(f"Cargadas {features_total} características desde los archivos.")
    
    for idx, feat in enumerate(features_list):
        if idx > 0 and idx % 10000 == 0:
            print(f"  ...procesando {idx}/{features_total} (Filtro BoundingBox omitió {features_filtered})...")
            
        geom = feat.get("geometry")
        if not geom:
            continue
            
        geom_type = geom.get("type")
        if geom_type == "LineString":
            lines = [geom.get("coordinates", [])]
        elif geom_type == "MultiLineString":
            lines = geom.get("coordinates", [])
        else:
            continue
            
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            in_bbox = False
            for line in lines:
                for coord in line:
                    if min_lon <= coord[0] <= max_lon and min_lat <= coord[1] <= max_lat:
                        in_bbox = True
                        break
                if in_bbox:
                    break
            if not in_bbox:
                features_filtered += 1
                continue

        features_processed += 1

        line_id = str(feat.get("id", f"line_{idx}"))
        transport_type = _get_transport_type(feat)
        layer_type = _get_layer_type(feat)
        transport_weight = TRANSPORT_WEIGHTS.get(transport_type, TRANSPORT_WEIGHTS["default"])
        
        # Store line information
        line_info[line_id] = {
            "transport_type": transport_type,
            "layer_type": layer_type,
            "weight": transport_weight,
            "properties": feat.get("properties", {}),
            "name": feat.get("properties", {}).get("name", line_id)
        }

        # Extract stations for station_line type
        if layer_type == "station_line":
            station_coords = feat.get("properties", {}).get("stations", [])
            if station_coords:
                stations[line_id] = [tuple(coord) for coord in station_coords]

        # Process each line
        for coords in lines:
            if len(coords) < 2:
                continue

            # Create nodes for all coordinates
            node_ids = []
            for coord in coords:
                node_ids.append(add_node(tuple(coord)))

            # Add edges based on layer type
            if layer_type == "street":
                # Streets: can walk between any adjacent points
                for i in range(len(node_ids) - 1):
                    curr_node = node_ids[i]
                    next_node = node_ids[i + 1]
                    distance = _calculate_distance_km(
                        node_index[curr_node], 
                        node_index[next_node]
                    )
                    
                    cost = distance * WALKING_COST_PER_KM
                    
                    line_data = {
                        "line_id": line_id,
                        "transport_type": transport_type,
                        "layer_type": layer_type,
                        "weight": cost,
                        "distance_km": distance
                    }
                    
                    add_edge(curr_node, next_node, cost, distance, line_data)

            elif layer_type == "free_line":
                # Free lines: can board at any point, travel along line, alight at any point
                # Add sequential connections for traveling along the line
                for i in range(len(node_ids) - 1):
                    curr_node = node_ids[i]
                    next_node = node_ids[i + 1]
                    distance = _calculate_distance_km(
                        node_index[curr_node], 
                        node_index[next_node]
                    )
                    
                    cost = distance * transport_weight
                    
                    line_data = {
                        "line_id": line_id,
                        "transport_type": transport_type,
                        "layer_type": layer_type,
                        "weight": cost,
                        "distance_km": distance
                    }
                    
                    add_edge(curr_node, next_node, cost, distance, line_data)

            elif layer_type == "station_line":
                # Station lines: can only board/alight at designated stations
                line_stations = stations.get(line_id, [])
                if not line_stations:
                    # If no explicit stations, use start and end points
                    line_stations = [tuple(coords[0]), tuple(coords[-1])]
                
                # Add station nodes
                station_nodes = [add_node(station_coord) for station_coord in line_stations]
                
                # Connect all stations to each other (can travel between any two stations)
                for i, station1 in enumerate(station_nodes):
                    for j, station2 in enumerate(station_nodes):
                        if i != j:
                            distance = _calculate_distance_km(
                                node_index[station1], 
                                node_index[station2]
                            )
                            cost = (distance * transport_weight) + TRANSFER_PENALTY
                            
                            line_data = {
                                "line_id": line_id,
                                "transport_type": transport_type,
                                "layer_type": layer_type,
                                "weight": cost,
                                "distance_km": distance,
                                "is_station_connection": True
                            }
                            
                            add_edge(station1, station2, cost, distance, line_data)

    # ── Bridge connections: link transport nodes ↔ nearest street node ──────
    # Instead of an O(N²) loop over all nodes, we only create ONE walking edge
    # from each transport-only node to its single nearest street node.
    from collections import defaultdict
    
    print("Creando puentes transporte ↔ calles...")
    
    # 1. Classify nodes by layer
    node_layers = defaultdict(set)
    for (n1, n2), edges in edge_lines.items():
        for edge in edges:
            lt = edge.get("layer_type", "unknown")
            node_layers[n1].add(lt)
            node_layers[n2].add(lt)
    
    street_nodes = {nid for nid, layers in node_layers.items() if "street" in layers}
    transport_only = {nid for nid in G.nodes() if nid not in street_nodes}
    
    print(f"  Nodos calle: {len(street_nodes)}, Nodos solo-transporte: {len(transport_only)}")
    
    # 2. Spatial index of street nodes only (lightweight)
    street_grid = defaultdict(list)
    grid_sz = 0.002  # ~220m cells
    for nid in street_nodes:
        if nid in node_index:
            c = node_index[nid]
            street_grid[(int(c[0]/grid_sz), int(c[1]/grid_sz))].append((nid, c))
    
    # 3. For each transport-only node, connect to nearest street node
    bridges = 0
    for nid in transport_only:
        if nid not in node_index:
            continue
        coord = node_index[nid]
        gx, gy = int(coord[0]/grid_sz), int(coord[1]/grid_sz)
        
        best_id, best_dist = None, float('inf')
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for snid, sc in street_grid.get((gx+dx, gy+dy), []):
                    d = abs(coord[0]-sc[0]) + abs(coord[1]-sc[1])  # Manhattan for speed
                    if d < best_dist:
                        best_dist = d
                        best_id = snid
        
        if best_id is not None:
            real_dist = _calculate_distance_km(coord, node_index[best_id])
            if real_dist <= MAX_WALKING_DISTANCE_KM:
                # Add TRANSFER_PENALTY to bridge to discourage arbitrary transit switching
                bridge_cost = (real_dist * WALKING_COST_PER_KM) + TRANSFER_PENALTY
                line_data = {
                    "line_id": "walking_bridge",
                    "transport_type": "walking",
                    "layer_type": "street",
                    "weight": bridge_cost,
                    "distance_km": real_dist,
                    "is_walking": True
                }
                add_edge(nid, best_id, bridge_cost, real_dist, line_data)
                bridges += 1
    
    print(f"  ✅ {bridges} puentes creados")

    return {
        "graph": G, 
        "node_index": node_index, 
        "edge_lines": edge_lines,
        "line_info": line_info,
        "stations": stations
    }


def _find_nearest_node(
    point: Tuple[float, float], node_index: Dict[str, Tuple[float, float]]
) -> str:
    """Find nearest node using simplified distance calculation for speed."""
    px, py = point
    best = None
    bestd = float("inf")
    # Use Manhattan distance for speed (good enough for finding nearest)
    for nid, (nx_, ny_) in node_index.items():
        d = abs(px - nx_) + abs(py - ny_)  # Manhattan distance is faster than Euclidean
        if d < bestd:
            bestd = d
            best = nid
    return best


def _find_optimal_path(
    G: nx.Graph, 
    edge_lines: Dict[Tuple[str, str], List[Dict[str, Any]]], 
    line_info: Dict[str, Dict[str, Any]],
    node_index: Dict[str, Tuple[float, float]],
    src_nid: str, 
    dst_nid: str
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Find optimal path with multi-layer support and fallback strategies.
    
    Returns (path_node_ids, route_segments) where route_segments contains detailed info about each segment.
    """
    src_coord = node_index[src_nid]
    dst_coord = node_index[dst_nid]
    direct_distance = _calculate_distance_km(src_coord, dst_coord)
    
    # Strategy 1: Direct walking if reasonable
    if direct_distance <= MAX_WALKING_DISTANCE_KM:
        walking_segment = {
            "type": "walking",
            "distance_km": direct_distance,
            "cost": direct_distance * WALKING_COST_PER_KM,
            "coordinates": [list(src_coord), list(dst_coord)]
        }
        return [src_nid, dst_nid], [walking_segment]
    
    # Strategy 2: Try A* path on existing graph
    def dist_heuristic(u, v):
        try:
            u_coord = node_index[u]
            v_coord = node_index[v]
            return _calculate_distance_km(u_coord, v_coord) * 1.0 # Minimum weight factor
        except KeyError:
            return 0

    print(f"Buscando ruta con A* desde {src_nid} hasta {dst_nid}...")
    try:
        path_nodes = nx.astar_path(G, source=src_nid, target=dst_nid, heuristic=dist_heuristic, weight="weight")
        print(f"Ruta A* encontrada con {len(path_nodes)} nodos.")
    except nx.NetworkXNoPath:
        # Strategy 3: Find nearest connected nodes and create multi-segment route
        print(f"No direct path found. Attempting multi-segment routing with A*...")
        
        # Find all nodes within walking distance of source
        src_candidates = []
        dst_candidates = []
        
        for node_id, coord in node_index.items():
            src_dist = _calculate_distance_km(src_coord, coord)
            dst_dist = _calculate_distance_km(dst_coord, coord)
            
            if src_dist <= MAX_WALKING_DISTANCE_KM and G.degree(node_id) > 0:
                src_candidates.append((node_id, src_dist))
            if dst_dist <= MAX_WALKING_DISTANCE_KM and G.degree(node_id) > 0:
                dst_candidates.append((node_id, dst_dist))
        
        # Sort by distance
        src_candidates.sort(key=lambda x: x[1])
        dst_candidates.sort(key=lambda x: x[1])
        
        # Try combinations until we find a path
        best_path = None
        best_segments = None
        best_cost = float('inf')
        
        for src_node, src_walk_dist in src_candidates[:5]:  # Try top 5 closest
            for dst_node, dst_walk_dist in dst_candidates[:5]:
                try:
                    middle_path = nx.astar_path(G, source=src_node, target=dst_node, heuristic=dist_heuristic, weight="weight")
                    
                    # Calculate total cost
                    total_cost = (src_walk_dist + dst_walk_dist) * WALKING_COST_PER_KM
                    path_cost = nx.path_weight(G, middle_path, weight="weight")
                    total_cost += path_cost
                    
                    if total_cost < best_cost:
                            best_cost = total_cost
                            best_path = [src_nid] + middle_path + [dst_nid]
                            
                            # Create segments
                            segments = []
                            
                            # Walking to network
                            if src_walk_dist > 0:
                                segments.append({
                                    "type": "walking",
                                    "distance_km": src_walk_dist,
                                    "cost": src_walk_dist * WALKING_COST_PER_KM,
                                    "coordinates": [list(src_coord), list(node_index[src_node])]
                                })
                            
                            # Network path
                            for i in range(len(middle_path) - 1):
                                curr_node = middle_path[i]
                                next_node = middle_path[i + 1]
                                edge_key = tuple(sorted((curr_node, next_node)))
                                
                                if edge_key in edge_lines:
                                    best_line = min(edge_lines[edge_key], key=lambda x: x["weight"])
                                    segments.append({
                                        "type": "transport",
                                        "line_id": best_line["line_id"],
                                        "transport_type": best_line["transport_type"],
                                        "coordinates": [list(node_index[curr_node]), list(node_index[next_node])],
                                        "distance_km": best_line["distance_km"],
                                        "cost": best_line["weight"]
                                    })
                            
                            # Walking from network
                            if dst_walk_dist > 0:
                                segments.append({
                                    "type": "walking",
                                    "distance_km": dst_walk_dist,
                                    "cost": dst_walk_dist * WALKING_COST_PER_KM,
                                    "coordinates": [list(node_index[dst_node]), list(dst_coord)]
                                })
                            
                            best_segments = segments
                            
                except nx.NetworkXNoPath:
                    continue
        
        if best_path:
            return best_path, best_segments
        else:
            # Strategy 4: Last resort - direct walking regardless of distance
            print(f"No network path found. Using direct walking ({direct_distance:.2f} km)")
            walking_segment = {
                "type": "walking",
                "distance_km": direct_distance,
                "cost": direct_distance * WALKING_COST_PER_KM * 2,  # Penalty for long walk
                "coordinates": [list(src_coord), list(dst_coord)]
            }
            return [src_nid, dst_nid], [walking_segment]
    
    # Convert successful path to segments, consolidated by TRANSPORT TYPE
    # (not by line_id, since streets have unique IDs per segment)
    raw_edges = []
    for i in range(len(path_nodes) - 1):
        current_node = path_nodes[i]
        next_node = path_nodes[i + 1]
        edge_key = tuple(sorted((current_node, next_node)))
        
        if edge_key in edge_lines:
            best_line = min(edge_lines[edge_key], key=lambda x: x["weight"])
            transport_type = best_line.get("transport_type", "unknown")
            layer_type = best_line.get("layer_type", "unknown")
            # Normalize: streets and walking bridges are all "walking"
            if layer_type == "street" or transport_type == "walking":
                mode = "walking"
            else:
                mode = transport_type
            raw_edges.append({
                "mode": mode,
                "line_id": best_line.get("line_id", ""),
                "transport_type": transport_type,
                "from": current_node,
                "to": next_node,
                "distance_km": best_line.get("distance_km", 0),
            })
    
    # Consolidate consecutive edges with the same mode
    segments = []
    if raw_edges:
        current_mode = raw_edges[0]["mode"]
        current_coords = [list(node_index[raw_edges[0]["from"]])]
        current_dist = 0.0
        current_lines = set()
        
        for edge in raw_edges:
            if edge["mode"] == current_mode:
                current_coords.append(list(node_index[edge["to"]]))
                current_dist += edge["distance_km"]
                current_lines.add(edge["line_id"])
            else:
                # Flush previous segment
                segments.append({
                    "type": current_mode,
                    "transport_type": current_mode,
                    "coordinates": current_coords,
                    "distance_km": round(current_dist, 2),
                })
                # Start new segment
                current_mode = edge["mode"]
                current_coords = [list(node_index[edge["from"]]), list(node_index[edge["to"]])]
                current_dist = edge["distance_km"]
                current_lines = {edge["line_id"]}
        
        # Flush last segment
        segments.append({
            "type": current_mode,
            "transport_type": current_mode,
            "coordinates": current_coords,
            "distance_km": round(current_dist, 2),
        })
    
    print(f"Ruta consolidada: {len(segments)} segmentos")
    return path_nodes, segments


def shortest_path(
    nodes_geojson: str, 
    lines_geojson: str, 
    src_id: str, 
    dst_id: str,
    transport_preferences: Dict[str, float] = None,
    max_walking_km: float = 1.0,
    transfer_penalty: float = 2.0
) -> Dict[str, Any]:
    """Compute optimal path along multi-layer network between node ids.
    Supports:
    - Street layer: walking connections
    - Free line layer: board/alight anywhere
    - Station line layer: board/alight only at stations

    Args:
        nodes_geojson: Path to nodes GeoJSON file
        lines_geojson: Path to lines GeoJSON file  
        src_id: Source node ID
        dst_id: Destination node ID
        transport_preferences: Custom weights for transport types (optional)
        max_walking_km: Maximum walking distance in km (default: 1.0)
        transfer_penalty: Penalty cost for line transfers (default: 2.0)

    Returns a dict with detailed route information including multi-modal segments.
    """
    # Update global constants with user preferences
    global MAX_WALKING_DISTANCE_KM, TRANSFER_PENALTY
    MAX_WALKING_DISTANCE_KM = max_walking_km
    TRANSFER_PENALTY = transfer_penalty
    
    # Update transport weights if provided
    if transport_preferences:
        TRANSPORT_WEIGHTS.update(transport_preferences)

    # 1. Load nodes and find src/dst coordinates
    try:
        with open(nodes_geojson, "r", encoding="utf-8") as f:
            nodes = json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to load nodes: {str(e)}")

    src_coord = None
    dst_coord = None
    for feat in nodes.get("features", []):
        pid = feat.get("properties", {}).get("id")
        if pid == src_id:
            src_coord = tuple(feat.get("geometry", {}).get("coordinates"))
        if pid == dst_id:
            dst_coord = tuple(feat.get("geometry", {}).get("coordinates"))

    if src_coord is None:
        raise ValueError(f"Source node '{src_id}' not found in nodes geojson")
    if dst_coord is None:
        raise ValueError(f"Destination node '{dst_id}' not found in nodes geojson")

    # 2. Compute bounding box from src/dst (margin ~ 3.3km)
    margin = 0.03
    min_lon = min(src_coord[0], dst_coord[0]) - margin
    max_lon = max(src_coord[0], dst_coord[0]) + margin
    min_lat = min(src_coord[1], dst_coord[1]) - margin
    max_lat = max(src_coord[1], dst_coord[1]) + margin
    bbox = (min_lon, min_lat, max_lon, max_lat)

    # 3. Check subgraph cache (same area = instant)
    t0 = time.time()
    cached = _subgraph_cache.get(lines_geojson, bbox)

    if cached is not None:
        results = cached
    else:
        # 4. Load features using spatial tiles for large files, full load for small files
        print(f"🗺️  Cargando features para bbox ({min_lon:.4f},{min_lat:.4f}) - ({max_lon:.4f},{max_lat:.4f})...")
        all_features = []
        
        for path in lines_geojson.split(","):
            path = path.strip()
            if not path or not os.path.exists(path):
                continue
            
            # Check file size to decide strategy
            file_size = os.path.getsize(path)
            
            if file_size > 1_000_000:  # > 1MB → use tiles
                # Ensure tiles exist (one-time preprocessing)
                _tile_index.preprocess(path)
                features = _tile_index.load_features_in_bbox(path, bbox)
            else:
                # Small file → load fully (teleférico, puma katari, etc.)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                features = data.get("features", [])
                print(f"    📄 {os.path.basename(path)}: {len(features)} features (carga completa)")
            
            all_features.extend(features)
        
        print(f"  Total: {len(all_features)} features combinadas")
        
        # 5. Build subgraph from loaded features
        try:
            results = build_network_from_lines(features_list=all_features, bbox=bbox)
            _subgraph_cache.put(lines_geojson, bbox, results)
        except Exception as e:
            raise ValueError(f"Failed to build network: {str(e)}")

    G = results["graph"]
    node_idx = results["node_index"]
    edge_lines = results["edge_lines"]
    line_info = results["line_info"]
    stations = results.get("stations", {})
    
    print(f"Grafo listo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas ({time.time()-t0:.3f}s)")

    # 3. Map to nearest network nodes
    src_nid = _find_nearest_node(src_coord, node_idx)
    dst_nid = _find_nearest_node(dst_coord, node_idx)
    
    print(f"Mapped {src_id} -> {src_nid}, {dst_id} -> {dst_nid}")

    # 4. Find optimal path (A* with heuristic on the full cached graph)
    try:
        path_node_ids, route_segments = _find_optimal_path(G, edge_lines, line_info, node_idx, src_nid, dst_nid)
    except Exception as e:
        raise ValueError(f"Failed during route computation: {str(e)}")

    # Process segments to create GeoJSON features and summary
    features = []
    lines_used = {}  # line_id -> segment info
    total_distance = 0
    total_walking_distance = 0
    
    for segment in route_segments:
        if segment["type"] == "transport":
            line_id = segment["line_id"]
            transport_type = segment["transport_type"]
            
            # Add to lines_used summary
            if line_id not in lines_used:
                lines_used[line_id] = {
                    "line_id": line_id,
                    "transport_type": transport_type,
                    "name": line_info.get(line_id, {}).get("name", line_id),
                    "layer_type": line_info.get(line_id, {}).get("layer_type", "unknown"),
                    "segments": [],
                    "total_distance": 0,
                    "is_transfer": segment.get("transfer", False)
                }
            
            lines_used[line_id]["segments"].append({
                "coordinates": segment["coordinates"],
                "distance_km": segment["distance_km"]
            })
            lines_used[line_id]["total_distance"] += segment["distance_km"]
            total_distance += segment["distance_km"]
            
            # Create GeoJSON feature for this segment
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": segment["coordinates"]
                },
                "properties": {
                    "source": "transport",
                    "line_id": line_id,
                    "transport_type": transport_type,
                    "layer_type": line_info.get(line_id, {}).get("layer_type", "unknown"),
                    "distance_km": segment["distance_km"],
                    "transfer": segment.get("transfer", False)
                }
            })
            
        elif segment["type"] == "walking":
            total_walking_distance += segment["distance_km"]
            total_distance += segment["distance_km"]
            
            # Create GeoJSON feature for walking segment
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": segment["coordinates"]
                },
                "properties": {
                    "source": "walking",
                    "distance_km": segment["distance_km"]
                }
            })

    # Add walking segments from/to exact coordinates if needed
    first_segment_start = route_segments[0]["coordinates"][0] if route_segments else None
    last_segment_end = route_segments[-1]["coordinates"][-1] if route_segments else None

    if first_segment_start and (
        abs(src_coord[0] - first_segment_start[0]) > 1e-4 or 
        abs(src_coord[1] - first_segment_start[1]) > 1e-4
    ):
        walk_distance = _calculate_distance_km(src_coord, tuple(first_segment_start))
        total_walking_distance += walk_distance
        features.insert(0, {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [list(src_coord), first_segment_start]
            },
            "properties": {
                "source": "walk_to_network",
                "distance_km": walk_distance
            }
        })

    if last_segment_end and (
        abs(dst_coord[0] - last_segment_end[0]) > 1e-4 or 
        abs(dst_coord[1] - last_segment_end[1]) > 1e-4
    ):
        walk_distance = _calculate_distance_km(tuple(last_segment_end), dst_coord)
        total_walking_distance += walk_distance
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [last_segment_end, list(dst_coord)]
            },
            "properties": {
                "source": "walk_from_network",
                "distance_km": walk_distance
            }
        })

    route_fc = {"type": "FeatureCollection", "features": features}

    return {
        "path_node_ids": path_node_ids,
        "route_geojson": route_fc,
        "lines_used": list(lines_used.values()),
        "route_segments": route_segments,
        "summary": {
            "total_lines": len(lines_used),
            "total_distance_km": round(total_distance, 3),
            "walking_distance_km": round(total_walking_distance, 3),
            "transport_distance_km": round(total_distance - total_walking_distance, 3),
            "transport_types_used": list(set(line["transport_type"] for line in lines_used.values())),
            "layer_types_used": list(set(line["layer_type"] for line in lines_used.values()))
        }
    }
