"""
Tests para el plugin GeoServer.

Este archivo contiene tests unitarios y de integración para validar
la funcionalidad del plugin de geoserver.
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import json

# Add the project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add plugin directory to path
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from plugin_interface import GeoServerPlugin
from geoserver_utils import GeoServerConnector, GEOSERVER_TYPES, OUTPUT_FORMATS


class TestGeoServerPlugin(unittest.TestCase):
    """Tests para la interfaz principal del plugin."""
    
    def setUp(self):
        """Setup para cada test."""
        self.plugin = GeoServerPlugin()
    
    def test_plugin_initialization(self):
        """Test inicialización del plugin."""
        self.assertEqual(self.plugin.NAME, "geoserver")
        self.assertIsInstance(self.plugin.connectors, dict)
    
    def test_get_available_methods(self):
        """Test obtener métodos disponibles."""
        methods = self.plugin.get_available_methods()
        
        expected_methods = [
            "get_capabilities", "list_layers", "download_layer",
            "batch_download", "get_server_info", "test_connection"
        ]
        
        for method in expected_methods:
            self.assertIn(method, methods)
            self.assertIn("description", methods[method])
            self.assertIn("parameters", methods[method])
            self.assertIn("returns", methods[method])
    
    def test_validate_method_parameters(self):
        """Test validación de parámetros."""
        # Test método válido con parámetros correctos
        validation = self.plugin.validate_method_parameters(
            "test_connection",
            base_url="http://localhost:8080/geoserver"
        )
        self.assertTrue(validation["valid"])
        self.assertEqual(len(validation["errors"]), 0)
        
        # Test método válido con parámetros faltantes
        validation = self.plugin.validate_method_parameters("test_connection")
        self.assertFalse(validation["valid"])
        self.assertIn("Required parameter 'base_url' missing", validation["errors"])
        
        # Test método inválido
        validation = self.plugin.validate_method_parameters("invalid_method")
        self.assertFalse(validation["valid"])
    
    def test_get_server_info(self):
        """Test obtener información del servidor."""
        result = self.plugin.execute_method("get_server_info")
        
        self.assertTrue(result["success"])
        server_info = result["result"]
        
        self.assertIn("supported_servers", server_info)
        self.assertIn("supported_formats", server_info)
        self.assertIn("services", server_info)
        self.assertEqual(server_info["plugin_version"], "1.0.0")


class TestGeoServerConnector(unittest.TestCase):
    """Tests para el conector de geoserver."""
    
    def setUp(self):
        """Setup para cada test."""
        self.base_url = "http://localhost:8080/geoserver"
        self.connector = GeoServerConnector(self.base_url)
    
    def test_connector_initialization(self):
        """Test inicialización del conector."""
        self.assertEqual(self.connector.base_url, self.base_url)
        self.assertEqual(self.connector.server_type, "geoserver")
        self.assertIsNone(self.connector.username)
        self.assertIsNone(self.connector.password)
    
    def test_connector_with_auth(self):
        """Test conector con autenticación."""
        connector = GeoServerConnector(
            self.base_url,
            username="admin",
            password="geoserver"
        )
        
        self.assertEqual(connector.username, "admin")
        self.assertEqual(connector.password, "geoserver")
        self.assertEqual(connector.session.auth, ("admin", "geoserver"))
    
    def test_connector_with_token(self):
        """Test conector con token."""
        token = "test_token_123"
        connector = GeoServerConnector(self.base_url, token=token)
        
        self.assertEqual(connector.token, token)
        self.assertEqual(
            connector.session.headers["Authorization"],
            f"Bearer {token}"
        )
    
    @patch('geoserver_utils.requests.Session.get')
    def test_get_capabilities_success(self, mock_get):
        """Test obtener capabilidades exitosamente."""
        # Mock XML response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities>
            <Capability>
                <Layer>
                    <Name>test:layer</Name>
                    <Title>Test Layer</Title>
                    <Abstract>Test layer description</Abstract>
                </Layer>
            </Capability>
        </WMS_Capabilities>'''
        mock_get.return_value = mock_response
        
        capabilities = self.connector.get_capabilities("WMS")
        
        self.assertNotIn("error", capabilities)
        self.assertEqual(capabilities["service"], "WMS")
        self.assertIn("layers", capabilities)
    
    @patch('geoserver_utils.requests.Session.get')
    def test_get_capabilities_error(self, mock_get):
        """Test error al obtener capabilidades."""
        mock_get.side_effect = Exception("Connection error")
        
        capabilities = self.connector.get_capabilities("WMS")
        
        self.assertIn("error", capabilities)
        self.assertIn("Connection error", capabilities["error"])
    
    def test_parse_wms_layers(self):
        """Test parsing de layers WMS."""
        xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <WMS_Capabilities>
            <Capability>
                <Layer>
                    <Name>test:layer1</Name>
                    <Title>Test Layer 1</Title>
                    <Abstract>First test layer</Abstract>
                </Layer>
                <Layer>
                    <Name>test:layer2</Name>
                    <Title>Test Layer 2</Title>
                </Layer>
            </Capability>
        </WMS_Capabilities>'''
        
        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_content)
        layers = self.connector._parse_wms_layers(root)
        
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0]["name"], "test:layer1")
        self.assertEqual(layers[0]["title"], "Test Layer 1")
        self.assertEqual(layers[0]["abstract"], "First test layer")
        self.assertEqual(layers[1]["name"], "test:layer2")
    
    def test_build_wfs_url(self):
        """Test construcción de URL WFS."""
        format_config = OUTPUT_FORMATS["geojson"]
        url = self.connector._build_wfs_url("test:layer", format_config)
        
        self.assertIn("service=WFS", url)
        self.assertIn("request=GetFeature", url)
        self.assertIn("typeName=test%3Alayer", url)
        self.assertIn("outputFormat=application%2Fjson", url)
    
    def test_build_wfs_url_with_params(self):
        """Test construcción de URL WFS con parámetros adicionales."""
        format_config = OUTPUT_FORMATS["geojson"]
        url = self.connector._build_wfs_url(
            "test:layer", 
            format_config,
            bbox="-180,-90,180,90",
            maxFeatures=100,
            crs="EPSG:4326"
        )
        
        self.assertIn("bbox=-180%2C-90%2C180%2C90", url)
        self.assertIn("maxFeatures=100", url)
        self.assertIn("srsName=EPSG%3A4326", url)


class TestPluginIntegration(unittest.TestCase):
    """Tests de integración del plugin."""
    
    def setUp(self):
        """Setup para cada test."""
        self.plugin = GeoServerPlugin()
    
    @patch('geoserver_utils.GeoServerConnector')
    def test_get_connector_caching(self, mock_connector_class):
        """Test que el conector se guarda en cache."""
        mock_connector = Mock()
        mock_connector_class.return_value = mock_connector
        
        base_url = "http://test.com"
        
        # Primera llamada
        connector1 = self.plugin._get_connector(base_url)
        
        # Segunda llamada con los mismos parámetros
        connector2 = self.plugin._get_connector(base_url)
        
        # Debe ser el mismo objeto (cached)
        self.assertEqual(connector1, connector2)
        self.assertEqual(mock_connector_class.call_count, 1)
    
    @patch('geoserver_utils.GeoServerConnector.get_capabilities')
    def test_test_connection_success(self, mock_get_capabilities):
        """Test conexión exitosa."""
        mock_get_capabilities.return_value = {
            "service": "WMS",
            "layers": [{"name": "test:layer"}],
            "server_config": {"name": "GeoServer"}
        }
        
        result = self.plugin.execute_method(
            "test_connection",
            base_url="http://localhost:8080/geoserver"
        )
        
        self.assertTrue(result["success"])
        connection_result = result["result"]
        self.assertEqual(connection_result["connection_status"], "success")
        self.assertEqual(connection_result["available_layers"], 1)
    
    @patch('geoserver_utils.GeoServerConnector.get_capabilities')
    def test_test_connection_failure(self, mock_get_capabilities):
        """Test fallo de conexión."""
        mock_get_capabilities.side_effect = Exception("Connection failed")
        
        result = self.plugin.execute_method(
            "test_connection",
            base_url="http://localhost:8080/geoserver"
        )
        
        self.assertTrue(result["success"])  # El método se ejecuta, pero la conexión falla
        connection_result = result["result"]
        self.assertEqual(connection_result["connection_status"], "failed")
        self.assertIn("Connection failed", connection_result["error"])
    
    @patch('geoserver_utils.GeoServerConnector.download_layer')
    @patch('geoserver_utils.create_asset_from_layer')
    def test_download_layer_success(self, mock_create_asset, mock_download):
        """Test descarga exitosa de layer."""
        # Mock file path
        mock_file_path = "/tmp/test_layer.geojson"
        mock_download.return_value = mock_file_path
        
        # Mock asset creation
        mock_asset = {
            "id": "test-asset-id",
            "title": "Test Layer",
            "data_uri": mock_file_path
        }
        mock_create_asset.return_value = mock_asset
        
        result = self.plugin.execute_method(
            "download_layer",
            base_url="http://localhost:8080/geoserver",
            layer_name="test:layer",
            output_format="geojson"
        )
        
        self.assertTrue(result["success"])
        download_result = result["result"]
        self.assertEqual(download_result["file_path"], mock_file_path)
        self.assertEqual(download_result["layer_name"], "test:layer")
        self.assertEqual(download_result["asset"], mock_asset)
    
    @patch('geoserver_utils.GeoServerConnector.download_layer')
    @patch('geoserver_utils.create_asset_from_layer')
    def test_batch_download_mixed_results(self, mock_create_asset, mock_download):
        """Test descarga en lote con resultados mixtos."""
        # Configurar mocks
        def download_side_effect(layer_name, **kwargs):
            if layer_name == "test:layer1":
                return "/tmp/layer1.geojson"
            else:
                raise Exception("Layer not found")
        
        mock_download.side_effect = download_side_effect
        mock_create_asset.return_value = {"id": "test-asset"}
        
        result = self.plugin.execute_method(
            "batch_download",
            base_url="http://localhost:8080/geoserver",
            layer_names=["test:layer1", "test:layer2"],
            output_format="geojson"
        )
        
        self.assertTrue(result["success"])
        batch_result = result["result"]
        
        self.assertEqual(batch_result["total_requested"], 2)
        self.assertEqual(batch_result["successful_downloads"], 1)
        self.assertEqual(batch_result["failed_downloads"], 1)
        self.assertEqual(len(batch_result["results"]), 1)
        self.assertEqual(len(batch_result["errors"]), 1)


class TestUtilityFunctions(unittest.TestCase):
    """Tests para funciones de utilidad."""
    
    def test_geoserver_types_config(self):
        """Test configuración de tipos de geoserver."""
        self.assertIn("geoserver", GEOSERVER_TYPES)
        self.assertIn("mapserver", GEOSERVER_TYPES)
        self.assertIn("arcgis", GEOSERVER_TYPES)
        self.assertIn("qgis", GEOSERVER_TYPES)
        
        for server_type, config in GEOSERVER_TYPES.items():
            self.assertIn("name", config)
            self.assertIn("description", config)
    
    def test_output_formats_config(self):
        """Test configuración de formatos de salida."""
        expected_formats = ["geojson", "shapefile", "gml", "kml", "csv", "json"]
        
        for fmt in expected_formats:
            self.assertIn(fmt, OUTPUT_FORMATS)
            format_config = OUTPUT_FORMATS[fmt]
            self.assertIn("mime_type", format_config)
            self.assertIn("extension", format_config)
            self.assertIn("service", format_config)
    
    def test_analyze_geojson(self):
        """Test análisis de archivo GeoJSON."""
        from geoserver_utils import analyze_geojson
        
        # Crear archivo temporal GeoJSON
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-74.0, 40.7]
                    },
                    "properties": {
                        "name": "Test Point",
                        "population": 1000
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(geojson_data, f)
            temp_file = f.name
        
        try:
            analysis = analyze_geojson(temp_file)
            
            self.assertEqual(analysis["feature_count"], 1)
            self.assertIn("Point", analysis["geometry_types"])
            self.assertIn("name", analysis["properties"])
            self.assertIn("population", analysis["properties"])
            
        finally:
            os.unlink(temp_file)
    
    def test_analyze_csv(self):
        """Test análisis de archivo CSV."""
        from geoserver_utils import analyze_csv
        
        # Crear archivo temporal CSV
        csv_content = "name,lat,lon,population\nTest City,40.7,-74.0,1000\nAnother City,41.0,-75.0,2000\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            temp_file = f.name
        
        try:
            analysis = analyze_csv(temp_file)
            
            self.assertEqual(analysis["feature_count"], 2)
            self.assertEqual(analysis["data_type"], "csv")
            self.assertIn("name", analysis["properties"])
            self.assertIn("lat", analysis["properties"])
            self.assertIn("lon", analysis["properties"])
            self.assertIn("population", analysis["properties"])
            
        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    # Configurar logging para tests
    import logging
    logging.basicConfig(level=logging.ERROR)
    
    # Ejecutar tests
    unittest.main(verbosity=2)
