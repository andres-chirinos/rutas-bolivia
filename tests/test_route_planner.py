import pytest
import os
import json
import tempfile
import uuid
import math
from unittest.mock import patch, MagicMock

from src.core.services.route_planner import RoutePlanner, _network_cache, _cache_get, _cache_set, _NETWORK_CACHE_MAX


@pytest.fixture
def mock_geojson_network():
    """Crea una red temporal de GeoJSON para pruebas."""
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-68.1193, -16.4897], [-68.1190, -16.4900]]
                },
                "properties": {
                    "OBJECTID": 1,
                    "nombre": "Ruta Test"
                }
            }
        ]
    }
    tmpf = os.path.join(tempfile.gettempdir(), f"test_network_{uuid.uuid4().hex}.geojson")
    with open(tmpf, "w", encoding="utf-8") as fh:
        json.dump(feature_collection, fh)
    yield tmpf
    if os.path.exists(tmpf):
        os.remove(tmpf)

@pytest.fixture
def mock_geojson_network_2():
    """Crea una segunda red temporal de GeoJSON para pruebas."""
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-68.1180, -16.4880], [-68.1170, -16.4870]]
                },
                "properties": {
                    "OBJECTID": 2,
                    "nombre": "Ruta Test 2"
                }
            }
        ]
    }
    tmpf = os.path.join(tempfile.gettempdir(), f"test_network_2_{uuid.uuid4().hex}.geojson")
    with open(tmpf, "w", encoding="utf-8") as fh:
        json.dump(feature_collection, fh)
    yield tmpf
    if os.path.exists(tmpf):
        os.remove(tmpf)

class TestRoutePlannerWhiteBox:
    """Pruebas de Caja Blanca para analizar el comportamiento interno y las rutas de código."""

    def test_haversine_km(self):
        """Verifica la lógica interna de cálculo de distancia."""
        planner = RoutePlanner()
        # Distancia entre dos puntos conocidos (ej: dos coordenadas cerca de La Paz)
        pt1 = (-68.1193, -16.4897)
        pt2 = (-68.1190, -16.4900)
        
        distance = planner._haversine_km(pt1, pt2)
        
        # Fórmula de haversine debería dar un resultado numérico positivo > 0
        assert isinstance(distance, float)
        assert distance > 0
        assert math.isclose(distance, 0.046, abs_tol=0.01) # Aprox 46 metros

    def test_prepare_network_single(self, mock_geojson_network):
        """Prueba de ruta interna para _prepare_network con un solo archivo."""
        planner = RoutePlanner()
        path, cache_key, merged_temp = planner._prepare_network(mock_geojson_network)
        
        assert path == mock_geojson_network
        assert cache_key == mock_geojson_network
        assert merged_temp is None # No debe crear archivo temporal para 1 solo archivo

    def test_prepare_network_multiple(self, mock_geojson_network, mock_geojson_network_2):
        """Prueba de ruta interna para _prepare_network con múltiples archivos (merge)."""
        planner = RoutePlanner()
        networks = [mock_geojson_network, mock_geojson_network_2]
        
        path, cache_key, merged_temp = planner._prepare_network(networks)
        
        assert path != mock_geojson_network
        assert path != mock_geojson_network_2
        assert cache_key == "|".join(sorted(networks))
        assert merged_temp is not None
        assert os.path.exists(merged_temp)
        
        # Verifica que se hizo merge correctamente
        with open(merged_temp, "r") as f:
            data = json.load(f)
            assert "features" in data
            assert len(data["features"]) == 2
            
        os.remove(merged_temp) # Limpiar cache manual
        
    def test_cache_lru_behavior(self):
        """Prueba de caja blanca sobre la variable global _network_cache para ver la lógica de límite LRU."""
        _network_cache.clear()
        
        # Insertar más elementos del límite
        for i in range(_NETWORK_CACHE_MAX + 2):
            _cache_set(f"key_{i}", {"data": i})
            
        assert len(_network_cache) == _NETWORK_CACHE_MAX
        assert "key_0" not in _network_cache # Los primeros elementos debieron ser eliminados
        
        # Comprobar hit en cache y que se mueva al final (reciente)
        val = _cache_get(f"key_{_NETWORK_CACHE_MAX + 1}")
        assert val == {"data": _NETWORK_CACHE_MAX + 1}
        _network_cache.clear()

    def test_prepare_network_comma_separated(self, mock_geojson_network, mock_geojson_network_2):
        """Prueba de caja blanca para verificar la expansión de redes separadas por comas."""
        planner = RoutePlanner()
        # Formar una cadena separada por comas con espacios
        network_str = f"{mock_geojson_network}, {mock_geojson_network_2}"
        
        path, cache_key, merged_temp = planner._prepare_network(network_str)
        
        # Debe comportarse igual que si hubiéramos pasado una lista
        expected_cache_key = "|".join(sorted([mock_geojson_network, mock_geojson_network_2]))
        
        assert cache_key == expected_cache_key
        assert merged_temp is not None
        assert os.path.exists(merged_temp)
        
        # Limpieza
        os.remove(merged_temp)



class TestRoutePlannerBlackBox:
    """Pruebas de Caja Negra para verificar el sistema desde las interfaces de entrada/salida."""

    def test_init_planner(self):
        """Prueba la inicialización normal y asignación de default."""
        planner = RoutePlanner(default_network="test.geojson")
        assert planner.default_network == "test.geojson"

    def test_route_by_coords_missing_network(self):
        """Prueba cómo maneja las excepciones ante falta de parámetros (archivos no existentes)."""
        planner = RoutePlanner()
        src = (-68.1500, -16.5000)
        dst = (-68.1000, -16.4800)
        
        with pytest.raises(FileNotFoundError, match="No network provided"):
            planner.route_by_coords(src, dst)
            
        with pytest.raises(FileNotFoundError, match="Network file not found"):
            planner.route_by_coords(src, dst, network="does_not_exist_file.geojson")

    @patch("plugins.graph_compute.shortest_path.build_network_from_lines")
    @patch("plugins.graph_compute.shortest_path._find_optimal_path")
    @patch("plugins.graph_compute.shortest_path._find_nearest_node")
    def test_route_by_coords_astar_output_structure(self, mock_find_nearest_node, mock_find_optimal_path, mock_build_network, mock_geojson_network):
        """
        Prueba la estructura general de retorno sin importar la implementación de astar 
        (mockeando las dependencias externas del plugin para no requerir grafos reales pesados).
        """
        # Preparar mocks
        mock_find_nearest_node.side_effect = ["nodo1", "nodo2"]
        mock_find_optimal_path.return_value = (
            ["nodo1", "nodo2"], 
            [{"type": "transport", "line_id": "linea1", "distance_km": 2.5, "coordinates": [[-68.1, -16.4], [-68.2, -16.5]]}]
        )
        
        mock_build_network.return_value = {
            "graph": MagicMock(),
            "node_index": {"nodo1": (-68.1, -16.4), "nodo2": (-68.2, -16.5)},
            "edge_lines": MagicMock(),
            "line_info": {"linea1": {"name": "Línea Test", "layer_type": "transporte"}}
        }
        
        # Limpiar caché para forzar la recreación
        _network_cache.clear()

        # Ejecutar caso
        planner = RoutePlanner(default_network=mock_geojson_network)
        src = (-68.1, -16.4)
        dst = (-68.2, -16.5)
        
        result = planner.route_by_coords(src, dst)
        
        # Verificaciones de Caja Negra (Salida esperada)
        assert isinstance(result, dict)
        assert "path_node_ids" in result
        assert "route_geojson" in result
        assert "lines_used" in result
        assert "summary" in result
        assert "requested" in result
        
        # Verifica la información requerida de entrada
        assert result["requested"]["src"] == list(src)
        assert result["requested"]["dst"] == list(dst)
        assert result["requested"]["planner"] == "astar"
        
        # Verifica formato summary
        assert result["summary"]["total_distance_km"] == 2.5
        assert result["summary"]["walking_distance_km"] == 0.0
        assert result["summary"]["transport_distance_km"] == 2.5
        assert result["summary"]["total_lines"] == 1
