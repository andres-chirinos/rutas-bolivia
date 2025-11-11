"""Deprecated shim for route_planner.

This module was used temporarily during refactoring. Use `src.core.services.route_planner`
which contains the single canonical implementation.
"""

raise ImportError("route_planner_v2 is deprecated; import RoutePlanner from src.core.services.route_planner instead")
