"""
GeoServer Plugin para el Datamesh Client.

Este plugin proporciona capacidades para obtener layers de diferentes tipos
de geoservers y servicios OGC (WMS, WFS, WCS) en varios formatos.
"""

from .plugin_interface import GeoServerPlugin

# Exportar la clase para que sea descubierta por el PluginManager
__all__ = ['GeoServerPlugin']
