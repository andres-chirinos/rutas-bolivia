# Documentación de Pruebas: RoutePlanner

Este documento detalla los diferentes casos de prueba implementados para la clase `RoutePlanner`, encargada del enrutamiento geográfico. Las pruebas están divididas según metodologías de Caja Blanca (pruebas basadas en el conocimiento interno del código) y Caja Negra (pruebas basadas puramente en entradas y salidas).

Las pruebas se encuentran implementadas en el archivo `tests/test_route_planner.py`.

---

## 1. Pruebas de Caja Blanca (`TestRoutePlannerWhiteBox`)

El propósito de la caja blanca es validar las lógicas internas, el correcto seguimiento de las rutas del código fuente y el manejo del estado interno como cálculos matemáticos y gestiones de caché.

### `test_haversine_km`
- **Objetivo**: Verificar el método privado `_haversine_km(pt1, pt2)` que realiza cálculos geográficos.
- **Explicación**: Comprueba la precisión y la lógica matemática interna (la fórmula de Haversine). Usando dos coordenadas de la ciudad de La Paz, se valida que el cálculo retorne un número flotante (float) positivo y que se aproxime a la medida real esperada, demostrando que la implementación no arroja fallos en cálculos matemáticos trigonométricos.

### `test_prepare_network_single`
- **Objetivo**: Analizar la ruta condicional de `_prepare_network()` cuando se le entrega solo un único archivo como entrada.
- **Explicación**: Asegura que el planificador no incurra en gastos innecesarios de I/O al procesar un solo origen. Valida que `merged_temp` retorne `None` (no se crean archivos en disco innecesarios) y que la llave de caché siga siendo idéntica a la ruta enviada.

### `test_prepare_network_multiple`
- **Objetivo**: Evaluar la ruta algorítmica donde se pasan múltiples archivos de red en `_prepare_network([archivos...])`.
- **Explicación**: Comprueba el código encargado de combinar varios archivos (`merge`). Valida que se genere temporalmente un archivo nuevo (existente en el disco) y mediante la inyección de `fixtures` mock de GeoJSON, verifica que el archivo final posea la colección de 'features' resultante de ambos archivos fusionados.

### `test_prepare_network_comma_separated`
- **Objetivo**: Verificar una sub-ruta oculta del código encargada del formateo de texto (`_prepare_network` con separación por comas).
- **Explicación**: El planificador tiene un *branch* de código (`if len(networks) == 1 and isinstance(networks[0], str) and "," in networks[0]`) que divide un solo string con valores separados por comas en listas de rutas individuales. Esta prueba valida directamente este comportamiento inyectando una cadena combinada `"archivo1.geojson, archivo2.geojson"`, demostrando que el programa lo expande e interactúa con el flujo de múltiples redes, generando correctamente un archivo temporal final (*merged_temp*).

### `test_cache_lru_behavior`
- **Objetivo**: Probar los mecanismos privados de gestión de la caché global (`_network_cache`, `_cache_set`, `_cache_get`).
- **Explicación**: Interviene en la variable de estado global de caché in-memory del servicio. Inserta más elementos del límite permitido por la política (`_NETWORK_CACHE_MAX`). Verifica que los elementos menos usados recientemente sean desalojados de la memoria para que nunca crezca infinitamente.

---

## 2. Pruebas de Caja Negra (`TestRoutePlannerBlackBox`)

Las pruebas de caja negra operan sin conocer la estructura del código, inyectando entradas (`inputs`) y observando si las salidas o excepciones (`outputs`/`raises`) obedecen el contrato establecido.

### `test_init_planner`
- **Objetivo**: Verificar la inicialización del objeto constructor de la clase.
- **Explicación**: Pasa un valor de prueba (`default_network`) en la instancia del objeto y asegura que retorne el mismo comportamiento guardado internamente mediante lectura de las propiedades públicas, sin acceder a métodos ocultos de estado.

### `test_route_by_coords_missing_network`
- **Objetivo**: Verificar las políticas defensivas de control de excepciones por entradas inválidas.
- **Explicación**: Se ejecutan solicitudes de ruta carentes de un parámetro requerido o indicando archivos fantasmas (que no existen en el sistema). Confirma que el sistema capture de manera elegante esta eventualidad devolviendo un explícito `FileNotFoundError` con mensajes de error entendibles para el usuario y no provocando cuelgues del sistema (crashes).

### `test_route_by_coords_astar_output_structure`
- **Objetivo**: Probar el comportamiento final del API al ser llamado por otros sistemas (el formato de salida o Response).
- **Explicación**: Hace una solicitud a `route_by_coords()` y analiza la respuesta completa. Dado que la construcción real de rutas por grafos es muy lenta para una prueba, se inyectan (*mocking*) resultados artificiales de las librerías dependientes. La prueba valida de manera estricta que la salida sea un Diccionario con las llaves `path_node_ids`, `route_geojson`, `lines_used` y `summary`, y que los componentes de resumen de distancias presenten los cálculos de kilómetros esperados dados unos resultados simulados.
