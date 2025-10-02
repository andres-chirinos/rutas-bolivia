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
TRANSFER_PENALTY = 2.0        # Reduced penalty for faster routing
WALKING_COST_PER_KM = 12.0    # Cost per km of walking
MAX_WALKING_DISTANCE_KM = 1.0 # Increased max walking distance
BOARDING_PENALTY = 1.0        # Small penalty for boarding transport


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
    if props.get("type") == "street" or "street" in str(feature.get("id", "")).lower():
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
    lines_geojson_path: str,
) -> Dict[str, Any]:
    """Build a multi-layer graph supporting streets, free lines, and station lines.
    Returns:
    - graph: NetworkX graph with multi-modal routing
    - node_index: maps node_id -> (lon, lat)
    - edge_lines: maps (node_id1, node_id2) -> list of line info dicts
    - line_info: maps line_id -> transport type and properties
    - stations: maps line_id -> list of station coordinates (for station_lines)
    """
    with open(lines_geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    G = nx.Graph()
    node_index: Dict[str, Tuple[float, float]] = {}
    edge_lines: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    line_info: Dict[str, Dict[str, Any]] = {}
    stations: Dict[str, List[Tuple[float, float]]] = {}

    def coord_id(coord: Tuple[float, float]) -> str:
        return f"{coord[0]:.5f},{coord[1]:.5f}"

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
                    
                    line_data = {
                        "line_id": line_id,
                        "transport_type": transport_type,
                        "layer_type": layer_type,
                        "weight": transport_weight,
                        "distance_km": distance
                    }
                    
                    add_edge(curr_node, next_node, transport_weight, distance, line_data)

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
                    
                    line_data = {
                        "line_id": line_id,
                        "transport_type": transport_type,
                        "layer_type": layer_type,
                        "weight": transport_weight + BOARDING_PENALTY,
                        "distance_km": distance
                    }
                    
                    add_edge(curr_node, next_node, transport_weight + BOARDING_PENALTY, distance, line_data)

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
                            
                            line_data = {
                                "line_id": line_id,
                                "transport_type": transport_type,
                                "layer_type": layer_type,
                                "weight": transport_weight + TRANSFER_PENALTY,
                                "distance_km": distance,
                                "is_station_connection": True
                            }
                            
                            add_edge(station1, station2, transport_weight + TRANSFER_PENALTY, distance, line_data)

    # Add selective walking connections between nearby nodes for multi-modal routing
    # Only connect nodes that are within walking distance and not already connected
    print("Adding walking connections...")
    node_list = list(node_index.items())
    walking_connections_added = 0
    
    # Use spatial indexing for efficiency - only check nearby nodes
    from collections import defaultdict
    spatial_grid = defaultdict(list)
    grid_size = 0.001  # Approximately 100m grid cells
    
    # Build spatial index
    for node_id, coord in node_list:
        grid_x = int(coord[0] / grid_size)
        grid_y = int(coord[1] / grid_size)
        spatial_grid[(grid_x, grid_y)].append((node_id, coord))
    
    # Only add walking connections between nodes in adjacent grid cells
    for (grid_x, grid_y), nodes_in_cell in spatial_grid.items():
        # Check current cell and 8 adjacent cells
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                adjacent_cell = (grid_x + dx, grid_y + dy)
                if adjacent_cell in spatial_grid:
                    for node1, coord1 in nodes_in_cell:
                        for node2, coord2 in spatial_grid[adjacent_cell]:
                            if node1 != node2 and not G.has_edge(node1, node2):
                                distance = _calculate_distance_km(coord1, coord2)
                                if distance <= MAX_WALKING_DISTANCE_KM:
                                    walking_weight = distance * WALKING_COST_PER_KM
                                    
                                    line_data = {
                                        "line_id": "walking",
                                        "transport_type": "walking",
                                        "layer_type": "street",
                                        "weight": walking_weight,
                                        "distance_km": distance,
                                        "is_walking": True
                                    }
                                    
                                    add_edge(node1, node2, walking_weight, distance, line_data)
                                    walking_connections_added += 1
    
    print(f"Added {walking_connections_added} walking connections")

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
    
    # Strategy 2: Try shortest path on existing graph
    try:
        if nx.has_path(G, src_nid, dst_nid):
            path_nodes = list(nx.shortest_path(G, source=src_nid, target=dst_nid, weight="weight"))
        else:
            raise nx.NetworkXNoPath("No direct path found")
    except nx.NetworkXNoPath:
        # Strategy 3: Find nearest connected nodes and create multi-segment route
        print(f"No direct path found. Attempting multi-segment routing...")
        
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
                    if nx.has_path(G, src_node, dst_node):
                        middle_path = list(nx.shortest_path(G, source=src_node, target=dst_node, weight="weight"))
                        
                        # Calculate total cost
                        total_cost = (src_walk_dist + dst_walk_dist) * WALKING_COST_PER_KM
                        path_cost = nx.shortest_path_length(G, source=src_node, target=dst_node, weight="weight")
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
    
    # Convert successful path to segments with line information
    segments = []
    current_line = None
    current_coords = []
    
    for i in range(len(path_nodes) - 1):
        current_node = path_nodes[i]
        next_node = path_nodes[i + 1]
        edge_key = tuple(sorted((current_node, next_node)))
        
        if edge_key in edge_lines:
            # Use the best available line for this edge
            best_line = min(edge_lines[edge_key], key=lambda x: x["weight"])
            line_id = best_line["line_id"]
            
            # If continuing on same line, extend current segment
            if line_id == current_line:
                current_coords.append(list(node_index[next_node]))
            else:
                # Finish previous segment if exists
                if current_line is not None and current_coords:
                    segments.append({
                        "type": "transport",
                        "line_id": current_line,
                        "transport_type": line_info.get(current_line, {}).get("transport_type", "unknown"),
                        "coordinates": current_coords,
                        "distance_km": sum(_calculate_distance_km(
                            tuple(current_coords[j]), tuple(current_coords[j+1])
                        ) for j in range(len(current_coords)-1)),
                        "cost": line_info.get(current_line, {}).get("weight", 0)
                    })
                
                # Start new segment
                current_line = line_id
                current_coords = [list(node_index[current_node]), list(node_index[next_node])]
    
    # Add final segment
    if current_line is not None and current_coords:
        segments.append({
            "type": "transport",
            "line_id": current_line,
            "transport_type": line_info.get(current_line, {}).get("transport_type", "unknown"),
            "coordinates": current_coords,
            "distance_km": sum(_calculate_distance_km(
                tuple(current_coords[j]), tuple(current_coords[j+1])
            ) for j in range(len(current_coords)-1)),
            "cost": line_info.get(current_line, {}).get("weight", 0)
        })
    
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

    # Build multi-layer network
    try:
        results = build_network_from_lines(lines_geojson)
        G = results["graph"]
        node_idx = results["node_index"]
        edge_lines = results["edge_lines"]
        line_info = results["line_info"]
        stations = results.get("stations", {})
        
        print(f"Built network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
    except Exception as e:
        raise ValueError(f"Failed to build network: {str(e)}")

    # Load nodes and find src/dst coordinates
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

    # Map to nearest network nodes
    src_nid = _find_nearest_node(src_coord, node_idx)
    dst_nid = _find_nearest_node(dst_coord, node_idx)
    
    print(f"Mapped {src_id} -> {src_nid}, {dst_id} -> {dst_nid}")

    # Find optimal path
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
        "summary": {
            "total_lines": len(lines_used),
            "total_distance_km": round(total_distance, 3),
            "walking_distance_km": round(total_walking_distance, 3),
            "transport_distance_km": round(total_distance - total_walking_distance, 3),
            "transport_types_used": list(set(line["transport_type"] for line in lines_used.values())),
            "layer_types_used": list(set(line["layer_type"] for line in lines_used.values()))
        }
    }
