// Async IIFE para usar await
(async () => {
  // Espera a que el DOM esté listo antes de inicializar el mapa
  await new Promise(requestAnimationFrame);

  // Carga Leaflet si no está presente
  if (!window.L) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);
    await new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
      s.onload = resolve;
      document.body.appendChild(s);
    });
  }

  // Solo muestra el mapa centrado en Bolivia
  const map = L.map("map").setView([-16.5, -68.1], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
  }).addTo(map);

  const apiUrl = "http://127.0.0.1:8001";
  const ALL_NETWORKS = encodeURIComponent(
    "dummy_datasets/vias_gamlp_catastro.geojson,dummy_datasets/rutas_recorridos_2025.geojson,dummy_datasets/lineasteleferico.geojson,dummy_datasets/puma_katari.geojson",
  );

  const info = document.getElementById("info");
  const refreshBtn = document.getElementById("refreshBtn");
  const loadLayersBtn = document.getElementById("loadLayersBtn");
  const clearCacheBtn = document.getElementById("clearCacheBtn");
  const searchEntityBtn = document.getElementById("searchEntityBtn");
  const searchKgBtn = document.getElementById("searchKgBtn");
  const enhanceKgBtn = document.getElementById("enhanceKgBtn");
  const analyzeDataBtn = document.getElementById("analyzeDataBtn");
  const searchPanel = document.getElementById("searchPanel");
  const kgSearchPanel = document.getElementById("kgSearchPanel");
  const enhanceKgPanel = document.getElementById("enhanceKgPanel");
  const analyzeDataPanel = document.getElementById("analyzeDataPanel");
  const entitySelect = document.getElementById("entitySelect");
  const radiusInput = document.getElementById("radiusInput");
  const executeSearchBtn = document.getElementById("executeSearchBtn");
  const closeSearchBtn = document.getElementById("closeSearchBtn");
  const kgQueryInput = document.getElementById("kgQueryInput");
  const kgTypeFilter = document.getElementById("kgTypeFilter");
  const executeKgSearchBtn = document.getElementById("executeKgSearchBtn");
  const closeKgSearchBtn = document.getElementById("closeKgSearchBtn");
  const kgSearchResults = document.getElementById("kgSearchResults");
  const externalQueryInput = document.getElementById("externalQueryInput");
  const externalSourceSelect = document.getElementById("externalSourceSelect");
  const searchExternalBtn = document.getElementById("searchExternalBtn");
  const closeEnhanceBtn = document.getElementById("closeEnhanceBtn");
  const externalResults = document.getElementById("externalResults");
  const datasetSelect = document.getElementById("datasetSelect");
  const autoEnhanceCheck = document.getElementById("autoEnhanceCheck");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const closeAnalyzeBtn = document.getElementById("closeAnalyzeBtn");
  const analysisResults = document.getElementById("analysisResults");
  const layerControls = document.getElementById("layerControls");
  const clearTourBtn = document.getElementById("clearTourBtn");
  const tourInfo = document.getElementById("tourInfo");
  const tourList = document.getElementById("tourList");
  const startRouteBtn = document.getElementById("startRouteBtn");
  const routeButtonContainer = document.getElementById("routeButtonContainer");
  const routeSidebar = document.getElementById("routeSidebar");
  const closeRouteSidebarBtn = document.getElementById("closeRouteSidebarBtn");
  const routeDetailsContent = document.getElementById("routeDetailsContent");
  const openSidebarBtn = document.getElementById("openSidebarBtn");
  const closeSidebarBtn = document.getElementById("closeSidebarBtn");
  const sidebar = document.getElementById("sidebar");

  // Variables para el modo tour (siempre activo)
  let selectedPlaces = [];
  let allNodes = null; // Almacenar todos los nodos disponibles
  let currentRouteDetails = null; // Almacenar detalles de la ruta actual

  // Sistema de caché para evitar peticiones repetidas
  const cache = {
    museums: null,
    datasets: new Map(),
    routes: new Map(),
    entitySearches: new Map(),
    kgSearches: new Map(),
    kgEntities: new Map(),

    // Generar clave para rutas
    getRouteKey(srcId, dstId, network) {
      return `${srcId}->${dstId}@${network}`;
    },

    // Generar clave para búsquedas de KG
    getKgSearchKey(query, entityType) {
      return `kg:${query}:${entityType || "all"}`;
    },

    // Caché de museos
    getMuseums() {
      return this.museums;
    },

    setMuseums(data) {
      this.museums = data;
      // Guardar en localStorage para persistencia
      try {
        localStorage.setItem(
          "museos_cache",
          JSON.stringify({
            data: data,
            timestamp: Date.now(),
          }),
        );
      } catch (e) {
        console.warn("No se pudo guardar en localStorage:", e);
      }
    },

    // Verificar si el caché de museos es válido (24 horas)
    isMuseumsCacheValid() {
      try {
        const cached = localStorage.getItem("museos_cache");
        if (!cached) return false;

        const parsed = JSON.parse(cached);
        const age = Date.now() - parsed.timestamp;
        const maxAge = 24 * 60 * 60 * 1000; // 24 horas

        if (age < maxAge) {
          this.museums = parsed.data;
          return true;
        }
      } catch (e) {
        console.warn("Error verificando caché:", e);
      }
      return false;
    },

    // Caché de datasets
    getDataset(filename) {
      return this.datasets.get(filename);
    },

    setDataset(filename, data) {
      this.datasets.set(filename, data);
    },

    // Caché de rutas
    getRoute(srcId, dstId, network) {
      const key = this.getRouteKey(srcId, dstId, network);
      return this.routes.get(key);
    },

    setRoute(srcId, dstId, network, data) {
      const key = this.getRouteKey(srcId, dstId, network);
      this.routes.set(key, data);

      // Limitar el tamaño del caché de rutas
      if (this.routes.size > 50) {
        const firstKey = this.routes.keys().next().value;
        this.routes.delete(firstKey);
      }
    },

    // Caché de búsquedas de entidad
    getEntitySearch(entityId, radius, includeMuseums, includeTransport) {
      const key = this.getEntitySearchKey(
        entityId,
        radius,
        includeMuseums,
        includeTransport,
      );
      return this.entitySearches.get(key);
    },

    setEntitySearch(entityId, radius, includeMuseums, includeTransport, data) {
      const key = this.getEntitySearchKey(
        entityId,
        radius,
        includeMuseums,
        includeTransport,
      );
      this.entitySearches.set(key, data);

      // Limitar el tamaño del caché de búsquedas
      if (this.entitySearches.size > 20) {
        const firstKey = this.entitySearches.keys().next().value;
        this.entitySearches.delete(firstKey);
      }
    },

    // Caché de búsquedas en KG
    getKgSearch(query, entityType) {
      const key = this.getKgSearchKey(query, entityType);
      return this.kgSearches.get(key);
    },

    setKgSearch(query, entityType, data) {
      const key = this.getKgSearchKey(query, entityType);
      this.kgSearches.set(key, data);

      // Limitar el tamaño del caché
      if (this.kgSearches.size > 30) {
        const firstKey = this.kgSearches.keys().next().value;
        this.kgSearches.delete(firstKey);
      }
    },

    // Caché de entidades específicas del KG
    getKgEntity(entityId) {
      return this.kgEntities.get(entityId);
    },

    setKgEntity(entityId, data) {
      this.kgEntities.set(entityId, data);

      // Limitar el tamaño del caché
      if (this.kgEntities.size > 50) {
        const firstKey = this.kgEntities.keys().next().value;
        this.kgEntities.delete(firstKey);
      }
    },
  };

  // Funciones para el modo tour
  function updateTourDisplay() {
    if (selectedPlaces.length === 0) {
      tourList.textContent = "Ningún lugar seleccionado";
      routeButtonContainer.style.display = "none";
    } else {
      const placeNames = selectedPlaces
        .map((place) => place.label || place.id)
        .join(" → ");
      tourList.textContent = `${selectedPlaces.length} lugares: ${placeNames}`;

      // Mostrar botón "Ver Ruta" centrado solo si hay al menos 2 lugares y existe una ruta calculada
      if (selectedPlaces.length >= 2 && currentRouteDetails) {
        routeButtonContainer.style.display = "block";
      } else {
        routeButtonContainer.style.display = "none";
      }
    }
  }

  // Función global para añadir lugares a la ruta desde los popups
  function addToTour(id, label, coordinates) {
    // Verificar si ya está seleccionado
    const existingIndex = selectedPlaces.findIndex((place) => place.id === id);

    if (existingIndex >= 0) {
      // Si ya está seleccionado, eliminarlo
      selectedPlaces.splice(existingIndex, 1);
      info.textContent = `${label} eliminado del tour.`;
    } else {
      // Si no está seleccionado, agregarlo
      const placeInfo = {
        id: id,
        label: label,
        coordinates: [coordinates[1], coordinates[0]], // [lon, lat] para GeoJSON
        latlng: { lat: coordinates[0], lng: coordinates[1] },
      };

      selectedPlaces.push(placeInfo);
      info.textContent = `${label} añadido al tour.`;
    }

    updateTourDisplay();
    updateTourMarkers();

    // Calcular ruta si hay al menos 2 lugares
    if (selectedPlaces.length >= 2) {
      setTimeout(calculateTourRoute, 500); // Pequeña pausa para mejor UX
    } else if (selectedPlaces.length === 0) {
      layerManager.removeLayer("route");
      layerManager.removeLayer("tourMarkers");
    }

    // Actualizar el popup activo para reflejar el nuevo estado
    const popup = map.getPopup();
    if (popup && popup.isOpen()) {
      // Recrear el contenido del popup con el nuevo estado
      const isNowInTour = selectedPlaces.some((place) => place.id === id);
      const buttonText = isNowInTour
        ? "➖ Quitar de la ruta"
        : "➕ Añadir a la ruta";
      const buttonColor = isNowInTour ? "#f44336" : "#4CAF50";

      const currentContent = popup.getContent();
      const updatedContent = currentContent.replace(
        /<button[^>]*onclick="window\.addToTour[^"]*"[^>]*>.*?<\/button>/,
        `<button onclick="window.addToTour('${id}', '${label.replace(/'/g, "\\'")}', [${coordinates[0]}, ${coordinates[1]}])" 
                         style="background: ${buttonColor}; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                    ${buttonText}
                </button>`,
      );

      popup.setContent(updatedContent);
    }
  }

  // Hacer la función global para que sea accesible desde los popups
  window.addToTour = addToTour;

  function toggleTourMode() {
    // Modo tour siempre activo - función removida pero mantenida por compatibilidad
    info.textContent =
      "Modo Tour activo. Haz clic en los museos para ver su información y añadirlos a la ruta.";
    map.getContainer().style.cursor = "crosshair";
  }

  function clearTour() {
    selectedPlaces = [];
    currentRouteDetails = null;
    updateTourDisplay();
    layerManager.removeLayer("route");
    layerManager.removeLayer("tourMarkers");
    closeRouteSidebar();
    info.textContent = "Tour limpiado.";

    // Limpiar información del panel de control
    const existingRouteInfo = layerControls.querySelectorAll(
      'div[style*="margin-top: 10px"]',
    );
    existingRouteInfo.forEach((el) => el.remove());
  }

  function showRouteDetails() {
    if (!currentRouteDetails) {
      info.textContent = "No hay detalles de ruta disponibles.";
      return;
    }

    const { segments, places } = currentRouteDetails;

    // Calcular estadísticas totales
    let totalDistance = 0;
    let totalWalkingDistance = 0;
    let totalTransportDistance = 0;
    let totalTransferTime = 0;
    const allLines = new Set();
    const transportTypes = new Set();

    segments.forEach((segment) => {
      if (segment.route && segment.route.summary) {
        const summary = segment.route.summary;
        totalDistance += summary.total_distance_km || 0;
        totalWalkingDistance += summary.walking_distance_km || 0;
        totalTransportDistance += summary.transport_distance_km || 0;
        totalTransferTime += summary.total_transfer_time_minutes || 0;
      }
      // Count transport modes from consolidated segments
      if (segment.route && segment.route.route_segments) {
        segment.route.route_segments.forEach((seg) => {
          const mode = seg.transport_type || seg.type;
          if (mode && mode !== 'walking') transportTypes.add(mode);
          allLines.add(mode);
        });
      }
    });

    // Generar contenido detallado
    let detailsHTML = `
            <div style="margin-bottom: 15px; padding: 10px; background: #f0f8ff; border-radius: 6px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">📊 Resumen General</h5>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
                    <div><strong>🎯 Lugares a visitar:</strong> ${places.length}</div>
                    <div><strong>🛣️ Segmentos de ruta:</strong> ${segments.length}</div>
                    <div><strong>📏 Distancia total:</strong> ${totalDistance.toFixed(2)} km</div>
                    <div><strong>🚶 Caminata:</strong> ${totalWalkingDistance.toFixed(2)} km</div>
                    <div><strong>🚌 En transporte:</strong> ${totalTransportDistance.toFixed(2)} km</div>
                    <div><strong>🔄 Tiempo transferencias:</strong> ${totalTransferTime.toFixed(0)} min</div>
                    <div><strong>🚇 Líneas diferentes:</strong> ${allLines.size}</div>
                    <div><strong>🚊 Tipos transporte:</strong> ${Array.from(transportTypes).join(", ")}</div>
                </div>
            </div>
            
            <div style="margin-bottom: 15px;">
                <h5 style="margin: 0 0 10px 0; color: #333;">🗺️ Itinerario Detallado</h5>
            </div>
        `;

    // Añadir detalles de cada segmento
    segments.forEach((segment, index) => {
      const from = segment.from;
      const to = segment.to;
      const route = segment.route;

      detailsHTML += `
                <div style="margin-bottom: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 6px; background: #fafafa;">
                    <h6 style="margin: 0 0 8px 0; color: #FF5722;">
                        ${index + 1}. ${from.label || from.id} → ${to.label || to.id}
                    </h6>
            `;

      if (route && route.summary) {
        const summary = route.summary;
        detailsHTML += `
                    <div style="font-size: 11px; margin-bottom: 8px;">
                        <span style="background: #e3f2fd; padding: 2px 6px; border-radius: 3px; margin-right: 4px;">
                            📏 ${summary.total_distance_km?.toFixed(2) || 0} km
                        </span>
                        <span style="background: #e8f5e8; padding: 2px 6px; border-radius: 3px; margin-right: 4px;">
                            🚶 ${summary.walking_distance_km?.toFixed(2) || 0} km
                        </span>
                        <span style="background: #fff3e0; padding: 2px 6px; border-radius: 3px;">
                            🚌 ${summary.transport_distance_km?.toFixed(2) || 0} km
                        </span>
                    </div>
                `;

        // Show visual transport timeline
        if (route.route_segments && route.route_segments.length > 0) {
          const modeColors = {
            walking: '#4CAF50',
            bus: '#2196F3',
            minibus: '#03A9F4',
            teleferico: '#9C27B0',
            taxi: '#FF9800',
            default: '#607D8B'
          };
          const modeLabels = {
            walking: 'Caminar',
            bus: 'Bus',
            minibus: 'Minibus',
            teleferico: 'Teleférico',
            taxi: 'Taxi',
            default: 'Transporte'
          };
          
          detailsHTML += `<div style="margin-top: 8px;">`;
          route.route_segments.forEach((seg, si) => {
            const mode = seg.transport_type || seg.type || 'default';
            const icon = getTransportIcon(mode);
            const color = modeColors[mode] || modeColors['default'];
            const label = modeLabels[mode] || mode;
            const dist = seg.distance_km?.toFixed(2) || '?';
            
            detailsHTML += `
              <div style="display: flex; align-items: center; margin: 4px 0;">
                <div style="width: 28px; height: 28px; border-radius: 50%; background: ${color}; color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0;">
                  ${icon}
                </div>
                <div style="flex: 1; height: 3px; background: ${color}; margin: 0 4px;"></div>
                <div style="font-size: 11px; color: #555; white-space: nowrap;">
                  <strong>${label}</strong> ${dist} km
                </div>
              </div>
            `;
            
            // Arrow between segments (except last)
            if (si < route.route_segments.length - 1) {
              detailsHTML += `<div style="text-align: center; font-size: 10px; color: #bbb; margin: -2px 0;">↓ cambio</div>`;
            }
          });
          detailsHTML += `</div>`;
        }
      } else {
        detailsHTML += `<div style="color: #999; font-size: 11px;">No hay detalles disponibles para este segmento</div>`;
      }

      detailsHTML += `</div>`;
    });

    // Mostrar sidebar de ruta con los detalles
    routeDetailsContent.innerHTML = detailsHTML;
    openRouteSidebar();

    info.textContent = "Detalles de la ruta mostrados. ¡Buen viaje!";
  }

  // Función auxiliar para obtener iconos de transporte
  function getTransportIcon(transportType) {
    const icons = {
      bus: "🚌",
      minibus: "🚐",
      taxi: "🚕",
      teleferico: "🚡",
      metro: "🚇",
      tram: "🚊",
      walk: "🚶",
      walking: "🚶",
      transfer: "🔄",
      default: "🚌",
    };
    return icons[transportType] || "🚌";
  }

  // Funciones para controlar la barra lateral
  function openSidebar() {
    sidebar.style.left = "0px";
    openSidebarBtn.style.display = "none";
  }

  function closeSidebar() {
    sidebar.style.left = "-350px";
    openSidebarBtn.style.display = "block";

    // Cerrar paneles abiertos cuando se cierra el sidebar
    searchPanel.style.display = "none";
    kgSearchPanel.style.display = "none";
    enhanceKgPanel.style.display = "none";
    analyzeDataPanel.style.display = "none";
  }

  // Funciones para controlar el sidebar de ruta
  function openRouteSidebar() {
    routeSidebar.style.right = "0px";
  }

  function closeRouteSidebar() {
    routeSidebar.style.right = "-400px";
  }

  async function searchByEntity() {
    const entityId = entitySelect.value;
    const radius = parseFloat(radiusInput.value) || 50;

    if (!entityId) {
      info.textContent = "Selecciona una entidad para buscar.";
      return;
    }

    info.textContent = `Buscando lugares relacionados con ${entitySelect.options[entitySelect.selectedIndex].text}...`;

    try {
      // Verificar caché primero
      let searchData = cache.getEntitySearch(entityId, radius, true, true);

      if (searchData) {
        console.log(`Búsqueda de entidad ${entityId} cargada desde caché`);
        renderEntitySearchResults(searchData);
      } else {
        // Realizar nueva búsqueda
        const searchUrl = `${apiUrl}/search/entity/${entityId}?radius_km=${radius}&include_museums=true&include_transport=true`;

        const response = await fetch(searchUrl);
        if (!response.ok) {
          throw new Error(
            `Error en búsqueda: ${response.status} ${response.statusText}`,
          );
        }

        searchData = await response.json();
        console.log("Resultados de búsqueda:", searchData);

        // Guardar en caché
        cache.setEntitySearch(entityId, radius, true, true, searchData);

        renderEntitySearchResults(searchData);
      }
    } catch (error) {
      console.error("Error en búsqueda por entidad:", error);
      info.textContent = `Error en búsqueda: ${error.message}`;
    }
  }

  function renderEntitySearchResults(searchData) {
    const entity = searchData.entity;
    const museums = searchData.museums;
    const transportNetworks = searchData.transport_networks || [];
    const stats = searchData.statistics;

    // Centrar mapa en la entidad
    if (entity && entity.coordinates) {
      map.setView([entity.coordinates[1], entity.coordinates[0]], 11);
    }

    // Limpiar capas anteriores de búsqueda
    layerManager.removeLayer("search_museums");
    layerManager.removeLayer("search_transport");
    layerManager.removeLayer("search_center");

    // Mostrar centro de búsqueda
    if (entity && entity.coordinates) {
      const centerLayer = L.layerGroup();

      // Marcador del centro
      const centerMarker = L.circleMarker(
        [entity.coordinates[1], entity.coordinates[0]],
        {
          radius: 12,
          fillColor: "#FF5722",
          color: "#D84315",
          weight: 3,
          opacity: 1,
          fillOpacity: 0.7,
        },
      );

      centerMarker.bindPopup(`
                <strong>🎯 Centro de Búsqueda</strong><br>
                <strong>${entity.name}</strong><br>
                Radio: ${entity.search_radius_km} km<br>
                Área: ${stats.search_area_km2.toFixed(0)} km²
            `);

      centerLayer.addLayer(centerMarker);

      // Círculo de radio de búsqueda
      const searchCircle = L.circle(
        [entity.coordinates[1], entity.coordinates[0]],
        {
          radius: entity.search_radius_km * 1000, // metros
          fillColor: "#FF5722",
          color: "#FF5722",
          weight: 2,
          opacity: 0.5,
          fillOpacity: 0.1,
        },
      );

      centerLayer.addLayer(searchCircle);
      layerManager.addLayer(
        "search_center",
        centerLayer,
        `Centro: ${entity.name}`,
      );
    }

    // Mostrar museos encontrados
    if (museums && museums.features && museums.features.length > 0) {
      const museumsLayer = L.geoJSON(museums, {
        pointToLayer: function (feature, latlng) {
          return L.circleMarker(latlng, {
            radius: 8,
            fillColor: "#4CAF50",
            color: "#2E7D32",
            weight: 2,
            opacity: 1,
            fillOpacity: 0.8,
          });
        },
        onEachFeature: function (feature, layer) {
          const props = feature.properties || {};
          const id = props.id || props.qid || feature.id;
          const label = props.label || props.name || "Museo";
          const description = props.description;
          const distance = props.distance_from_center_km || "N/A";

          // Verificar si ya está en el tour
          const isInTour = selectedPlaces.some((place) => place.id === id);
          const buttonText = isInTour
            ? "➖ Quitar de la ruta"
            : "➕ Añadir a la ruta";
          const buttonColor = isInTour ? "#f44336" : "#4CAF50";

          let popupContent = `
                        <div style="min-width: 200px;">
                            <h4 style="margin: 0 0 8px 0; color: #333;">🏛️ ${label}</h4>
                            ${description ? `<p style="margin: 4px 0; font-size: 12px; color: #666;">${description}</p>` : ""}
                            <p style="margin: 4px 0; font-size: 11px;"><strong>📏 Distancia:</strong> ${distance} km</p>
                            <p style="margin: 4px 0; font-size: 11px;"><strong>🆔 ID:</strong> ${id || "N/A"}</p>
                            <div style="margin-top: 10px; text-align: center;">
                                <button onclick="window.addToTour('${id}', '${label.replace(/'/g, "\\'")}', [${feature.geometry.coordinates[1]}, ${feature.geometry.coordinates[0]}])" 
                                        style="background: ${buttonColor}; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                    ${buttonText}
                                </button>
                            </div>
                        </div>
                    `;

          layer.bindPopup(popupContent);
        },
      });

      layerManager.addLayer(
        "search_museums",
        museumsLayer,
        `Museos (${museums.features.length})`,
      );
    }

    // Mostrar redes de transporte encontradas
    transportNetworks.forEach((network, index) => {
      if (
        network.data &&
        network.data.features &&
        network.data.features.length > 0
      ) {
        const networkLayer = L.geoJSON(network.data, {
          style: function (feature) {
            const colors = [
              "#2196F3",
              "#FF9800",
              "#9C27B0",
              "#E91E63",
              "#795548",
            ];
            return {
              color: colors[index % colors.length],
              weight: 2,
              opacity: 0.7,
            };
          },
          onEachFeature: function (feature, layer) {
            const props = feature.properties || {};
            const distance = props.distance_from_center_km || "N/A";

            layer.bindPopup(`
                            <strong>🚌 ${network.name}</strong><br>
                            ${props.line_id || props.name || "Línea de transporte"}<br>
                            Distancia: ${distance} km
                        `);
          },
        });

        layerManager.addLayer(
          `search_transport_${index}`,
          networkLayer,
          `${network.name} (${network.feature_count})`,
        );
      }
    });

    // Mostrar resumen en el panel
    showEntitySearchSummary(searchData);

    // Cerrar panel de búsqueda
    searchPanel.style.display = "none";

    info.textContent = `Búsqueda completada: ${stats.total_museums} museos, ${stats.total_transport_features} elementos de transporte encontrados.`;
  }

  function showEntitySearchSummary(searchData) {
    const entity = searchData.entity;
    const stats = searchData.statistics;
    const transportNetworks = searchData.transport_networks || [];

    // Limpiar información previa
    const existingSearchInfo = layerControls.querySelectorAll(
      'div[data-search-summary="true"]',
    );
    existingSearchInfo.forEach((el) => el.remove());

    let searchInfo = `<div data-search-summary="true" style="margin-top: 10px; padding: 10px; background: #fff3e0; border: 1px solid #ff9800; border-radius: 4px;">
            <h5 style="margin: 0 0 8px 0; color: #333;">🔍 Búsqueda: ${entity.name}</h5>
            <div style="font-size: 12px; line-height: 1.4;">
                <div><strong>Radio de búsqueda:</strong> ${entity.search_radius_km} km</div>
                <div><strong>Área total:</strong> ${stats.search_area_km2.toFixed(0)} km²</div>
                <div><strong>Museos encontrados:</strong> ${stats.total_museums}</div>
                <div><strong>Elementos de transporte:</strong> ${stats.total_transport_features}</div>
            </div>
        </div>`;

    if (transportNetworks.length > 0) {
      searchInfo += `<div data-search-summary="true" style="margin-top: 8px; padding: 10px; background: #fff3e0; border: 1px solid #ff9800; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">🚌 Redes de Transporte</h5>
                <div style="font-size: 11px;">`;

      transportNetworks.forEach((network) => {
        if (!network.error) {
          searchInfo += `
                        <div style="margin-bottom: 4px;">
                            <strong>${network.name}:</strong> ${network.feature_count} elementos
                        </div>`;
        }
      });

      searchInfo += `</div></div>`;
    }

    layerControls.innerHTML += searchInfo;
  }

  async function searchKnowledgeGraph() {
    const query = kgQueryInput.value.trim();
    const entityType = kgTypeFilter.value;

    if (!query) {
      info.textContent = "Ingresa un término de búsqueda.";
      return;
    }

    if (query.length < 2) {
      info.textContent =
        "El término de búsqueda debe tener al menos 2 caracteres.";
      return;
    }

    info.textContent = `Buscando "${query}" en el knowledge graph...`;
    kgSearchResults.innerHTML =
      '<div style="padding:10px; text-align:center;">🔍 Buscando...</div>';

    try {
      // Verificar caché primero
      let searchData = cache.getKgSearch(query, entityType);

      if (searchData) {
        console.log("Búsqueda KG cargada desde caché");
        renderKgSearchResults(searchData);
      } else {
        // Realizar nueva búsqueda
        const searchUrl = `${apiUrl}/kg/search?query=${encodeURIComponent(query)}&limit=50${entityType ? `&entity_type=${entityType}` : ""}`;

        const response = await fetch(searchUrl);
        if (!response.ok) {
          throw new Error(
            `Error en búsqueda KG: ${response.status} ${response.statusText}`,
          );
        }

        searchData = await response.json();
        console.log("Resultados búsqueda KG:", searchData);

        // Guardar en caché
        cache.setKgSearch(query, entityType, searchData);

        renderKgSearchResults(searchData);
      }
    } catch (error) {
      console.error("Error en búsqueda KG:", error);
      info.textContent = `Error en búsqueda: ${error.message}`;
      kgSearchResults.innerHTML = `<div style="padding:10px; color:red;">❌ Error: ${error.message}</div>`;
    }
  }

  function renderKgSearchResults(searchData) {
    const results = searchData.results || [];

    if (results.length === 0) {
      kgSearchResults.innerHTML =
        '<div style="padding:10px; color:#666;">🔍 No se encontraron resultados.</div>';
      info.textContent = `Sin resultados para "${searchData.query}"`;
      return;
    }

    let resultsHtml = `<div style="margin-bottom:8px; font-weight:bold;">
            ${results.length} resultado${results.length > 1 ? "s" : ""} encontrado${results.length > 1 ? "s" : ""}:
        </div>`;

    results.forEach((result, index) => {
      const entity = result.entity_data;
      const summary = result.summary;
      const kgId = result.kg_id;

      // Determinar ícono según el tipo
      let icon = "📄";
      if (summary.type === "process_instance") icon = "⚙️";
      else if (summary.type === "asset") icon = "💾";

      // Determinar color según relevancia
      const relevance = result.relevance_score || 0;
      let bgColor = "#f5f5f5";
      if (relevance > 80) bgColor = "#e8f5e8";
      else if (relevance > 50) bgColor = "#fff3e0";

      resultsHtml += `
                <div style="margin-bottom:8px; padding:10px; border:1px solid #ddd; border-radius:4px; background:${bgColor}; cursor:pointer;"
                     onclick="showEntityDetails('${kgId}')" title="Click para ver detalles">
                    <div style="display:flex; justify-content:space-between; align-items:start;">
                        <div style="flex:1;">
                            <div style="font-weight:bold; color:#333;">
                                ${icon} ${summary.title || "Sin título"}
                            </div>
                            <div style="font-size:11px; color:#666; margin:4px 0;">
                                Tipo: ${summary.type || "unknown"} | Relevancia: ${relevance}%
                            </div>
                            <div style="font-size:12px; color:#555; line-height:1.3;">
                                ${summary.description || "Sin descripción"}
                            </div>
                            ${summary.owner ? `<div style="font-size:10px; color:#888; margin-top:4px;">Owner: ${summary.owner}</div>` : ""}
                        </div>
                        <div style="margin-left:8px; font-size:10px; color:#999;">
                            ${summary.created_at ? new Date(summary.created_at).toLocaleDateString() : ""}
                        </div>
                    </div>
                </div>`;
    });

    kgSearchResults.innerHTML = resultsHtml;
    info.textContent = `${results.length} resultado${results.length > 1 ? "s" : ""} encontrado${results.length > 1 ? "s" : ""} para "${searchData.query}"`;
  }

  async function showEntityDetails(entityId) {
    info.textContent = `Cargando detalles de la entidad...`;

    try {
      // Verificar caché primero
      let entityData = cache.getKgEntity(entityId);

      if (entityData) {
        console.log("Detalles de entidad cargados desde caché");
        renderEntityDetails(entityData);
      } else {
        // Cargar detalles de la entidad
        const detailsUrl = `${apiUrl}/kg/entity/${entityId}?include_related=true`;

        const response = await fetch(detailsUrl);
        if (!response.ok) {
          throw new Error(
            `Error cargando entidad: ${response.status} ${response.statusText}`,
          );
        }

        entityData = await response.json();
        console.log("Detalles de entidad:", entityData);

        // Guardar en caché
        cache.setKgEntity(entityId, entityData);

        renderEntityDetails(entityData);
      }
    } catch (error) {
      console.error("Error cargando detalles:", error);
      info.textContent = `Error cargando detalles: ${error.message}`;
    }
  }

  function renderEntityDetails(entityData) {
    const entity = entityData.entity_data;
    const summary = entityData.summary;
    const related = entityData.related_entities || [];
    const files = entityData.files_and_datasets || [];
    const processes = entityData.processes || [];

    // Cerrar paneles de búsqueda
    kgSearchPanel.style.display = "none";
    searchPanel.style.display = "none";

    // Limpiar información previa de entidades
    const existingEntityInfo = layerControls.querySelectorAll(
      'div[data-entity-details="true"]',
    );
    existingEntityInfo.forEach((el) => el.remove());

    // Determinar ícono
    let icon = "📄";
    if (summary.type === "process_instance") icon = "⚙️";
    else if (summary.type === "asset") icon = "💾";

    let entityInfo = `<div data-entity-details="true" style="margin-top: 10px; padding: 10px; background: #f3e5f5; border: 1px solid #9c27b0; border-radius: 4px;">
            <h5 style="margin: 0 0 8px 0; color: #333;">${icon} ${summary.title || "Entidad"}</h5>
            <div style="font-size: 12px; line-height: 1.4;">
                <div><strong>Tipo:</strong> ${summary.type || "unknown"}</div>
                <div><strong>ID:</strong> ${entityData.entity_id}</div>
                ${summary.owner ? `<div><strong>Propietario:</strong> ${summary.owner}</div>` : ""}
                ${summary.created_at ? `<div><strong>Creado:</strong> ${new Date(summary.created_at).toLocaleDateString()}</div>` : ""}
                <div style="margin-top:6px;"><strong>Descripción:</strong><br>${summary.description || "Sin descripción"}</div>
            </div>
        </div>`;

    // Mostrar archivos/datasets relacionados
    if (files.length > 0) {
      entityInfo += `<div data-entity-details="true" style="margin-top: 8px; padding: 10px; background: #f3e5f5; border: 1px solid #9c27b0; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">💾 Archivos y Datasets</h5>
                <div style="font-size: 11px;">`;

      files.forEach((file) => {
        const exists = file.exists ? "✅" : "❌";
        const uri = file.uri || "N/A";
        const shortUri = uri.length > 50 ? uri.substring(0, 47) + "..." : uri;

        entityInfo += `
                    <div style="margin-bottom: 4px; padding: 4px; background: #fafafa; border-radius: 2px;">
                        ${exists} <strong>${file.kind || "file"}:</strong><br>
                        <span style="font-family: monospace; font-size: 10px; color: #666;">${shortUri}</span>
                    </div>`;
      });

      entityInfo += `</div></div>`;
    }

    // Mostrar entidades relacionadas
    if (related.length > 0) {
      entityInfo += `<div data-entity-details="true" style="margin-top: 8px; padding: 10px; background: #f3e5f5; border: 1px solid #9c27b0; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">🔗 Entidades Relacionadas</h5>
                <div style="font-size: 11px;">`;

      related.forEach((rel) => {
        const relSummary = rel.summary;
        let relIcon = "📄";
        if (relSummary.type === "process_instance") relIcon = "⚙️";
        else if (relSummary.type === "asset") relIcon = "💾";

        entityInfo += `
                    <div style="margin-bottom: 4px; padding: 4px; background: #fafafa; border-radius: 2px; cursor: pointer;"
                         onclick="showEntityDetails('${rel.entity_id}')" title="Click para ver detalles">
                        ${relIcon} <strong>${relSummary.title || "Sin título"}</strong><br>
                        <span style="color: #666;">Relación: ${rel.relationship}</span><br>
                        <span style="font-size: 10px; color: #888;">${relSummary.description || "Sin descripción"}</span>
                    </div>`;
      });

      entityInfo += `</div></div>`;
    }

    // Mostrar procesos relacionados
    if (processes.length > 0) {
      entityInfo += `<div data-entity-details="true" style="margin-top: 8px; padding: 10px; background: #f3e5f5; border: 1px solid #9c27b0; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">⚙️ Procesos Relacionados</h5>
                <div style="font-size: 11px;">`;

      processes.forEach((proc) => {
        const status = proc.status || "unknown";
        const statusColor =
          status === "success"
            ? "#4caf50"
            : status === "error"
              ? "#f44336"
              : "#ff9800";

        entityInfo += `
                    <div style="margin-bottom: 4px; padding: 4px; background: #fafafa; border-radius: 2px;">
                        ⚙️ <strong>${proc.process_class || "Proceso"}</strong><br>
                        <span style="color: #666;">Relación: ${proc.relationship}</span><br>
                        <span style="color: ${statusColor}; font-weight: bold;">Estado: ${status}</span><br>
                        ${proc.executed_at ? `<span style="font-size: 10px; color: #888;">Ejecutado: ${new Date(proc.executed_at).toLocaleDateString()}</span>` : ""}
                    </div>`;
      });

      entityInfo += `</div></div>`;
    }

    layerControls.innerHTML += entityInfo;
    info.textContent = `Detalles cargados para ${summary.title || "entidad"}: ${related.length} relaciones, ${files.length} archivos, ${processes.length} procesos`;
  }

  function clearEntityDetails() {
    const existingEntityInfo = layerControls.querySelectorAll(
      'div[data-entity-details="true"]',
    );
    existingEntityInfo.forEach((el) => el.remove());
  }

  async function searchExternalEntities() {
    const query = externalQueryInput.value.trim();
    const source = externalSourceSelect.value;

    if (!query) {
      info.textContent = "Ingresa un término de búsqueda.";
      return;
    }

    info.textContent = `Buscando "${query}" en ${source}...`;
    externalResults.innerHTML =
      '<div style="padding:10px; text-align:center;">🔍 Buscando en KG externo...</div>';

    try {
      const searchUrl = `${apiUrl}/kg/entities/external?query=${encodeURIComponent(query)}&source=${source}&limit=10`;

      const response = await fetch(searchUrl);
      if (!response.ok) {
        throw new Error(
          `Error en búsqueda externa: ${response.status} ${response.statusText}`,
        );
      }

      const searchData = await response.json();
      console.log("Resultados búsqueda externa:", searchData);

      renderExternalResults(searchData);
    } catch (error) {
      console.error("Error en búsqueda externa:", error);
      info.textContent = `Error en búsqueda externa: ${error.message}`;
      externalResults.innerHTML = `<div style="padding:10px; color:red;">❌ Error: ${error.message}</div>`;
    }
  }

  function renderExternalResults(searchData) {
    const results = searchData.results || [];

    if (results.length === 0) {
      externalResults.innerHTML =
        '<div style="padding:10px; color:#666;">🔍 No se encontraron entidades externas.</div>';
      info.textContent = `Sin resultados externos para "${searchData.query}"`;
      return;
    }

    let resultsHtml = `<div style="margin-bottom:8px; font-weight:bold;">
            ${results.length} entidad${results.length > 1 ? "es" : ""} encontrada${results.length > 1 ? "s" : ""} en ${searchData.source}:
        </div>`;

    results.forEach((result, index) => {
      resultsHtml += `
                <div style="margin-bottom:8px; padding:10px; border:1px solid #ddd; border-radius:4px; background:#f9f9f9;">
                    <div style="font-weight:bold; color:#333;">
                        🌐 ${result.title || "Sin título"}
                    </div>
                    <div style="font-size:11px; color:#666; margin:4px 0;">
                        ID: ${result.external_id} | Fuente: ${result.source}
                    </div>
                    <div style="font-size:12px; color:#555; line-height:1.3;">
                        ${result.description || "Sin descripción"}
                    </div>
                    ${result.url ? `<div style="font-size:10px; margin-top:4px;"><a href="${result.url}" target="_blank" style="color:#2196f3;">Ver en ${result.source}</a></div>` : ""}
                    <div style="margin-top:8px;">
                        <button onclick="createLocalEntity('${result.external_id}', '${result.source}', '${(result.title || "").replace(/'/g, "\\'")}', '${(result.description || "").replace(/'/g, "\\'")}')" 
                                style="background:#4caf50; color:white; padding:4px 8px; border:none; border-radius:4px; cursor:pointer; font-size:11px;">
                            ➕ Crear Entidad Local
                        </button>
                    </div>
                </div>`;
    });

    externalResults.innerHTML = resultsHtml;
    info.textContent = `${results.length} entidad${results.length > 1 ? "es" : ""} externa${results.length > 1 ? "s" : ""} encontrada${results.length > 1 ? "s" : ""} en ${searchData.source}`;
  }

  async function createLocalEntity(externalId, source, title, description) {
    try {
      info.textContent = "Creando entidad local...";

      const entityData = {
        title: title,
        type: "ExternalEntity",
        description: description,
        external_links: [
          {
            external_id: externalId,
            source: source,
            confidence: 0.9,
            relation_type: "same_as",
          },
        ],
        properties: {
          source_kg: source,
        },
        created_by: "user",
      };

      const response = await fetch(`${apiUrl}/kg/entities/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entityData),
      });

      if (!response.ok) {
        throw new Error(`Error creando entidad: ${response.status}`);
      }

      const result = await response.json();
      console.log("Entidad creada:", result);

      info.textContent = `✅ Entidad "${title}" creada exitosamente en el KG local`;
    } catch (error) {
      console.error("Error creando entidad:", error);
      info.textContent = `❌ Error creando entidad: ${error.message}`;
    }
  }

  async function analyzeDataset() {
    const selectedDataset = datasetSelect.value;
    const autoEnhance = autoEnhanceCheck.checked;

    if (!selectedDataset) {
      info.textContent = "Selecciona un dataset para analizar.";
      return;
    }

    info.textContent = `Analizando ${selectedDataset}...`;
    analysisResults.innerHTML =
      '<div style="padding:10px; text-align:center;">📊 Analizando estructura de datos...</div>';

    try {
      const analysisData = {
        dataset_path: selectedDataset,
      };

      const response = await fetch(`${apiUrl}/kg/describe/dataset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(analysisData),
      });

      if (!response.ok) {
        throw new Error(
          `Error en análisis: ${response.status} ${response.statusText}`,
        );
      }

      const result = await response.json();
      console.log("Análisis de dataset:", result);

      renderAnalysisResults(result);
    } catch (error) {
      console.error("Error en análisis:", error);
      info.textContent = `Error en análisis: ${error.message}`;
      analysisResults.innerHTML = `<div style="padding:10px; color:red;">❌ Error: ${error.message}</div>`;
    }
  }

  function renderAnalysisResults(analysisData) {
    const columns = analysisData.columns || [];
    const descriptions = analysisData.descriptions || {};

    if (columns.length === 0) {
      analysisResults.innerHTML =
        '<div style="padding:10px; color:#666;">📄 No se pudieron extraer columnas del dataset.</div>';
      return;
    }

    let resultsHtml = `<div style="margin-bottom:12px; font-weight:bold;">
            📊 Análisis de ${columns.length} columna${columns.length > 1 ? "s" : ""} en ${analysisData.dataset_path}:
        </div>`;

    columns.forEach((column) => {
      const desc = descriptions[column] || {};
      const semanticMatches = desc.semantic_meaning || [];
      const relatedEntities = desc.related_entities || [];

      resultsHtml += `
                <div style="margin-bottom:12px; padding:12px; border:1px solid #ddd; border-radius:6px; background:#fafafa;">
                    <div style="font-weight:bold; color:#333; margin-bottom:6px;">
                        📋 Columna: ${column}
                    </div>
                    <div style="margin-bottom:4px;">
                        <strong>Tipo inferido:</strong> <span style="color:#2196f3;">${desc.inferred_type || "general"}</span>
                    </div>
                    <div style="margin-bottom:6px; font-size:12px; color:#555;">
                        ${desc.suggested_description || "Sin descripción generada"}
                    </div>
                    
                    ${
                      semanticMatches.length > 0
                        ? `
                    <div style="margin-top:8px;">
                        <strong style="font-size:11px;">🔗 Coincidencias semánticas:</strong>
                        <div style="margin-top:4px;">
                            ${semanticMatches
                              .slice(0, 3)
                              .map(
                                (match) => `
                                <span style="display:inline-block; background:#e3f2fd; padding:2px 6px; border-radius:3px; font-size:10px; margin:2px;">
                                    ${match.entity_title || "Sin título"} (${Math.round(match.confidence * 100)}%)
                                </span>
                            `,
                              )
                              .join("")}
                        </div>
                    </div>`
                        : ""
                    }
                    
                    ${
                      relatedEntities.length > 0
                        ? `
                    <div style="margin-top:8px;">
                        <strong style="font-size:11px;">📊 Entidades relacionadas:</strong>
                        <div style="margin-top:4px;">
                            ${relatedEntities
                              .slice(0, 3)
                              .map(
                                (entity) => `
                                <span style="display:inline-block; background:#e8f5e9; padding:2px 6px; border-radius:3px; font-size:10px; margin:2px; cursor:pointer;"
                                      onclick="showEntityDetails('${entity.entity_id}')" title="Click para ver detalles">
                                    ${entity.entity_title || "Sin título"} (${Math.round(entity.similarity * 100)}%)
                                </span>
                            `,
                              )
                              .join("")}
                        </div>
                    </div>`
                        : ""
                    }
                </div>`;
    });

    analysisResults.innerHTML = resultsHtml;
    info.textContent = `✅ Análisis completado: ${columns.length} columnas analizadas`;
  }

  async function calculateTourRoute() {
    if (selectedPlaces.length < 2) {
      info.textContent =
        "Selecciona al menos 2 lugares para calcular una ruta.";
      return;
    }

    info.textContent = "Calculando ruta del tour...";

    try {
      // Calcular ruta punto a punto
      const routeSegments = [];
      const allRouteFeatures = [];
      const network = ALL_NETWORKS;

      for (let i = 0; i < selectedPlaces.length - 1; i++) {
        const src = selectedPlaces[i];
        const dst = selectedPlaces[i + 1];

        // Verificar caché primero
        let data = cache.getRoute(src.id, dst.id, network);

        if (data) {
          console.log(`Ruta ${src.id} -> ${dst.id} cargada desde caché`);
        } else {
          // Calcular nueva ruta
          const demoUrl = `${apiUrl}/demo/museums?src=${encodeURIComponent(src.id)}&dst=${encodeURIComponent(dst.id)}&network=${network}`;

          const resp = await fetch(demoUrl);
          if (resp.ok) {
            data = await resp.json();
            // Guardar en caché
            cache.setRoute(src.id, dst.id, network, data);
            console.log(
              `Ruta ${src.id} -> ${dst.id} calculada y guardada en caché`,
            );
          } else {
            console.error(
              `Error calculando ruta ${src.id} -> ${dst.id}: ${resp.status}`,
            );
            continue;
          }
        }

        const route = data.route && (data.route.route_geojson || data.route);

        if (route && route.features) {
          route.features.forEach((feature, index) => {
            // Marcar cada segmento con información del tramo del tour
            const modifiedFeature = {
              ...feature,
              properties: {
                ...feature.properties,
                tour_segment: i + 1,
                tour_from: src.label || src.id,
                tour_to: dst.label || dst.id,
                tour_total_segments: selectedPlaces.length - 1,
              },
            };
            allRouteFeatures.push(modifiedFeature);
          });

          routeSegments.push({
            from: src,
            to: dst,
            route: data.route,
          });
        }
      }

      // Renderizar la ruta completa
      if (allRouteFeatures.length > 0) {
        const completeRoute = {
          type: "FeatureCollection",
          features: allRouteFeatures,
        };

        // Guardar detalles de la ruta para el botón "Iniciar Ruta"
        currentRouteDetails = {
          segments: routeSegments,
          places: [...selectedPlaces],
          completeRoute: completeRoute,
          calculatedAt: new Date(),
        };

        renderTourRoute(completeRoute, routeSegments);

        // Mostrar resumen del tour
        let totalDistance = 0;
        let totalWalking = 0;
        let allLines = new Set();

        routeSegments.forEach((segment) => {
          if (segment.route && segment.route.summary) {
            totalDistance += segment.route.summary.total_distance_km;
            totalWalking += segment.route.summary.walking_distance_km;
            if (segment.route.lines_used) {
              segment.route.lines_used.forEach((line) =>
                allLines.add(line.line_id),
              );
            }
          }
        });

        // Actualizar display del tour para mostrar el botón
        updateTourDisplay();

        info.textContent = `Tour completo: ${selectedPlaces.length} lugares, ${totalDistance.toFixed(2)} km total, ${allLines.size} líneas de transporte`;
      } else {
        currentRouteDetails = null;
        updateTourDisplay();
        info.textContent = "No se pudo calcular la ruta del tour.";
      }
    } catch (error) {
      console.error("Error calculating tour route:", error);
      info.textContent = "Error al calcular la ruta del tour: " + error.message;
    }
  }

  function updateTourMarkers() {
    // Remover marcadores existentes
    layerManager.removeLayer("tourMarkers");

    if (selectedPlaces.length === 0) return;

    const markersLayer = L.layerGroup();

    selectedPlaces.forEach((place, index) => {
      let markerColor, markerIcon;

      if (index === 0) {
        // Primer lugar (origen)
        markerColor = "#4CAF50";
        markerIcon = "🚩";
      } else if (index === selectedPlaces.length - 1) {
        // Último lugar (destino)
        markerColor = "#F44336";
        markerIcon = "🏁";
      } else {
        // Lugares intermedios
        markerColor = "#FF9800";
        markerIcon = "📍";
      }

      const marker = L.circleMarker(place.latlng, {
        radius: 12,
        fillColor: markerColor,
        color: "#FFF",
        weight: 3,
        opacity: 1,
        fillOpacity: 0.8,
      });

      marker.bindPopup(`
                <strong>${markerIcon} Parada ${index + 1}</strong><br>
                ${place.label}<br>
                <small>Clic para eliminar del tour</small>
            `);

      // Permitir eliminar al hacer clic
      marker.on("click", function (e) {
        e.originalEvent.stopPropagation();
        selectedPlaces.splice(index, 1);
        updateTourDisplay();
        updateTourMarkers();

        if (selectedPlaces.length >= 2) {
          setTimeout(calculateTourRoute, 500);
        } else {
          layerManager.removeLayer("route");
        }
      });

      markersLayer.addLayer(marker);

      // Agregar número de parada
      const numberMarker = L.marker(place.latlng, {
        icon: L.divIcon({
          className: "tour-number",
          html: `<div style="background: ${markerColor}; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; border: 2px solid white;">${index + 1}</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
        }),
      });

      markersLayer.addLayer(numberMarker);
    });

    layerManager.addLayer("tourMarkers", markersLayer, "Lugares seleccionados");
  }

  function renderTourRoute(routeGeoJSON, routeSegments) {
    const routeLayer = L.layerGroup();

    // Colores para diferentes tipos de transporte
    const transportColors = {
      teleferico: "#E91E63",
      bus: "#2196F3",
      minibus: "#FF9800",
      taxi: "#9C27B0",
      walking: "#4CAF50",
    };

    // Colores para diferentes segmentos del tour
    const segmentColors = [
      "#F44336",
      "#2196F3",
      "#4CAF50",
      "#FF9800",
      "#9C27B0",
      "#795548",
      "#607D8B",
    ];

    let segmentCount = 0;

    if (routeGeoJSON.features && Array.isArray(routeGeoJSON.features)) {
      routeGeoJSON.features.forEach((feature, index) => {
        const props = feature.properties || {};
        const source = props.source || "unknown";
        const transportType = props.transport_type || "unknown";
        const lineId = props.line_id || null;
        const isTransfer = props.transfer || false;
        const tourSegment = props.tour_segment || 1;

        let color, weight, opacity, dashArray;

        if (
          source === "walking" ||
          source === "walk_to_network" ||
          source === "walk_from_network"
        ) {
          color = transportColors.walking;
          weight = 4;
          opacity = 0.7;
          dashArray = "10, 5";
        } else if (source === "transport") {
          color =
            transportColors[transportType] ||
            segmentColors[(tourSegment - 1) % segmentColors.length];
          weight = isTransfer ? 6 : 5;
          opacity = 0.9;
          dashArray = isTransfer ? "15, 5, 5, 5" : null;
        } else {
          color = segmentColors[(tourSegment - 1) % segmentColors.length];
          weight = 3;
          opacity = 0.6;
        }

        try {
          const lineLayer = L.geoJSON(feature, {
            style: {
              color: color,
              weight: weight,
              opacity: opacity,
              dashArray: dashArray,
            },
          });

          let popupContent = `<strong>Tour: Segmento ${tourSegment}</strong><br>`;
          if (props.tour_from && props.tour_to) {
            popupContent += `De: ${props.tour_from}<br>A: ${props.tour_to}<br>`;
          }
          if (lineId) {
            popupContent += `Línea: ${lineId}<br>`;
          }
          if (transportType !== "unknown") {
            popupContent += `Tipo: ${transportType}<br>`;
          }
          if (props.distance_km) {
            popupContent += `Distancia: ${props.distance_km.toFixed(3)} km<br>`;
          }
          if (isTransfer) {
            popupContent += `<span style="color: orange;">⚡ Transferencia</span><br>`;
          }
          popupContent += `Fuente: ${source}`;

          lineLayer.bindPopup(popupContent);
          routeLayer.addLayer(lineLayer);
          segmentCount++;
        } catch (e) {
          console.error("Error processing tour route segment:", e, feature);
        }
      });
    }

    layerManager.addLayer("route", routeLayer, "Ruta del Tour");

    // Ajustar vista al tour completo
    if (routeLayer.getLayers().length > 0) {
      try {
        const bounds = routeLayer.getBounds();
        if (isValidBounds(bounds)) {
          map.fitBounds(bounds, { padding: [20, 20] });
        }
      } catch (e) {
        console.warn("Could not fit bounds for tour route:", e);
      }
    }

    // Mostrar información del tour en el panel
    showTourSummary(routeSegments);
  }

  function showTourSummary(routeSegments) {
    // Limpiar información previa
    const existingRouteInfo = layerControls.querySelectorAll(
      'div[style*="margin-top: 10px"]',
    );
    existingRouteInfo.forEach((el) => el.remove());

    let totalDistance = 0;
    let totalWalking = 0;
    let totalTransport = 0;
    const allLines = new Set();
    const transportTypes = new Set();

    routeSegments.forEach((segment) => {
      if (segment.route && segment.route.summary) {
        totalDistance += segment.route.summary.total_distance_km;
        totalWalking += segment.route.summary.walking_distance_km;
        totalTransport += segment.route.summary.transport_distance_km;

        if (segment.route.lines_used) {
          segment.route.lines_used.forEach((line) => {
            allLines.add(line.line_id);
            transportTypes.add(line.transport_type);
          });
        }
      }
    });

    let tourInfo = `<div style="margin-top: 10px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
            <h5 style="margin: 0 0 8px 0; color: #333;">🗺️ Resumen del Tour</h5>
            <div style="font-size: 12px; line-height: 1.4;">
                <div><strong>Lugares a visitar:</strong> ${selectedPlaces.length}</div>
                <div><strong>Segmentos de ruta:</strong> ${routeSegments.length}</div>
                <div><strong>Distancia total:</strong> ${totalDistance.toFixed(2)} km</div>
                <div><strong>Caminata:</strong> ${totalWalking.toFixed(2)} km</div>
                <div><strong>Transporte:</strong> ${totalTransport.toFixed(2)} km</div>
                <div><strong>Líneas usadas:</strong> ${allLines.size}</div>
            </div>
        </div>`;

    // Mostrar itinerario detallado
    if (routeSegments.length > 0) {
      tourInfo += `<div style="margin-top: 8px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
                <h5 style="margin: 0 0 8px 0; color: #333;">📋 Itinerario</h5>
                <div style="font-size: 11px;">`;

      routeSegments.forEach((segment, idx) => {
        const summary = segment.route.summary || {};
        tourInfo += `
                    <div style="margin-bottom: 6px; padding: 4px; background: #f5f5f5; border-radius: 2px;">
                        <strong>${idx + 1}. ${segment.from.label} → ${segment.to.label}</strong><br>
                        <span style="color: #666;">
                            ${summary.total_distance_km ? summary.total_distance_km.toFixed(2) + " km" : "N/A"} • 
                            ${summary.total_lines || 0} líneas • 
                            ${summary.walking_distance_km ? summary.walking_distance_km.toFixed(2) + " km caminata" : "0 km caminata"}
                        </span>
                    </div>`;
      });

      tourInfo += `</div></div>`;
    }

    layerControls.innerHTML += tourInfo;
  }

  // Sistema de gestión de capas expandido
  const layerManager = {
    layers: {
      network_rutas: {
        layer: null,
        name: "Rutas Puma Katari",
        visible: false,
        zIndex: 1,
        color: "#2196F3",
      },
      network_vias: {
        layer: null,
        name: "Vías GAMLP",
        visible: false,
        zIndex: 2,
        color: "#FF9800",
      },
      network_calles: {
        layer: null,
        name: "Red Puma Katari",
        visible: false,
        zIndex: 3,
        color: "#9C27B0",
      },
      network_teleferico: {
        layer: null,
        name: "Líneas Teleférico",
        visible: false,
        zIndex: 4,
        color: "#E91E63",
      },
      network_igm: {
        layer: null,
        name: "Caminos IGM",
        visible: false,
        zIndex: 5,
        color: "#795548",
      },
      nodes: {
        layer: null,
        name: "Museos",
        visible: true,
        zIndex: 6,
        color: "#4CAF50",
      },
      route: {
        layer: null,
        name: "Ruta calculada",
        visible: true,
        zIndex: 7,
        color: "#F44336",
      },
      tourMarkers: {
        layer: null,
        name: "Lugares seleccionados",
        visible: true,
        zIndex: 8,
        color: "#FF5722",
      },
      search_center: {
        layer: null,
        name: "Centro de búsqueda",
        visible: true,
        zIndex: 9,
        color: "#FF5722",
      },
      search_museums: {
        layer: null,
        name: "Museos encontrados",
        visible: true,
        zIndex: 10,
        color: "#4CAF50",
      },
      search_transport: {
        layer: null,
        name: "Transporte encontrado",
        visible: true,
        zIndex: 11,
        color: "#2196F3",
      },
    },

    // Configuración de datasets disponibles
    datasets: {
      "rutas_recorridos_2025.geojson": {
        name: "Rutas de Transporte Publico",
        description:
          "Líneas de transporte público de Bus, Micro, Minibus, Carry y Trufi",
        style: { color: "#2196F3", weight: 3, opacity: 0.7 },
        layer_key: "network_rutas",
      },
      "vias_gamlp_catastro.geojson": {
        name: "Vías GAMLP",
        description: "Red vial del catastro municipal GAMLP",
        style: { color: "#FF9800", weight: 2, opacity: 0.6 },
        layer_key: "network_vias",
      },
      "puma_katari.geojson": {
        name: "Red Puma Katari",
        description: "Red completa del sistema Puma Katari",
        style: { color: "#9C27B0", weight: 2, opacity: 0.5 },
        layer_key: "network_calles",
      },
      "lineasteleferico.geojson": {
        name: "Líneas Teleférico",
        description: "Red de teleférico Mi Teleférico La Paz",
        style: { color: "#E91E63", weight: 4, opacity: 0.8 },
        layer_key: "network_teleferico",
      },
      "caminos_igm250000.geojson": {
        name: "Caminos IGM",
        description:
          "Red de caminos del Instituto Geográfico Militar escala 1:250000",
        style: { color: "#795548", weight: 1, opacity: 0.4 },
        layer_key: "network_igm",
      },
    },

    addLayer(key, layer, name) {
      // Si es una capa de búsqueda de transporte dinámico, crear entrada dinámicamente
      if (key.startsWith("search_transport_") && !this.layers[key]) {
        this.layers[key] = {
          layer: null,
          name: name || "Transporte búsqueda",
          visible: true,
          zIndex: 11 + parseInt(key.split("_")[2] || 0),
          color: "#2196F3",
        };
      }

      if (this.layers[key] && this.layers[key].layer) {
        map.removeLayer(this.layers[key].layer);
      }

      if (!this.layers[key]) {
        // Crear entrada para capas dinámicas
        this.layers[key] = {
          layer: null,
          name: name || key,
          visible: true,
          zIndex: Object.keys(this.layers).length + 1,
          color: "#666666",
        };
      }

      this.layers[key].layer = layer;
      if (name) this.layers[key].name = name;

      // Asegurar que la capa se agregue al mapa si está marcada como visible
      if (this.layers[key].visible) {
        map.addLayer(layer);
      }

      this.updateLayerOrder();
      this.renderControls();
    },

    async addLayerFromDataset(datasetName, url = null) {
      const dataset = this.datasets[datasetName];
      if (!dataset) {
        console.error("Dataset no encontrado:", datasetName);
        return false;
      }

      // Verificar caché primero
      let data = cache.getDataset(datasetName);
      if (data) {
        console.log(`Dataset ${dataset.name} cargado desde caché`);
        const statusInfo = document.getElementById("statusInfo");
        if (statusInfo)
          statusInfo.textContent = `${dataset.name} cargada desde caché`;
      } else {
        // URL por defecto si no se proporciona
        const dataUrl = url || `http://localhost:8001/files/${datasetName}`;

        try {
          console.log(`Cargando dataset: ${dataset.name}`);
          const statusInfo = document.getElementById("statusInfo");
          if (statusInfo)
            statusInfo.textContent = `Cargando ${dataset.name}...`;

          const response = await fetch(dataUrl);
          if (!response.ok) {
            throw new Error(
              `Error al cargar ${datasetName}: ${response.statusText}`,
            );
          }

          data = await response.json();
          console.log(`Dataset ${datasetName} cargado:`, data);

          // Guardar en caché
          cache.setDataset(datasetName, data);
        } catch (error) {
          console.error(`Error cargando ${datasetName}:`, error);
          const statusInfo = document.getElementById("statusInfo");
          if (statusInfo)
            statusInfo.textContent = `Error cargando ${dataset.name}: ${error.message}`;
          return false;
        }
      }

      try {
        // Crear capa con estilo personalizado
        const layer = L.geoJSON(data, {
          style: (feature) => ({
            ...dataset.style,
            fillColor: dataset.style.color,
            fillOpacity: dataset.style.opacity * 0.3,
          }),
          pointToLayer: (feature, latlng) => {
            return L.circleMarker(latlng, {
              radius: 4,
              ...dataset.style,
              fillColor: dataset.style.color,
              fillOpacity: 0.6,
            });
          },
        });

        // Guardar referencia a la capa
        const layerInfo = this.layers[dataset.layer_key];
        if (layerInfo.layer) {
          // Remover capa existente
          map.removeLayer(layerInfo.layer);
        }

        layerInfo.layer = layer;

        // Agregar al mapa si está visible
        if (layerInfo.visible) {
          map.addLayer(layer);
        }

        console.log(`Capa ${dataset.name} agregada exitosamente`);
        const statusInfo = document.getElementById("statusInfo");
        if (statusInfo)
          statusInfo.textContent = `${dataset.name} cargada exitosamente`;

        // Actualizar control de capas
        this.updateLayerOrder();
        this.renderControls();

        return true;
      } catch (error) {
        console.error(`Error procesando ${datasetName}:`, error);
        const statusInfo = document.getElementById("statusInfo");
        if (statusInfo)
          statusInfo.textContent = `Error procesando ${dataset.name}: ${error.message}`;
        return false;
      }
    },

    removeLayer(key) {
      if (this.layers[key] && this.layers[key].layer) {
        map.removeLayer(this.layers[key].layer);
        this.layers[key].layer = null;
      }
      this.renderControls();
    },

    toggleLayer(key) {
      const layerInfo = this.layers[key];
      if (!layerInfo.layer) return;

      layerInfo.visible = !layerInfo.visible;
      if (layerInfo.visible) {
        map.addLayer(layerInfo.layer);
      } else {
        map.removeLayer(layerInfo.layer);
      }
      this.renderControls();
    },

    moveLayerUp(key) {
      const maxZ = Math.max(...Object.values(this.layers).map((l) => l.zIndex));
      if (this.layers[key].zIndex < maxZ) {
        this.layers[key].zIndex++;
        this.updateLayerOrder();
        this.renderControls();
      }
    },

    moveLayerDown(key) {
      const minZ = Math.min(...Object.values(this.layers).map((l) => l.zIndex));
      if (this.layers[key].zIndex > minZ) {
        this.layers[key].zIndex--;
        this.updateLayerOrder();
        this.renderControls();
      }
    },

    updateLayerOrder() {
      Object.entries(this.layers).forEach(([key, layerInfo]) => {
        if (layerInfo.layer && layerInfo.visible) {
          layerInfo.layer.setZIndex &&
            layerInfo.layer.setZIndex(layerInfo.zIndex * 100);
          if (layerInfo.layer.eachLayer) {
            layerInfo.layer.eachLayer((sublayer) => {
              if (sublayer.setZIndex)
                sublayer.setZIndex(layerInfo.zIndex * 100);
            });
          }
        }
      });
    },

    renderControls() {
      const sortedLayers = Object.entries(this.layers)
        .filter(([key, info]) => info.layer)
        .sort(([, a], [, b]) => b.zIndex - a.zIndex);

      layerControls.innerHTML = sortedLayers
        .map(
          ([key, info]) => `
                <div style='margin-bottom:8px; padding:8px; border:1px solid #ddd; background:white; border-radius:4px;'>
                    <div style='display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;'>
                        <label style='display:flex; align-items:center; cursor:pointer;'>
                            <input type='checkbox' ${info.visible ? "checked" : ""} 
                                   onchange='layerManager.toggleLayer("${key}")' style='margin-right:6px;'>
                            <span style='color:${info.color}; font-weight:bold;'>${info.name}</span>
                        </label>
                        <span style='font-size:10px; color:#666;'>Z:${info.zIndex}</span>
                    </div>
                    <div style='display:flex; gap:4px;'>
                        <button onclick='layerManager.moveLayerUp("${key}")' 
                                style='padding:2px 6px; font-size:10px;' title='Mover arriba'>↑</button>
                        <button onclick='layerManager.moveLayerDown("${key}")' 
                                style='padding:2px 6px; font-size:10px;' title='Mover abajo'>↓</button>
                        <button onclick='layerManager.removeLayer("${key}")' 
                                style='padding:2px 6px; font-size:10px; background:#ffebee;' title='Eliminar'>✕</button>
                    </div>
                </div>
            `,
        )
        .join("");
    },

    // Panel de carga de datasets
    showLayerLoadingPanel() {
      const panelHTML = `
                <div id="layerLoadingPanel" style="
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    z-index: 1001;
                    max-width: 500px;
                    width: 90%;
                ">
                    <h3 style="margin-top: 0;">📊 Cargar Capas de Datos</h3>
                    <div id="datasetList" style="margin: 15px 0;">
                        ${Object.entries(this.datasets)
                          .map(
                            ([filename, dataset]) => `
                            <div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
                                <label style="display: flex; align-items: center; cursor: pointer;">
                                    <input type="checkbox" id="dataset_${filename}" 
                                           ${this.layers[dataset.layer_key]?.layer ? "checked" : ""}
                                           style="margin-right: 10px;">
                                    <div>
                                        <strong>${dataset.name}</strong><br>
                                        <small style="color: #666;">${dataset.description}</small>
                                    </div>
                                </label>
                            </div>
                        `,
                          )
                          .join("")}
                    </div>
                    <div style="text-align: right; margin-top: 20px;">
                        <button id="cancelLayerLoad" style="margin-right: 10px; padding: 8px 16px; background: #ccc; border: none; border-radius: 4px; cursor: pointer;">
                            Cancelar
                        </button>
                        <button id="confirmLayerLoad" style="padding: 8px 16px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">
                            Aplicar Cambios
                        </button>
                    </div>
                </div>
                <div id="layerLoadingOverlay" style="
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.5);
                    z-index: 1000;
                "></div>
            `;

      document.body.insertAdjacentHTML("beforeend", panelHTML);

      // Event handlers para el panel
      document.getElementById("cancelLayerLoad").onclick = () => {
        this.closeLayerLoadingPanel();
      };

      document.getElementById("layerLoadingOverlay").onclick = () => {
        this.closeLayerLoadingPanel();
      };

      document.getElementById("confirmLayerLoad").onclick = async () => {
        await this.applyLayerChanges();
        this.closeLayerLoadingPanel();
      };
    },

    closeLayerLoadingPanel() {
      const panel = document.getElementById("layerLoadingPanel");
      const overlay = document.getElementById("layerLoadingOverlay");
      if (panel) panel.remove();
      if (overlay) overlay.remove();
    },

    async applyLayerChanges() {
      for (const [filename, dataset] of Object.entries(this.datasets)) {
        const checkbox = document.getElementById(`dataset_${filename}`);
        const layerInfo = this.layers[dataset.layer_key];

        if (checkbox.checked && !layerInfo.layer) {
          // Cargar nueva capa
          await this.addLayerFromDataset(filename);
        } else if (!checkbox.checked && layerInfo.layer) {
          // Remover capa existente
          map.removeLayer(layerInfo.layer);
          layerInfo.layer = null;
          layerInfo.visible = false;
        }
      }

      this.updateLayerOrder();
      this.renderControls();
      const statusInfo = document.getElementById("statusInfo");
      if (statusInfo)
        statusInfo.textContent = "Capas actualizadas exitosamente";
    },
  };

  // Hacer el layerManager global para que los botones puedan accederlo
  window.layerManager = layerManager;

  // Función auxiliar para verificar si bounds son válidos
  function isValidBounds(bounds) {
    if (!bounds) return false;
    try {
      const sw = bounds.getSouthWest();
      const ne = bounds.getNorthEast();
      return (
        sw &&
        ne &&
        typeof sw.lat === "number" &&
        typeof sw.lng === "number" &&
        typeof ne.lat === "number" &&
        typeof ne.lng === "number" &&
        sw.lat !== ne.lat &&
        sw.lng !== ne.lng
      );
    } catch (e) {
      return false;
    }
  }

  function renderNodes(nodesGeojson) {
    allNodes = nodesGeojson; // Guardar referencia para el modo tour

    const layer = L.geoJSON(nodesGeojson, {
      pointToLayer: function (feature, latlng) {
        return L.circleMarker(latlng, {
          radius: 8,
          fillColor: "#4CAF50",
          color: "#2E7D32",
          weight: 2,
          opacity: 1,
          fillOpacity: 0.7,
        });
      },
      onEachFeature: function (feature, layer) {
        const id =
          feature.properties &&
          (feature.properties.id || feature.properties.qid || feature.id);
        const label =
          feature.properties &&
          (feature.properties.label || feature.properties.name || id);
        const description =
          feature.properties && feature.properties.description;
        const address = feature.properties && feature.properties.address;
        const wikidata = feature.properties && feature.properties.wikidata;

        // Crear contenido del popup con información detallada y botón
        const isInTour = selectedPlaces.some((place) => place.id === id);
        const buttonText = isInTour
          ? "➖ Quitar de la ruta"
          : "➕ Añadir a la ruta";
        const buttonColor = isInTour ? "#f44336" : "#4CAF50";

        const imgUrl =
          feature.properties &&
          (feature.properties.image ||
            feature.properties.pic ||
            feature.properties.thumbnail);
        let imageHtml = "";
        if (imgUrl) {
          imageHtml = `<div style="width:100%; height:120px; border-radius:4px; overflow:hidden; margin-bottom:8px;">
                        <img src="${imgUrl}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'">
                    </div>`;
        }

        let popupContent = `
                    <div style="min-width: 200px;">
                        ${imageHtml}
                        <h4 style="margin: 0 0 8px 0; color: #333;">${label}</h4>
                        ${description ? `<p style="margin: 4px 0; font-size: 12px; color: #666;">${description}</p>` : ""}
                        ${address ? `<p style="margin: 4px 0; font-size: 11px;"><strong>📍 Dirección:</strong> ${address}</p>` : ""}
                        ${wikidata ? `<p style="margin: 4px 0; font-size: 11px;"><strong>🌐 Wikidata:</strong> ${wikidata}</p>` : ""}
                        <div style="margin-top: 10px; text-align: center;">
                            <button onclick="window.addToTour('${id}', '${label.replace(/'/g, "\\'")}', [${feature.geometry.coordinates[1]}, ${feature.geometry.coordinates[0]}])" 
                                    style="background: ${buttonColor}; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                                ${buttonText}
                            </button>
                        </div>
                    </div>
                `;

        layer.bindPopup(popupContent);

        // Remover el manejo automático de clics - ahora solo se usa el botón del popup
      },
    });

    layerManager.addLayer("nodes", layer);

    // Verificación segura de bounds
    if (layer.getBounds && typeof layer.getBounds === "function") {
      const bounds = layer.getBounds();
      if (isValidBounds(bounds)) {
        map.fitBounds(bounds, { padding: [20, 20] });
      }
    }
  }

  function populateSelects(nodesGeojson) {
    // Función removida pero mantenida por compatibilidad - ya no se usan selectores
    // Los nodos se manejan directamente en el mapa
  }

  async function fetchAndRender(srcId, dstId) {
    // Limpiar información del panel de control antes de cargar nueva ruta
    const existingRouteInfo = layerControls.querySelectorAll(
      'div[style*="margin-top: 10px"]',
    );
    existingRouteInfo.forEach((el) => el.remove());

    layerManager.removeLayer("route");
    info.innerText = "Cargando...";
    const demoUrl =
      apiUrl +
      "/demo/museums?src=" +
      encodeURIComponent(srcId) +
      "&dst=" +
      encodeURIComponent(dstId) +
      "&network=" +
      ALL_NETWORKS;
    try {
      const resp = await fetch(demoUrl);
      if (!resp.ok) {
        const txt = await resp.text();
        info.innerText = `API error ${resp.status}: ${txt}`;
        return;
      }

      const data = await resp.json();
      console.log("Data received:", data);

      const nodes = data.nodes;
      const network = data.network;
      const route = data.route && (data.route.route_geojson || data.route);

      if (nodes) {
        renderNodes(nodes);
        // populateSelects ya no es necesario
      }

      if (network) {
        const networkLayer = L.geoJSON(network, {
          style: { color: "#2196F3", weight: 2, opacity: 0.6 },
        });
        layerManager.addLayer("network", networkLayer);
      }

      if (route) {
        console.log("Processing route:", route);
        const routeLayer = L.layerGroup();

        // Colores para diferentes tipos de transporte
        const transportColors = {
          teleferico: "#E91E63", // Rosa/magenta para teleférico
          bus: "#2196F3", // Azul para buses
          minibus: "#FF9800", // Naranja para minibuses
          taxi: "#9C27B0", // Púrpura para taxis
          walking: "#4CAF50", // Verde para caminata
        };

        // Contador para líneas desconocidas
        let unknownLineCounter = 0;
        const additionalColors = [
          "#795548",
          "#607D8B",
          "#F44336",
          "#3F51B5",
          "#009688",
        ];

        // Recopilar puntos de transferencia
        const transferPoints = [];
        let segmentCount = 0;

        if (route.features && Array.isArray(route.features)) {
          route.features.forEach((feature, index) => {
            const props = feature.properties || {};
            const source = props.source || "unknown";
            const transportType = props.transport_type || "unknown";
            const lineId = props.line_id || null;
            const isTransfer = props.transfer || false;

            let color, weight, opacity, dashArray;

            if (
              source === "walking" ||
              source === "walk_to_network" ||
              source === "walk_from_network"
            ) {
              // Segmentos de caminata
              color = transportColors.walking;
              weight = 4;
              opacity = 0.7;
              dashArray = "10, 5"; // Línea punteada
            } else if (source === "transport") {
              // Líneas de transporte
              color =
                transportColors[transportType] ||
                additionalColors[unknownLineCounter % additionalColors.length];
              if (!transportColors[transportType]) unknownLineCounter++;

              weight = isTransfer ? 6 : 5; // Más gruesa si es transferencia
              opacity = 0.9;
              dashArray = isTransfer ? "15, 5, 5, 5" : null; // Patrón especial para transferencias
            } else {
              // Fallback para otros tipos
              color = "#666666";
              weight = 3;
              opacity = 0.6;
            }

            try {
              const lineLayer = L.geoJSON(feature, {
                style: {
                  color: color,
                  weight: weight,
                  opacity: opacity,
                  dashArray: dashArray,
                },
              });

              // Popup con información detallada
              let popupContent = `<strong>Segmento ${index + 1}</strong><br>`;
              if (lineId) {
                popupContent += `Línea: ${lineId}<br>`;
              }
              if (transportType !== "unknown") {
                popupContent += `Tipo: ${transportType}<br>`;
              }
              if (props.distance_km) {
                popupContent += `Distancia: ${props.distance_km.toFixed(3)} km<br>`;
              }
              if (isTransfer) {
                popupContent += `<span style="color: orange;">⚡ Transferencia</span><br>`;
              }
              popupContent += `Fuente: ${source}`;

              lineLayer.bindPopup(popupContent);
              routeLayer.addLayer(lineLayer);
              segmentCount++;

              // Marcar puntos de transferencia
              if (
                isTransfer &&
                feature.geometry &&
                feature.geometry.coordinates
              ) {
                const coords = feature.geometry.coordinates;
                if (coords.length > 0) {
                  const firstPoint = coords[0];
                  transferPoints.push({
                    latlng: [firstPoint[1], firstPoint[0]], // [lat, lng]
                    lineId: lineId,
                    transportType: transportType,
                  });
                }
              }
            } catch (e) {
              console.error("Error processing route segment:", e, feature);
            }
          });

          // Agregar marcadores para puntos de transferencia
          transferPoints.forEach((point, index) => {
            try {
              const marker = L.circleMarker(point.latlng, {
                radius: 6,
                fillColor: "#FF5722",
                color: "#D84315",
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9,
              });

              marker.bindPopup(`
                                <strong>⚡ Punto de Transferencia</strong><br>
                                Línea: ${point.lineId}<br>
                                Tipo: ${point.transportType}
                            `);

              routeLayer.addLayer(marker);
            } catch (e) {
              console.error("Error adding transfer point:", e, point);
            }
          });
        } else {
          // Fallback para formato de ruta simple
          console.log("Using fallback route rendering");
          try {
            const simpleLayer = L.geoJSON(route, {
              style: { color: "#F44336", weight: 4, opacity: 0.8 },
            });
            routeLayer.addLayer(simpleLayer);
            segmentCount = 1;
          } catch (e) {
            console.error("Error in fallback route rendering:", e);
          }
        }

        console.log(`Route layer created with ${segmentCount} segments`);

        // Agregar la capa de ruta al mapa
        layerManager.addLayer("route", routeLayer, "Ruta calculada");

        // Verificación segura de bounds para la ruta
        if (routeLayer.getLayers().length > 0) {
          try {
            const bounds = routeLayer.getBounds();
            if (isValidBounds(bounds)) {
              map.fitBounds(bounds, { padding: [20, 20] });
            }
          } catch (e) {
            console.warn("Could not fit bounds for route:", e);
          }
        }

        // Mostrar información detallada de la ruta en el panel
        if (data.route && data.route.summary) {
          const summary = data.route.summary;
          const lines = data.route.lines_used || [];

          let routeInfo = `<div style="margin-top: 10px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
                        <h5 style="margin: 0 0 8px 0; color: #333;">📊 Resumen de Ruta</h5>
                        <div style="font-size: 12px; line-height: 1.4;">
                            <div><strong>Total líneas:</strong> ${summary.total_lines}</div>
                            <div><strong>Distancia total:</strong> ${summary.total_distance_km.toFixed(2)} km</div>
                            <div><strong>Caminata:</strong> ${summary.walking_distance_km.toFixed(2)} km</div>
                            <div><strong>Transporte:</strong> ${summary.transport_distance_km.toFixed(2)} km</div>
                        </div>
                    </div>`;

          if (lines.length > 0) {
            routeInfo += `<div style="margin-top: 8px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
                            <h5 style="margin: 0 0 8px 0; color: #333;">🚌 Líneas Utilizadas</h5>
                            <div style="font-size: 11px;">`;

            const transportColors = {
              teleferico: "#E91E63",
              bus: "#2196F3",
              minibus: "#FF9800",
              taxi: "#9C27B0",
            };

            lines.forEach((line, idx) => {
              const color = transportColors[line.transport_type] || "#666";
              routeInfo += `
                                <div style="display: flex; align-items: center; margin-bottom: 4px;">
                                    <div style="width: 12px; height: 3px; background: ${color}; margin-right: 6px; border-radius: 1px;"></div>
                                    <span><strong>${line.name}</strong> (${line.transport_type}) - ${line.total_distance.toFixed(2)} km</span>
                                </div>`;
            });

            routeInfo += `</div></div>`;
          }

          // Leyenda de colores
          routeInfo += `<div style="margin-top: 8px; padding: 10px; background: #fff; border: 1px solid #ddd; border-radius: 4px;">
                        <h5 style="margin: 0 0 8px 0; color: #333;">🎨 Leyenda</h5>
                        <div style="font-size: 11px; line-height: 1.6;">
                            <div style="display: flex; align-items: center; margin-bottom: 2px;">
                                <div style="width: 12px; height: 3px; background: #E91E63; margin-right: 6px;"></div>
                                <span>Teleférico</span>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 2px;">
                                <div style="width: 12px; height: 3px; background: #2196F3; margin-right: 6px;"></div>
                                <span>Bus</span>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 2px;">
                                <div style="width: 12px; height: 3px; background: #FF9800; margin-right: 6px;"></div>
                                <span>Minibus</span>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 2px;">
                                <div style="width: 12px; height: 3px; background: #9C27B0; margin-right: 6px;"></div>
                                <span>Taxi</span>
                            </div>
                            <div style="display: flex; align-items: center; margin-bottom: 2px;">
                                <div style="width: 12px; height: 3px; background: #4CAF50; margin-right: 6px; border: 1px dashed #333;"></div>
                                <span>Caminata</span>
                            </div>
                            <div style="display: flex; align-items: center;">
                                <div style="width: 12px; height: 4px; background: #666; margin-right: 6px; border: 1px dashed #333;"></div>
                                <span>Transferencia</span>
                            </div>
                        </div>
                    </div>`;

          layerControls.innerHTML += routeInfo;
        }

        info.innerText = `Ruta cargada: ${segmentCount} segmentos procesados`;
      } else {
        info.innerText = "No se encontró información de ruta en la respuesta";
      }
    } catch (err) {
      console.error("Error in fetchAndRender:", err);
      info.innerText = "Error: " + String(err);
    }
  }

  // Inicialización optimizada - cargar museos directamente desde caché o endpoint dedicado
  try {
    // Verificar caché primero
    if (cache.isMuseumsCacheValid()) {
      const cachedMuseums = cache.getMuseums();
      if (cachedMuseums && cachedMuseums.features) {
        renderNodes(cachedMuseums);
        info.textContent = `${cachedMuseums.features.length} museos cargados desde caché. Haz clic en cualquier museo para comenzar tu tour.`;
      }
    } else {
      // Cargar museos usando el endpoint dedicado
      info.textContent = "Cargando museos disponibles...";

      const museumsResp = await fetch(`${apiUrl}/museums`);
      if (museumsResp.ok) {
        const museumsData = await museumsResp.json();

        if (museumsData.nodes && museumsData.nodes.features) {
          // Guardar en caché
          cache.setMuseums(museumsData.nodes);

          renderNodes(museumsData.nodes);
          info.textContent = `${museumsData.nodes.features.length} museos cargados. Haz clic en cualquier museo para comenzar tu tour.`;
        } else {
          info.textContent = "Museos cargados. Haz clic para comenzar tu tour.";
        }
      } else {
        // Fallback al endpoint anterior si el nuevo no funciona
        console.warn("Endpoint /museums no disponible, usando fallback");
        const fallbackResp = await fetch(
          `${apiUrl}/demo/museums?src=Q138511481&dst=Q138511511&network=${ALL_NETWORKS}`,
        );
        if (fallbackResp.ok) {
          const fallbackData = await fallbackResp.json();
          if (fallbackData.nodes && fallbackData.nodes.features) {
            cache.setMuseums(fallbackData.nodes);
            renderNodes(fallbackData.nodes);
            info.textContent = `${fallbackData.nodes.features.length} museos cargados (fallback). Haz clic en cualquier museo para comenzar tu tour.`;
          }
        } else {
          info.textContent = "Error al cargar museos. Intenta recargar.";
        }
      }
    }

    // Activar modo tour automáticamente
    toggleTourMode();
  } catch (e) {
    console.error("Error en inicialización:", e);
    info.textContent =
      "Error al inicializar. Usa el botón Recargar para intentar de nuevo.";
  }

  // Event listeners simplificados para modo tour únicamente
  refreshBtn.addEventListener("click", async () => {
    try {
      info.textContent = "Recargando museos...";

      // Forzar recarga desde el servidor (limpiar caché)
      cache.museums = null;
      localStorage.removeItem("museos_cache");

      const refreshResp = await fetch(`${apiUrl}/museums`);
      if (refreshResp.ok) {
        const refreshData = await refreshResp.json();
        if (refreshData.nodes) {
          cache.setMuseums(refreshData.nodes);
          renderNodes(refreshData.nodes);
          info.textContent =
            "Museos recargados desde el servidor. Continúa construyendo tu tour.";
        } else {
          info.textContent = "Error en la respuesta del servidor.";
        }
      } else {
        // Fallback
        const fallbackResp = await fetch(
          `${apiUrl}/demo/museums?src=Q9046895&dst=Q5139104&network=${ALL_NETWORKS}`,
        );
        if (fallbackResp.ok) {
          const fallbackData = await fallbackResp.json();
          if (fallbackData.nodes) {
            cache.setMuseums(fallbackData.nodes);
            renderNodes(fallbackData.nodes);
            info.textContent =
              "Museos recargados (fallback). Continúa construyendo tu tour.";
          }
        }
      }
    } catch (e) {
      console.error("Error al recargar:", e);
      info.textContent = "Error al recargar museos: " + String(e);
    }
  });

  clearTourBtn.addEventListener("click", clearTour);

  // Event listeners para la barra lateral
  openSidebarBtn.addEventListener("click", openSidebar);
  closeSidebarBtn.addEventListener("click", closeSidebar);

  // Event listeners para el sidebar de ruta
  startRouteBtn.addEventListener("click", showRouteDetails);
  closeRouteSidebarBtn.addEventListener("click", closeRouteSidebar);

  // Cerrar sidebar al hacer clic fuera de él
  document.addEventListener("click", (e) => {
    if (
      sidebar.style.left === "0px" &&
      !sidebar.contains(e.target) &&
      !openSidebarBtn.contains(e.target)
    ) {
      closeSidebar();
    }

    // También cerrar sidebar de ruta al hacer clic fuera
    if (
      routeSidebar.style.right === "0px" &&
      !routeSidebar.contains(e.target) &&
      !routeButtonContainer.contains(e.target)
    ) {
      closeRouteSidebar();
    }
  });

  // Event listener para cargar capas
  loadLayersBtn.addEventListener("click", () => {
    layerManager.showLayerLoadingPanel();
  });

  // Event listener para limpiar caché
  clearCacheBtn.addEventListener("click", () => {
    // Limpiar todos los cachés
    cache.museums = null;
    cache.datasets.clear();
    cache.routes.clear();
    cache.entitySearches.clear();
    localStorage.removeItem("museos_cache");

    info.textContent =
      "Caché limpiado completamente. Los datos se recargarán la próxima vez.";

    // Opcional: recargar museos inmediatamente
    setTimeout(() => {
      refreshBtn.click();
    }, 1000);
  });

  // Event listeners para búsqueda por entidad
  searchEntityBtn.addEventListener("click", () => {
    searchPanel.style.display =
      searchPanel.style.display === "none" ? "block" : "none";
    kgSearchPanel.style.display = "none"; // Cerrar panel KG si está abierto
  });

  closeSearchBtn.addEventListener("click", () => {
    searchPanel.style.display = "none";
    clearEntityDetails();
  });

  executeSearchBtn.addEventListener("click", searchByEntity);

  // Permitir búsqueda con Enter en el select
  entitySelect.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      searchByEntity();
    }
  });

  radiusInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      searchByEntity();
    }
  });

  // Event listeners para búsqueda en Knowledge Graph
  searchKgBtn.addEventListener("click", () => {
    kgSearchPanel.style.display =
      kgSearchPanel.style.display === "none" ? "block" : "none";
    searchPanel.style.display = "none"; // Cerrar panel de entidad si está abierto
    enhanceKgPanel.style.display = "none"; // Cerrar otros paneles
    analyzeDataPanel.style.display = "none";
  });

  closeKgSearchBtn.addEventListener("click", () => {
    kgSearchPanel.style.display = "none";
    clearEntityDetails();
  });

  executeKgSearchBtn.addEventListener("click", searchKnowledgeGraph);

  // Permitir búsqueda con Enter en el input de KG
  kgQueryInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      searchKnowledgeGraph();
    }
  });

  // Event listeners para enriquecimiento con KG externo
  enhanceKgBtn.addEventListener("click", () => {
    enhanceKgPanel.style.display =
      enhanceKgPanel.style.display === "none" ? "block" : "none";
    searchPanel.style.display = "none";
    kgSearchPanel.style.display = "none";
    analyzeDataPanel.style.display = "none";
  });

  closeEnhanceBtn.addEventListener("click", () => {
    enhanceKgPanel.style.display = "none";
  });

  searchExternalBtn.addEventListener("click", searchExternalEntities);

  externalQueryInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") {
      searchExternalEntities();
    }
  });

  // Event listeners para análisis de datos
  analyzeDataBtn.addEventListener("click", () => {
    analyzeDataPanel.style.display =
      analyzeDataPanel.style.display === "none" ? "block" : "none";
    searchPanel.style.display = "none";
    kgSearchPanel.style.display = "none";
    enhanceKgPanel.style.display = "none";
  });

  closeAnalyzeBtn.addEventListener("click", () => {
    analyzeDataPanel.style.display = "none";
  });

  analyzeBtn.addEventListener("click", analyzeDataset);

  // Sistema Experto Lógica
  const openSuggestionsBtn = document.getElementById("openSuggestionsBtn");
  const runModalExpertBtn = document.getElementById("runModalExpertBtn");
  const expertBottomPanel = document.getElementById("expertBottomPanel");
  const closeExpertBottomBtn = document.getElementById("closeExpertBottomBtn");
  const expertBottomHeader = document.getElementById("expertBottomHeader");
  const expertBottomTitle = document.getElementById("expertBottomTitle");
  const expertCategorySelection = document.getElementById(
    "expertCategorySelection",
  );
  const expertResultsView = document.getElementById("expertResultsView");

  if (closeExpertBottomBtn) {
    closeExpertBottomBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      expertBottomPanel.style.bottom = "-100%";
      if (openSuggestionsBtn) openSuggestionsBtn.style.display = "flex";
    });
  }

  if (expertBottomHeader) {
    expertBottomHeader.addEventListener("click", () => {
      if (expertBottomPanel.style.bottom === "0px") {
        expertBottomPanel.style.bottom = "-100%";
        if (openSuggestionsBtn) openSuggestionsBtn.style.display = "flex";
      } else {
        expertBottomPanel.style.bottom = "0px";
        if (openSuggestionsBtn) openSuggestionsBtn.style.display = "none";
      }
    });
  }

  if (openSuggestionsBtn) {
    openSuggestionsBtn.addEventListener("click", () => {
      expertCategorySelection.style.display = "flex";
      expertResultsView.style.display = "none";
      expertBottomTitle.textContent = "Sugerencias Inteligentes";
      expertBottomPanel.style.bottom = "0px";
      openSuggestionsBtn.style.display = "none";
    });
  }

  ["modPrefHistory", "modPrefNature", "modPrefFamily", "modPrefTime"].forEach(
    (id) => {
      const chk = document.getElementById(id);
      if (chk) {
        chk.addEventListener("change", (e) => {
          e.target.parentElement.style.background = e.target.checked
            ? "#fff3e0"
            : "#f5f5f5";
          e.target.parentElement.style.borderColor = e.target.checked
            ? "#FF9800"
            : "#eee";
        });
      }
    },
  );

  if (runModalExpertBtn) {
    runModalExpertBtn.addEventListener("click", async () => {
      runModalExpertBtn.innerHTML = "Buscando...";
      runModalExpertBtn.disabled = true;

      const prefs = {
        likes_history: document.getElementById("modPrefHistory").checked,
        likes_nature: document.getElementById("modPrefNature").checked,
        with_family: document.getElementById("modPrefFamily").checked,
        limited_time: document.getElementById("modPrefTime").checked,
      };

      try {
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            prefs.user_lat = pos.coords.latitude;
            prefs.user_lon = pos.coords.longitude;
            await fetchAndDisplayRecommendations(prefs);
          },
          async () => {
            prefs.user_lat = -16.5044756;
            prefs.user_lon = -68.1305956;
            await fetchAndDisplayRecommendations(prefs);
          },
        );
      } catch (error) {
        alert(`❌ Error: ${error.message}`);
      } finally {
        runModalExpertBtn.innerHTML = "Descubrir Lugares ✨";
        runModalExpertBtn.disabled = false;
      }
    });
  }
  async function fetchAndDisplayRecommendations(
    prefs,
    modalResultsDiv,
    modalReasoningDiv,
  ) {
    try {
      const resp = await fetch(`${apiUrl}/expert/recommendations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prefs),
      });

      if (!resp.ok) throw new Error("Error al consultar sistema experto");

      const data = await resp.json();

      if (!data.success) throw new Error(data.error);

      // Mostrar vista de resultados en el panel inferior
      expertCategorySelection.style.display = "none";
      expertResultsView.style.display = "flex";

      // Preparar panel inferior
      const bottomResultsDiv = document.getElementById("expertBottomResults");
      const bottomReasoningDiv = document.getElementById(
        "expertBottomReasoning",
      );
      const bottomTitle = document.getElementById("expertBottomTitle");

      bottomTitle.textContent = `${data.total_recommended} Lugares Recomendados para ti`;

      bottomReasoningDiv.style.display = "block";
      bottomReasoningDiv.innerHTML = data.reasoning
        .map((r) => `• ${r}`)
        .join("<br>");

      bottomResultsDiv.innerHTML = ""; // Limpiar resultados anteriores

      if (data.recommendations && data.recommendations.length > 0) {
        const recommendedIds = data.recommendations.map(
          (p) => p.properties.id || p.properties.qid || p.id,
        );

        // Resaltar en mapa
        if (typeof map !== "undefined") {
          map.eachLayer((layer) => {
            if (
              layer instanceof L.CircleMarker &&
              layer.feature &&
              layer.feature.properties
            ) {
              const id =
                layer.feature.properties.id ||
                layer.feature.properties.qid ||
                layer.feature.id;
              if (recommendedIds.includes(id)) {
                layer.setStyle({
                  color: "#E65100",
                  fillColor: "#FF9800",
                  radius: 12,
                  weight: 3,
                  fillOpacity: 1,
                });
                if (layer.bringToFront) layer.bringToFront();
              } else {
                layer.setStyle({
                  color: "#2E7D32",
                  fillColor: "#4CAF50",
                  radius: 8,
                  weight: 2,
                  fillOpacity: 0.7,
                });
              }
            }
          });
        }

        // Crear las tarjetas dinámicamente y adjuntar el listener del mapa
        data.recommendations.forEach((place, i) => {
          const props = place.properties;
          const coords = place.geometry.coordinates; // [lon, lat]
          const imgUrl = props.image || props.pic || props.thumbnail || ""; // Si existe imagen

          const card = document.createElement("div");
          card.style.cssText =
            "background:#f9f9f9; border-top:4px solid #FF9800; padding:15px; border-radius:8px; display:flex; flex-direction:column; gap:10px; min-width:250px; max-width:280px; box-shadow:0 2px 8px rgba(0,0,0,0.1); flex-shrink:0;";

          let imageHtml = "";
          if (imgUrl) {
            imageHtml = `<div style="width:100%; height:120px; border-radius:4px; overflow:hidden;">
                            <img src="${imgUrl}" style="width:100%; height:100%; object-fit:cover;" onerror="this.style.display='none'">
                        </div>`;
          }

          card.innerHTML = `
                        ${imageHtml}
                        <div style="flex:1;">
                            <div style="font-weight:bold; font-size:15px; color:#333; margin-bottom:4px; white-space:normal;">${i + 1}. ${props.label || "Lugar sin nombre"}</div>
                            <div style="color:#666; font-size:12px; margin-bottom:8px;">🏷️ ${props.typeLabel || "Lugar de interés"}</div>
                            ${props.description ? `<div style="color:#777; font-size:11px; display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; white-space:normal;">${props.description}</div>` : ""}
                        </div>
                        <button class="flyToMapBtn" data-lat="${coords[1]}" data-lon="${coords[0]}" data-id="${props.id || props.qid || place.id}" style="background:#FF9800; color:white; border:none; padding:8px; border-radius:20px; cursor:pointer; font-size:12px; font-weight:bold; box-shadow:0 2px 5px rgba(255,152,0,0.3); transition:background 0.2s; width:100%; margin-top:auto;">📍 Ver Mapa</button>
                    `;

          bottomResultsDiv.appendChild(card);
        });

        // Adjuntar listeners de forma segura
        const flyBtns = bottomResultsDiv.querySelectorAll(".flyToMapBtn");
        flyBtns.forEach((btn) => {
          btn.addEventListener("click", (e) => {
            const lat = parseFloat(e.target.getAttribute("data-lat"));
            const lon = parseFloat(e.target.getAttribute("data-lon"));
            const id = e.target.getAttribute("data-id");

            if (typeof map !== "undefined") {
              map.flyTo([lat, lon], 17, { animate: true, duration: 1.5 });
              // Bajar panel un poco para ver bien el mapa
              expertBottomPanel.style.bottom = "-28vh";

              // Seleccionar y abrir popup en el mapa
              map.eachLayer((layer) => {
                if (
                  layer instanceof L.CircleMarker &&
                  layer.feature &&
                  layer.feature.properties
                ) {
                  const layerId =
                    layer.feature.properties.id ||
                    layer.feature.properties.qid ||
                    layer.feature.id;
                  if (layerId === id) {
                    layer.openPopup();
                  }
                }
              });
            }
          });
        });
      } else {
        bottomResultsDiv.innerHTML =
          '<div style="color:#FF9800; padding:15px; background:#fff3e0; border-radius:8px; width:100%; text-align:center;">No se encontraron recomendaciones exactas cerca de ti.</div>';
      }

      // Subir el bottom panel (si no lo estaba)
      expertBottomPanel.style.bottom = "0px";
    } catch (error) {
      alert(`Error: ${error.message}`);
      runModalExpertBtn.innerHTML = "¡Encontrar Lugares!";
      runModalExpertBtn.disabled = false;
    }
  }
})();
