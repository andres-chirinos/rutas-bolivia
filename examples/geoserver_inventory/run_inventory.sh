#!/bin/bash
# Script rápido para generar inventario completo

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🌍 Generando inventario completo de layers..."
echo "📁 Directorio: $SCRIPT_DIR"

cd "$PROJECT_ROOT"

# Activar entorno virtual si existe
if [ -f ".venv/bin/activate" ]; then
    echo "🐍 Activando entorno virtual..."
    source .venv/bin/activate
fi

# Ejecutar inventario
python "$SCRIPT_DIR/generate_layers_inventory.py" \
    "$SCRIPT_DIR/geoservers_catalog.json" \
    -o "$SCRIPT_DIR/layers_inventory_$(date +%Y%m%d_%H%M%S).csv"

echo "✅ Inventario completado!"
echo "📁 Archivos generados en: $SCRIPT_DIR"
ls -la "$SCRIPT_DIR"/*.csv 2>/dev/null || echo "📄 No se encontraron archivos CSV generados"
