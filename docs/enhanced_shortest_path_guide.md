# Enhanced Shortest Path Algorithm - Usage Guide

This enhanced version of the shortest path algorithm has been redesigned to optimize transport routes considering:

## 🎯 Key Features

### 1. **Transport Type Preferences**
Different transport modes have different weights (lower = better):
- **Teleférico**: 1.0 (most preferred)
- **Bus**: 2.0 (good option)
- **Minibus**: 3.0 (standard option)  
- **Taxi**: 4.0 (least preferred)

### 2. **Smart Transfer Decisions**
- Evaluates if using multiple lines is worth it vs. walking a bit more
- Configurable transfer penalty (default: 5.0 cost units)
- Considers walking up to 500m as reasonable alternative

### 3. **Detailed Route Breakdown**
Results now include:
- Separate information for each line used
- Walking vs transport distance breakdown
- Transfer points identification
- Transport type summary

## 🚀 Usage Examples

### Basic Usage
```python
from plugins.graph_compute.shortest_path import shortest_path

result = shortest_path(
    nodes_geojson="nodes.geojson",
    lines_geojson="lines.geojson", 
    src_id="start_point",
    dst_id="end_point"
)
```

### Customized Preferences
```python
# Prefer buses over teleférico
result = shortest_path(
    nodes_geojson="nodes.geojson",
    lines_geojson="lines.geojson",
    src_id="start_point", 
    dst_id="end_point",
    transport_preferences={
        "teleferico": 3.0,  # Less preferred
        "bus": 1.0,         # Most preferred
        "minibus": 2.0
    },
    max_walking_km=0.8,     # Allow more walking
    transfer_penalty=10.0    # Higher penalty for transfers
)
```

### Global Configuration
```python
from plugins.graph_compute.shortest_path import update_transport_config

# Update global preferences
update_transport_config(
    transport_weights={
        "teleferico": 1.0,
        "bus": 1.5, 
        "minibus": 3.0,
        "taxi": 5.0
    },
    transfer_penalty=7.0,
    max_walking_distance_km=0.6
)
```

## 📊 Result Structure

```python
{
    "path_node_ids": ["node1", "node2", ...],
    "route_geojson": {
        "type": "FeatureCollection",
        "features": [...]  # Detailed route segments
    },
    "lines_used": [
        {
            "line_id": "linea_roja",
            "transport_type": "teleferico", 
            "name": "Línea Roja Teleférico",
            "total_distance": 2.5,
            "segments": [...],
            "is_transfer": false
        }
    ],
    "summary": {
        "total_lines": 2,
        "total_distance_km": 3.2,
        "walking_distance_km": 0.4,
        "transport_distance_km": 2.8,
        "transport_types_used": ["teleferico", "bus"]
    }
}
```

## 🔧 Configuration Options

### Transport Weights
Lower values = more preferred:
- `teleferico`: Cable car/gondola
- `bus`: Large buses
- `minibus`: Shared vans/minibuses  
- `taxi`: Taxis and ride-sharing

### Distance & Penalty Settings
- `max_walking_km`: Maximum reasonable walking distance
- `transfer_penalty`: Cost penalty for changing lines
- `walking_cost_per_km`: Cost per km of walking

## 🎯 Algorithm Benefits

1. **Fewer Transfers**: Minimizes line changes when possible
2. **Smart Walking**: Considers walking short distances vs multiple transfers
3. **Transport Preferences**: Prioritizes preferred transport modes
4. **Practical Routes**: Optimizes for real-world usability, not just distance
5. **Detailed Information**: Provides complete breakdown for route planning

## 🚌 Line Property Detection

The algorithm automatically detects transport types from GeoJSON properties:
- Checks: `tipo`, `type`, `transport_type`, `mode`, `linea_tipo`
- Infers from names: "teleferico", "bus", "mini", "taxi" keywords
- Falls back to "default" type if undetected

## 💡 Tips for Best Results

1. **Include transport type** in your line GeoJSON properties
2. **Adjust penalties** based on your specific transport network
3. **Set reasonable walking limits** for your city/terrain
4. **Use transfer penalties** to reflect real-world inconvenience
5. **Test different configurations** to find optimal settings
