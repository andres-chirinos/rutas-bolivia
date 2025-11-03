"""Plugin: produce a minimal HTML viewer using Leaflet for GeoJSON points and optional path."""
import json
from typing import List


def _escape(s: str) -> str:
  return s.replace("'", "\\'").replace('\n', ' ')


def visualize_geojson(
  geojson_path: str,
  out_html: str,
  path: List[str] | None = None,
  network_geojson: str | None = None,
  route_geojson: str | None = None,
):
  with open(geojson_path, "r", encoding="utf-8") as f:
    geo = json.load(f)

  markers_js = []
  id_to_coords = {}
  for feat in geo.get("features", []):
    lon, lat = feat["geometry"]["coordinates"]
    label = _escape(str(feat["properties"].get("label", "")))
    nid = feat["properties"].get("id")
    id_to_coords[nid] = [lat, lon]
    markers_js.append(f"L.marker([{lat},{lon}]).bindPopup('{label} ({nid})').addTo(map)")

  route_layer_js = ""
  if network_geojson:
    with open(network_geojson, "r", encoding="utf-8") as nf:
      net = json.load(nf)
    net_json = json.dumps(net)
    route_layer_js = (
      "var net = %s;\n"
      "var netLayer = L.geoJSON(net, {style: function(feature){ return {color: 'gray', weight:2}; }}).addTo(map);"
    ) % net_json

  path_js = ""
  if path:
    latlons = [id_to_coords[i] for i in path if i in id_to_coords]
    path_js = (
      "var path = L.polyline(%s, {color: 'blue', weight:3}).addTo(map);\nmap.fitBounds(path.getBounds());"
    ) % (json.dumps(latlons))

  html = """
  <!doctype html>
  <html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  </head>
  <body>
    <div id="map" style="width: 100%; height: 90vh"></div>
    <script>
    var map = L.map('map').setView([-16.5, -68.1], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19}).addTo(map);
    {MARKERS_JS}
  {ROUTE_LAYER_JS}
  {PATH_JS}
    </script>
  </body>
  </html>
  """
  # perform safe replacements
  markers_block = ";\n        ".join(markers_js)
  html = html.replace("{MARKERS_JS}", markers_block)
  html = html.replace("{ROUTE_LAYER_JS}", route_layer_js)
  html = html.replace("{PATH_JS}", path_js)

  with open(out_html, "w", encoding="utf-8") as f:
    f.write(html)

  return out_html
