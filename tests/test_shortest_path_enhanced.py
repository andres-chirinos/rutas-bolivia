#!/usr/bin/env python3
"""Test script for the enhanced shortest path algorithm."""

import json
import sys
import os
sys.path.append('plugins/graph_compute')

from shortest_path import shortest_path, get_transport_config, update_transport_config

def create_test_data():
    """Create simple test data to verify the algorithm."""
    # Create test nodes
    nodes = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-68.1193, -16.5000]},
                "properties": {"id": "start"}
            },
            {
                "type": "Feature", 
                "geometry": {"type": "Point", "coordinates": [-68.1093, -16.4900]},
                "properties": {"id": "end"}
            }
        ]
    }
    
    # Create test lines with different transport types
    lines = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "linea_roja_teleferico",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-68.1193, -16.5000],
                        [-68.1150, -16.4980],
                        [-68.1100, -16.4950],
                        [-68.1093, -16.4900]
                    ]
                },
                "properties": {
                    "tipo": "teleferico",
                    "name": "Línea Roja Teleférico"
                }
            },
            {
                "type": "Feature", 
                "id": "bus_301",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-68.1193, -16.5000],
                        [-68.1180, -16.4990],
                        [-68.1120, -16.4940]
                    ]
                },
                "properties": {
                    "tipo": "bus",
                    "name": "Bus 301"
                }
            },
            {
                "type": "Feature",
                "id": "minibus_234", 
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [-68.1120, -16.4940],
                        [-68.1100, -16.4920],
                        [-68.1093, -16.4900]
                    ]
                },
                "properties": {
                    "tipo": "minibus",
                    "name": "Minibus 234"
                }
            }
        ]
    }
    
    # Save test files
    with open("test_nodes.geojson", "w") as f:
        json.dump(nodes, f, indent=2)
    
    with open("test_lines.geojson", "w") as f:
        json.dump(lines, f, indent=2)

def test_routing():
    """Test the routing algorithm with different configurations."""
    print("🚀 Testing Enhanced Shortest Path Algorithm")
    print("=" * 50)
    
    # Create test data
    create_test_data()
    
    # Show current config
    config = get_transport_config()
    print("\n📋 Current Configuration:")
    for key, value in config.items():
        if key != "description":
            print(f"  {key}: {value}")
    
    # Test 1: Default preferences
    print("\n🛤️  Test 1: Default Transport Preferences")
    try:
        result = shortest_path("test_nodes.geojson", "test_lines.geojson", "start", "end")
        print(f"✅ Route found!")
        print(f"   Lines used: {result['summary']['total_lines']}")
        print(f"   Total distance: {result['summary']['total_distance_km']:.3f} km")
        print(f"   Walking distance: {result['summary']['walking_distance_km']:.3f} km")
        print(f"   Transport types: {result['summary']['transport_types_used']}")
        
        print("\n   Line details:")
        for line in result['lines_used']:
            print(f"     • {line['name']} ({line['transport_type']}) - {line['total_distance']:.3f} km")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Prefer buses over teleférico
    print("\n🚌 Test 2: Preferring Buses")
    update_transport_config(transport_weights={
        "teleferico": 3.0,  # Make teleférico less preferred
        "bus": 1.0,         # Make buses most preferred
        "minibus": 2.0
    })
    
    try:
        result = shortest_path("test_nodes.geojson", "test_lines.geojson", "start", "end")
        print(f"✅ Route found!")
        print(f"   Lines used: {result['summary']['total_lines']}")
        print(f"   Transport types: {result['summary']['transport_types_used']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 3: High transfer penalty (prefer walking)
    print("\n🚶 Test 3: High Transfer Penalty")
    update_transport_config(
        transfer_penalty=20.0,  # High penalty for transfers
        max_walking_distance_km=2.0  # Allow more walking
    )
    
    try:
        result = shortest_path("test_nodes.geojson", "test_lines.geojson", "start", "end")
        print(f"✅ Route found!")
        print(f"   Lines used: {result['summary']['total_lines']}")
        print(f"   Walking distance: {result['summary']['walking_distance_km']:.3f} km")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Cleanup
    os.remove("test_nodes.geojson")
    os.remove("test_lines.geojson")
    
    print("\n🎉 Tests completed!")

if __name__ == "__main__":
    test_routing()
