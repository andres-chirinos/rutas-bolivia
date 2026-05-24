import json
import os
from typing import Dict, Any, List

class TouristExpertSystem:
    """
    Sistema experto basado en reglas (Forward Chaining) para lugares turísticos y eventos.
    Deduce recomendaciones basadas en las preferencias del usuario cruzándolas con 
    los metadatos de los lugares turísticos de la base de datos (Ej. Wikidata).
    """
    def __init__(self):
        self.rules = []
        self._setup_rules()

    def _setup_rules(self):
        # Reglas del motor de inferencia.
        # Formato: (Función_de_condición, Tipos_recomendados, Mensaje_explicativo, Multiplicador_de_peso)
        
        self.rules.append({
            "condition": lambda prefs: prefs.get("likes_history", False) or prefs.get("likes_art", False),
            "target_types": ["museo", "monumento", "edificio histórico", "sitio arqueológico", "iglesia"],
            "message": "Dado que te interesa la historia y el arte, hemos priorizado los museos y la arquitectura patrimonial.",
            "weight": 2.0
        })
        
        self.rules.append({
            "condition": lambda prefs: prefs.get("likes_nature", False) or prefs.get("likes_outdoors", False),
            "target_types": ["parque", "plaza", "parque nacional", "montaña", "sitio arqueológico"],
            "message": "Como disfrutas de la naturaleza y el aire libre, estos espacios abiertos y parques te encantarán.",
            "weight": 2.0
        })
        
        self.rules.append({
            "condition": lambda prefs: prefs.get("with_family", False),
            "target_types": ["parque", "plaza", "museo"],
            "message": "Considerando que viajas en familia, te sugerimos espacios amplios, educativos y seguros.",
            "weight": 1.5
        })
        
        self.rules.append({
            "condition": lambda prefs: prefs.get("limited_time", False),
            "target_types": ["monumento", "plaza"],
            "message": "Debido a tu poco tiempo, te recomendamos puntos emblemáticos y céntricos de rápida visita.",
            "weight": 1.5
        })
        
        self.rules.append({
            "condition": lambda prefs: not any(prefs.values()),
            "target_types": ["plaza", "monumento", "museo"],
            "message": "Recomendaciones generales y sitios de interés principales para tu visita.",
            "weight": 1.0
        })

    def infer_recommendations(self, user_preferences: Dict[str, bool], available_places: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Ejecuta el motor de inferencia evaluando las reglas contra las preferencias
        y filtrando/ordenando los lugares turísticos en formato GeoJSON.
        """
        recommended_types = {}
        messages = []

        # Paso 1: Forward Chaining para activar las reglas
        for rule in self.rules:
            if rule["condition"](user_preferences):
                messages.append(rule["message"])
                for t in rule["target_types"]:
                    # Acumular peso si un tipo se recomienda por múltiples reglas
                    recommended_types[t] = recommended_types.get(t, 0) + rule["weight"]

        # Paso 2: Evaluar la base de hechos (available_places) contra las conclusiones
        scored_recommendations = []
        
        for place in available_places:
            props = place.get("properties", {})
            place_type = props.get("typeLabel", "").lower()
            
            # Verificar si el lugar encaja en alguna categoría recomendada
            if place_type in recommended_types:
                score = recommended_types[place_type]
                
                # Bonus por popularidad si estuviera disponible en las propiedades
                if "population" in props or "visitors" in props:
                    score += 0.5
                    
                scored_recommendations.append({
                    "score": score,
                    "place": place
                })
                
        # Paso 3: Ordenar por puntuación (Relevancia)
        scored_recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        # Extraer solo el objeto 'place' para devolver el formato esperado
        final_recommendations = [item["place"] for item in scored_recommendations]
        
        return {
            "success": True,
            "rules_triggered": len(messages),
            "reasoning": messages,
            "total_recommended": len(final_recommendations),
            "recommendations": final_recommendations
        }

def get_tourist_recommendations(user_preferences: Dict[str, bool], nodes_geojson_path: str = None) -> Dict[str, Any]:
    """
    Punto de entrada del plugin. Carga el dataset y ejecuta el sistema experto.
    """
    if not nodes_geojson_path or not os.path.exists(nodes_geojson_path):
        return {
            "success": False,
            "error": "Dataset de lugares turísticos no encontrado."
        }
        
    try:
        with open(nodes_geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        features = data.get("features", [])
        if not features:
            # Si el JSON no tiene formato FeatureCollection pero es lista de nodos estructurados
            features = data.get("data", [])
            if not features:
                features = data
            
        expert = TouristExpertSystem()
        result = expert.infer_recommendations(user_preferences, features)
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error procesando el sistema experto: {str(e)}"
        }
