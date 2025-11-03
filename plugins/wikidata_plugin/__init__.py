"""
Wikidata Plugin para el Datamesh Client.

Este plugin proporciona capacidades para ejecutar queries SPARQL en Wikidata
y manejar los resultados como assets del datamesh con diccionarios de datos.
"""

from .plugin_interface import WikidataPlugin

# Exportar la clase para que sea descubierta por el PluginManager
__all__ = ['WikidataPlugin']
