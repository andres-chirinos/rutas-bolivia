"""
Puerto para plugins de obtención de datos (data fetching plugins).

Esta interfaz define el contrato que deben implementar los plugins que
obtienen datos de fuentes externas y los convierten en assets.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDataFetcherPlugin(ABC):
    """Puerto abstracto para plugins que obtienen datos de fuentes externas."""
    
    NAME: str = "base_fetcher"
    
    @abstractmethod
    def get_available_methods(self) -> Dict[str, Dict[str, Any]]:
        """
        Retorna un diccionario con todos los métodos disponibles del plugin.
        
        Returns:
            Dict con estructura:
            {
                "method_name": {
                    "description": "Descripción del método",
                    "parameters": {
                        "param_name": {
                            "type": "string|number|boolean|object",
                            "description": "Descripción del parámetro",
                            "required": True|False,
                            "default": "valor por defecto si aplica"
                        }
                    },
                    "returns": "Descripción de lo que retorna"
                }
            }
        """
        raise NotImplementedError
    
    @abstractmethod
    def execute_method(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta un método específico del plugin.
        
        Args:
            method_name: Nombre del método a ejecutar
            **kwargs: Argumentos del método
            
        Returns:
            Dict con la respuesta del método, incluyendo:
            - asset: información del asset creado (si aplica)
            - data: datos obtenidos
            - metadata: metadatos adicionales
        """
        raise NotImplementedError
    
    def get_method_info(self, method_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información específica de un método.
        
        Args:
            method_name: Nombre del método
            
        Returns:
            Dict con información del método o None si no existe
        """
        methods = self.get_available_methods()
        return methods.get(method_name)
    
    def validate_method_parameters(self, method_name: str, **kwargs) -> Dict[str, Any]:
        """
        Valida los parámetros de un método antes de ejecutarlo.
        
        Args:
            method_name: Nombre del método
            **kwargs: Parámetros a validar
            
        Returns:
            Dict con:
            - valid: True si es válido
            - errors: Lista de errores si no es válido
            - sanitized_params: Parámetros procesados y con defaults aplicados
        """
        method_info = self.get_method_info(method_name)
        if not method_info:
            return {
                "valid": False,
                "errors": [f"Method '{method_name}' not found"],
                "sanitized_params": {}
            }
        
        errors = []
        sanitized = {}
        
        required_params = method_info.get("parameters", {})
        
        # Verificar parámetros requeridos
        for param_name, param_info in required_params.items():
            if param_info.get("required", False) and param_name not in kwargs:
                errors.append(f"Required parameter '{param_name}' missing")
            elif param_name in kwargs:
                sanitized[param_name] = kwargs[param_name]
            elif "default" in param_info:
                sanitized[param_name] = param_info["default"]
        
        # Verificar parámetros extra
        for param_name in kwargs:
            if param_name not in required_params:
                errors.append(f"Unknown parameter '{param_name}'")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "sanitized_params": sanitized
        }
