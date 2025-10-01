from ..plugins.graph_compute.shortest_path import shortest_path
from ..plugins.geo_visualizer.visualize import visualize_geojson

res = shortest_path("museos_bo.geojson", "lineaspuma.geojson", "Q9046895", "Q98713454")
open("route.json", "w").write(__import__("json").dumps(res["route_geojson"], indent=2))
visualize_geojson(
    "museos_bo.geojson",
    "museos_route.html",
    path=None,
    network_geojson="lineaspuma.geojson",
    route_geojson="route.json",
)
print("done")
