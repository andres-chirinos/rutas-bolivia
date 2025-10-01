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
import networkx as nx
from shapely.geometry import LineString, Point

# Transport type weights (lower = better preference)
TRANSPORT_WEIGHTS = {
    "teleferico": 1.0,    # Most preferred
    "bus": 2.0,           # Good option
    "minibus": 3.0,       # Standard option
    "taxi": 4.0,          # Less preferred
    "default": 3.0        # Unknown transport type
}

# Cost constants
TRANSFER_PENALTY = 5.0    # Cost of changing lines
WALKING_COST_PER_KM = 10.0  # Cost per km of walking (approximate)
MAX_WALKING_DISTANCE_KM = 0.5  # Max reasonable walking distance


def _get_transport_type(feature: Dict[str, Any]) -> str:
    """Extract transport type from feature properties."""
    props = feature.get("properties", {})
    
    # Check various property names that might indicate transport type
    for key in ["tipo", "type", "transport_type", "mode", "linea_tipo"]:
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
    
    return "default"


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
        "transfer_penalty": TRANSFER_PENALTY,
        "max_walking_distance_km": MAX_WALKING_DISTANCE_KM,
        "walking_cost_per_km": WALKING_COST_PER_KM,
        "description": {
            "transport_weights": "Lower values = more preferred transport type",
            "transfer_penalty": "Cost penalty for changing lines",
            "max_walking_distance_km": "Maximum reasonable walking distance",
            "walking_cost_per_km": "Cost per kilometer of walking"
        }
    }


def update_transport_config(**kwargs) -> None:
    """Update transport configuration parameters."""
    global TRANSPORT_WEIGHTS, TRANSFER_PENALTY, MAX_WALKING_DISTANCE_KM, WALKING_COST_PER_KM
    
    if "transport_weights" in kwargs:
        TRANSPORT_WEIGHTS.update(kwargs["transport_weights"])
    if "transfer_penalty" in kwargs:
        TRANSFER_PENALTY = kwargs["transfer_penalty"]
    if "max_walking_distance_km" in kwargs:
        MAX_WALKING_DISTANCE_KM = kwargs["max_walking_distance_km"]
    if "walking_cost_per_km" in kwargs:
        WALKING_COST_PER_KM = kwargs["walking_cost_per_km"]


def build_network_from_lines(
    lines_geojson_path: str,
) -> Dict[str, Any]:
    """Build a graph from LineString or MultiLineString features. Returns dict with:
    - graph: NetworkX graph with weighted edges
    - node_index: maps node_id -> (lon, lat)
    - edge_lines: maps (node_id1, node_id2) -> list of line info dicts
    - line_info: maps line_id -> transport type and properties
    """
    with open(lines_geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    G = nx.Graph()
    node_index: Dict[str, Tuple[float, float]] = {}
    edge_lines: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    line_info: Dict[str, Dict[str, Any]] = {}

    def coord_id(coord: Tuple[float, float]) -> str:
        return f"{coord[0]:.6f},{coord[1]:.6f}"

    for idx, feat in enumerate(data.get("features", [])):
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

        line_id = str(feat.get("id", idx))
        transport_type = _get_transport_type(feat)
        transport_weight = TRANSPORT_WEIGHTS.get(transport_type, TRANSPORT_WEIGHTS["default"])
        
        # Store line information
        line_info[line_id] = {
            "transport_type": transport_type,
            "weight": transport_weight,
            "properties": feat.get("properties", {}),
            "name": feat.get("properties", {}).get("name", line_id)
        }

        for coords in lines:
            for i in range(len(coords) - 1):
                a = tuple(coords[i])
                b = tuple(coords[i + 1])
                aid = coord_id(a)
                bid = coord_id(b)
                if aid not in node_index:
                    node_index[aid] = a
                    G.add_node(aid, coord=a)
                if bid not in node_index:
                    node_index[bid] = b
                    G.add_node(bid, coord=b)
                
                # Calculate segment distance
                distance_km = _calculate_distance_km(a, b)
                
                # Store line information for this edge
                edge_key = tuple(sorted((aid, bid)))
                line_edge_info = {
                    "line_id": line_id,
                    "transport_type": transport_type,
                    "weight": transport_weight,
                    "distance_km": distance_km
                }
                edge_lines.setdefault(edge_key, []).append(line_edge_info)
                
                # Add edge with minimum weight among all lines serving this segment
                if G.has_edge(aid, bid):
                    current_weight = G[aid][bid]["weight"]
                    new_weight = min(current_weight, transport_weight)
                    G[aid][bid]["weight"] = new_weight
                else:
                    G.add_edge(aid, bid, weight=transport_weight, distance_km=distance_km)

    return {
        "graph": G, 
        "node_index": node_index, 
        "edge_lines": edge_lines,
        "line_info": line_info
    }


def _find_nearest_node(
    point: Tuple[float, float], node_index: Dict[str, Tuple[float, float]]
) -> str:
    px, py = point
    best = None
    bestd = float("inf")
    for nid, (nx_, ny_) in node_index.items():
        d = math.hypot(px - nx_, py - ny_)
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
    """Find optimal path considering transport types, transfers, and walking alternatives.
    
    Returns (path_node_ids, route_segments) where route_segments contains detailed info about each segment.
    """
    import heapq
    import itertools
    
    # Counter to break ties in heap comparisons
    counter = itertools.count()
    
    # Check if walking is a reasonable option
    src_coord = node_index[src_nid]
    dst_coord = node_index[dst_nid]
    direct_distance = _calculate_distance_km(src_coord, dst_coord)
    
    if direct_distance <= MAX_WALKING_DISTANCE_KM:
        # Direct walking is reasonable
        walking_cost = direct_distance * WALKING_COST_PER_KM
        walking_segment = {
            "type": "walking",
            "distance_km": direct_distance,
            "cost": walking_cost,
            "coordinates": [list(src_coord), list(dst_coord)]
        }
        return [src_nid, dst_nid], [walking_segment]
    
    # Priority queue: (total_cost, num_transfers, counter, current_node, current_line, path, segments)
    pq = [(0, 0, next(counter), src_nid, None, [src_nid], [])]
    visited = {}  # (node, current_line) -> (min_cost, min_transfers)
    
    while pq:
        total_cost, num_transfers, _, current, current_line, path, segments = heapq.heappop(pq)
        
        if current == dst_nid:
            return path, segments
        
        # State key includes both node and current line (to handle transfers)
        state_key = (current, current_line)
        if state_key in visited:
            prev_cost, prev_transfers = visited[state_key]
            if prev_cost < total_cost or (prev_cost == total_cost and prev_transfers <= num_transfers):
                continue
        
        visited[state_key] = (total_cost, num_transfers)
        
        # Option 1: Continue on current line (if applicable)
        if current_line is not None:
            for neighbor in G.neighbors(current):
                if neighbor in path:  # Avoid cycles
                    continue
                    
                edge_key = tuple(sorted((current, neighbor)))
                available_lines = edge_lines.get(edge_key, [])
                
                # Check if current line serves this edge
                for line_data in available_lines:
                    if line_data["line_id"] == current_line:
                        new_cost = total_cost + line_data["weight"]
                        new_path = path + [neighbor]
                        new_segments = segments[:]
                        
                        # Extend current segment or create new one
                        if segments and segments[-1]["type"] == "transport" and segments[-1]["line_id"] == current_line:
                            new_segments[-1]["coordinates"].append(list(node_index[neighbor]))
                            new_segments[-1]["distance_km"] += line_data["distance_km"]
                        else:
                            new_segment = {
                                "type": "transport",
                                "line_id": current_line,
                                "transport_type": line_data["transport_type"],
                                "coordinates": [list(node_index[current]), list(node_index[neighbor])],
                                "distance_km": line_data["distance_km"],
                                "cost": line_data["weight"]
                            }
                            new_segments.append(new_segment)
                        
                        heapq.heappush(pq, (new_cost, num_transfers, next(counter), neighbor, current_line, new_path, new_segments))
        
        # Option 2: Start new line or transfer
        for neighbor in G.neighbors(current):
            if neighbor in path:  # Avoid cycles
                continue
                
            edge_key = tuple(sorted((current, neighbor)))
            available_lines = edge_lines.get(edge_key, [])
            
            for line_data in available_lines:
                line_id = line_data["line_id"]
                
                # Skip if continuing on same line (handled above)
                if line_id == current_line:
                    continue
                
                # Calculate cost including transfer penalty
                transfer_cost = TRANSFER_PENALTY if current_line is not None else 0
                new_cost = total_cost + line_data["weight"] + transfer_cost
                new_transfers = num_transfers + (1 if current_line is not None else 0)
                new_path = path + [neighbor]
                new_segments = segments[:]
                
                # Add new transport segment
                new_segment = {
                    "type": "transport",
                    "line_id": line_id,
                    "transport_type": line_data["transport_type"],
                    "coordinates": [list(node_index[current]), list(node_index[neighbor])],
                    "distance_km": line_data["distance_km"],
                    "cost": line_data["weight"],
                    "transfer": current_line is not None
                }
                new_segments.append(new_segment)
                
                heapq.heappush(pq, (new_cost, new_transfers, next(counter), neighbor, line_id, new_path, new_segments))
        
        # Option 3: Consider walking to nearby nodes (if reasonable)
        if len(path) > 1:  # Don't walk from start unless necessary
            current_coord = node_index[current]
            for node_id, coord in node_index.items():
                if node_id in path or node_id == current:
                    continue
                
                walk_distance = _calculate_distance_km(current_coord, coord)
                if walk_distance <= MAX_WALKING_DISTANCE_KM:
                    walk_cost = walk_distance * WALKING_COST_PER_KM
                    new_cost = total_cost + walk_cost
                    new_path = path + [node_id]
                    new_segments = segments[:]
                    
                    walking_segment = {
                        "type": "walking",
                        "distance_km": walk_distance,
                        "cost": walk_cost,
                        "coordinates": [list(current_coord), list(coord)]
                    }
                    new_segments.append(walking_segment)
                    
                    heapq.heappush(pq, (new_cost, num_transfers, next(counter), node_id, None, new_path, new_segments))
    
    # Fallback to regular shortest path
    try:
        fallback_path = list(nx.shortest_path(G, source=src_nid, target=dst_nid, weight="weight"))
        fallback_segments = []
        
        for i in range(len(fallback_path) - 1):
            current_node = fallback_path[i]
            next_node = fallback_path[i + 1]
            edge_key = tuple(sorted((current_node, next_node)))
            
            if edge_key in edge_lines:
                # Use the best available line for this edge
                best_line = min(edge_lines[edge_key], key=lambda x: x["weight"])
                segment = {
                    "type": "transport",
                    "line_id": best_line["line_id"],
                    "transport_type": best_line["transport_type"],
                    "coordinates": [list(node_index[current_node]), list(node_index[next_node])],
                    "distance_km": best_line["distance_km"],
                    "cost": best_line["weight"]
                }
                fallback_segments.append(segment)
        
        return fallback_path, fallback_segments
        
    except nx.NetworkXNoPath:
        raise ValueError("No path found between source and destination")


def shortest_path(
    nodes_geojson: str, 
    lines_geojson: str, 
    src_id: str, 
    dst_id: str,
    transport_preferences: Dict[str, float] = None,
    max_walking_km: float = 0.5,
    transfer_penalty: float = 5.0
) -> Dict[str, Any]:
    """Compute optimal path along `lines_geojson` network between node ids in `nodes_geojson`.
    Optimizes for transport efficiency considering line types, transfers, and walking alternatives.

    Args:
        nodes_geojson: Path to nodes GeoJSON file
        lines_geojson: Path to lines GeoJSON file
        src_id: Source node ID
        dst_id: Destination node ID
        transport_preferences: Custom weights for transport types (optional)
        max_walking_km: Maximum walking distance in km (default: 0.5)
        transfer_penalty: Penalty cost for line transfers (default: 5.0)

    Returns a dict with detailed route information including segments breakdown.
    """
    # Update global constants with user preferences
    global MAX_WALKING_DISTANCE_KM, TRANSFER_PENALTY
    MAX_WALKING_DISTANCE_KM = max_walking_km
    TRANSFER_PENALTY = transfer_penalty
    
    # Update transport weights if provided
    if transport_preferences:
        TRANSPORT_WEIGHTS.update(transport_preferences)
    # build network
    results = build_network_from_lines(lines_geojson)
    G = results["graph"]
    node_idx = results["node_index"]
    edge_lines = results["edge_lines"]
    line_info = results["line_info"]

    # load nodes and find src/dst coordinates
    with open(nodes_geojson, "r", encoding="utf-8") as f:
        nodes = json.load(f)

    src_coord = None
    dst_coord = None
    for feat in nodes.get("features", []):
        pid = feat.get("properties", {}).get("id")
        if pid == src_id:
            src_coord = tuple(feat.get("geometry", {}).get("coordinates"))
        if pid == dst_id:
            dst_coord = tuple(feat.get("geometry", {}).get("coordinates"))

    if src_coord is None or dst_coord is None:
        raise ValueError("src or dst id not found in nodes geojson")

    # map to nearest network node
    src_nid = _find_nearest_node(src_coord, node_idx)
    dst_nid = _find_nearest_node(dst_coord, node_idx)

    # Find optimal path considering all factors
    path_node_ids, route_segments = _find_optimal_path(G, edge_lines, line_info, node_idx, src_nid, dst_nid)

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
        abs(src_coord[0] - first_segment_start[0]) > 1e-9 or 
        abs(src_coord[1] - first_segment_start[1]) > 1e-9
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
        abs(dst_coord[0] - last_segment_end[0]) > 1e-9 or 
        abs(dst_coord[1] - last_segment_end[1]) > 1e-9
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
        "summary": {
            "total_lines": len(lines_used),
            "total_distance_km": total_distance,
            "walking_distance_km": total_walking_distance,
            "transport_distance_km": total_distance - total_walking_distance,
            "transport_types_used": list(set(line["transport_type"] for line in lines_used.values()))
        }
    }
