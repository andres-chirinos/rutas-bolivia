import pytest
import os
import json
import tempfile
import uuid
from typing import Dict, Any

from plugins.expert_system.tourist_expert import TouristExpertSystem, get_tourist_recommendations

@pytest.fixture
def mock_places_data() -> list[Dict[str, Any]]:
    """Fixture que provee un listado simulado de lugares turísticos extraídos de Wikidata."""
    return [
        {
            "type": "Feature",
            "properties": {
                "id": "Q1",
                "label": "Museo Nacional de Arte",
                "typeLabel": "museo"
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "Q2",
                "label": "Plaza Murillo",
                "typeLabel": "plaza"
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "Q3",
                "label": "Parque Nacional Madidi",
                "typeLabel": "parque nacional"
            }
        },
        {
            "type": "Feature",
            "properties": {
                "id": "Q4",
                "label": "Tiwanaku",
                "typeLabel": "sitio arqueológico"
            }
        }
    ]

@pytest.fixture
def temp_places_file(mock_places_data):
    """Fixture que crea un archivo temporal simulando un dataset en disco."""
    tmpf = os.path.join(tempfile.gettempdir(), f"mock_places_{uuid.uuid4().hex}.geojson")
    with open(tmpf, "w", encoding="utf-8") as fh:
        json.dump({"features": mock_places_data}, fh)
    yield tmpf
    if os.path.exists(tmpf):
        os.remove(tmpf)

class TestTouristExpertSystem:
    """Pruebas Unitarias para el motor de inferencia (Sistema Experto)"""
    
    def test_initialization(self):
        """Prueba que el sistema se inicializa con sus reglas cargadas."""
        expert = TouristExpertSystem()
        assert len(expert.rules) > 0
        assert isinstance(expert.rules, list)

    def test_infer_recommendations_history(self, mock_places_data):
        """Prueba la inferencia cuando el usuario prefiere historia/arte."""
        expert = TouristExpertSystem()
        prefs = {"likes_history": True, "likes_nature": False}
        
        result = expert.infer_recommendations(prefs, mock_places_data)
        
        assert result["success"] is True
        assert result["rules_triggered"] >= 1
        
        # Debería recomendar el museo y el sitio arqueológico, pero no el parque nacional
        recommendations = result["recommendations"]
        labels = [place["properties"]["label"] for place in recommendations]
        
        assert "Museo Nacional de Arte" in labels
        assert "Tiwanaku" in labels
        assert "Parque Nacional Madidi" not in labels
        
        # Comprobar que el razonamiento menciona la historia
        assert any("historia" in msg.lower() for msg in result["reasoning"])

    def test_infer_recommendations_nature_and_family(self, mock_places_data):
        """Prueba de múltiples reglas solapándose y priorizando resultados (Scoring)."""
        expert = TouristExpertSystem()
        prefs = {"likes_nature": True, "with_family": True}
        
        result = expert.infer_recommendations(prefs, mock_places_data)
        
        # El parque nacional coincide con naturaleza, y plaza coincide con ambas (naturaleza y familia)
        recommendations = result["recommendations"]
        labels = [place["properties"]["label"] for place in recommendations]
        
        assert "Plaza Murillo" in labels
        assert "Parque Nacional Madidi" in labels
        assert result["rules_triggered"] >= 2
        
    def test_infer_recommendations_default(self, mock_places_data):
        """Prueba la regla de fallback cuando no hay preferencias marcadas."""
        expert = TouristExpertSystem()
        prefs = {"likes_history": False, "likes_nature": False} # Todo falso
        
        result = expert.infer_recommendations(prefs, mock_places_data)
        
        recommendations = result["recommendations"]
        labels = [place["properties"]["label"] for place in recommendations]
        
        # La regla default sugiere plazas y museos
        assert "Plaza Murillo" in labels
        assert "Museo Nacional de Arte" in labels

class TestExpertSystemPluginEntryPoint:
    """Pruebas para el entry point que consume el API."""
    
    def test_get_tourist_recommendations_valid_file(self, temp_places_file):
        """Prueba que el plugin carga correctamente un archivo geojson."""
        prefs = {"likes_history": True}
        result = get_tourist_recommendations(prefs, temp_places_file)
        
        assert result["success"] is True
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0

    def test_get_tourist_recommendations_invalid_file(self):
        """Prueba el manejo de errores si se pasa una ruta que no existe."""
        prefs = {"likes_history": True}
        result = get_tourist_recommendations(prefs, "ruta/inventada/que/no/existe.json")
        
        assert result["success"] is False
        assert "error" in result
        assert "no encontrado" in result["error"].lower()
