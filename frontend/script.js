(function () {
  function pad(n) { return String(n).padStart(2, '0'); }

  function updateSimulationClocks() {
    const now = new Date();
    const value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    document.querySelectorAll('#simulation-clock, [data-simulation-clock]').forEach((el) => {
      el.textContent = value;
    });
  }

  function normalizePath(path) {
    const last = path.split('/').pop() || 'index.html';
    return last === '' ? 'index.html' : last;
  }

  function highlightActiveNav() {
    const current = normalizePath(window.location.pathname);
    document.querySelectorAll('nav a[href]').forEach((link) => {
      const href = normalizePath(link.getAttribute('href') || '');
      if (href === current || (current === '' && href === 'index.html')) {
        link.setAttribute('aria-current', 'page');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    updateSimulationClocks();
    setInterval(updateSimulationClocks, 1000);
    highlightActiveNav();
  });
})();

(function () {
  const OPT_WS_URL = 'ws://localhost:8000/opt';
  const RECONNECT_DELAY_MS = 3000;

  let optSocket;
  let optReconnectTimer;
  let hasLiveRecommendations = false;
  const recommendationJunctionNames = new Map();
  const recommendations = new Map();

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('recommendations-list')) {
      connectOptimisationSocket();
    }
  });

  function connectOptimisationSocket() {
    clearTimeout(optReconnectTimer);
    setOptimisationStatus('CONNECTING');

    optSocket = new WebSocket(OPT_WS_URL);

    optSocket.addEventListener('open', () => {
      setOptimisationStatus('LIVE REVIEW');
    });

    optSocket.addEventListener('message', (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'recommendation' && message.data) {
          addRecommendation(message.data);
        }
      } catch (error) {
        console.error('Invalid optimisation message:', error);
      }
    });

    optSocket.addEventListener('close', () => {
      setOptimisationStatus('DISCONNECTED');
      optReconnectTimer = setTimeout(connectOptimisationSocket, RECONNECT_DELAY_MS);
    });

    optSocket.addEventListener('error', () => {
      setOptimisationStatus('DISCONNECTED');
      optSocket.close();
    });
  }

  function addRecommendation(recommendation) {
    if (!recommendation.junction_id) return;

    if (!hasLiveRecommendations) {
      const list = document.getElementById('recommendations-list');
      if (list) list.innerHTML = '';
      hasLiveRecommendations = true;
    }

    recommendations.set(String(recommendation.junction_id), recommendation);
    renderRecommendations();
  }

  function renderRecommendations() {
    const list = document.getElementById('recommendations-list');
    if (!list) return;

    const items = Array.from(recommendations.values()).slice(-3).reverse();
    list.innerHTML = items.map(createRecommendationCard).join('');

    list.querySelectorAll('[data-decision]').forEach((button) => {
      button.addEventListener('click', () => {
        sendDecision(button.dataset.decision, button.dataset.junctionId);
      });
    });
  }

  function createRecommendationCard(recommendation) {
    const rawJunctionId = String(recommendation.junction_id);
    const junctionId = escapeHtml(rawJunctionId);
    const displayJunctionId = getRecommendationJunctionName(rawJunctionId);
    const title = `${displayJunctionId}: ${formatPattern(recommendation.pattern_type)}`;
    const confidence = Math.round((Number(recommendation.severity_score) || 0) * 100);
    const improvement = Number(recommendation.improvement_pct) || 0;
    const explanation = escapeHtml(formatRecommendationText(
      recommendation.explanation || 'Review the proposed signal timing change.',
      rawJunctionId,
      displayJunctionId
    ));

    return `
      <article class="bg-on-primary/10 p-md rounded-lg border border-on-primary/20" data-junction-id="${junctionId}">
        <div class="flex items-start justify-between gap-md mb-sm">
          <div>
            <h3 class="text-title-md font-bold">${escapeHtml(title)}</h3>
            <p class="text-body-sm opacity-90 mt-1">${explanation}</p>
          </div>
          <span class="text-label-sm flex items-center gap-xs opacity-90 whitespace-nowrap">
            <span class="w-1.5 h-1.5 rounded-full bg-on-primary"></span>
            Waiting for review
          </span>
        </div>
        <div class="grid grid-cols-2 gap-md mb-md">
          <div class="flex flex-col">
            <span class="text-label-sm uppercase opacity-70 font-bold">Confidence</span>
            <span class="text-title-lg font-data-mono">${confidence}%</span>
          </div>
          <div class="flex flex-col">
            <span class="text-label-sm uppercase opacity-70 font-bold">Est. Efficiency Gain</span>
            <span class="text-title-lg font-data-mono text-green-300">+${improvement.toFixed(1)}%</span>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-sm">
          <button data-decision="accept" data-junction-id="${junctionId}" class="bg-green-600 text-white flex items-center justify-center gap-sm py-2 rounded-lg text-title-md font-bold hover:bg-green-700 active:scale-[0.98] transition-all shadow-sm">
            <span class="material-symbols-outlined text-[20px]">check_circle</span> Accept
          </button>
          <button data-decision="reject" data-junction-id="${junctionId}" class="bg-white text-error border-2 border-error flex items-center justify-center gap-sm py-2 rounded-lg text-title-md font-bold hover:bg-error/5 active:scale-[0.98] transition-all">
            <span class="material-symbols-outlined text-[20px]">cancel</span> Decline
          </button>
        </div>
      </article>
    `;
  }

  function sendDecision(action, junctionId) {
    if (!optSocket || optSocket.readyState !== WebSocket.OPEN) {
      setOptimisationStatus('DISCONNECTED');
      return;
    }

    optSocket.send(JSON.stringify({
      action,
      junction_id: junctionId
    }));

    markRecommendationReviewed(junctionId, action);
  }

  function markRecommendationReviewed(junctionId, action) {
    const card = Array.from(document.querySelectorAll('[data-junction-id]'))
      .find((item) => item.dataset.junctionId === junctionId);
    if (!card) return;

    const status = card.querySelector('span.whitespace-nowrap');
    if (status) {
      status.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-on-primary"></span>${action === 'accept' ? 'Accepted' : 'Declined'}`;
    }

    card.querySelectorAll('button').forEach((button) => {
      button.disabled = true;
      button.classList.add('opacity-60', 'cursor-not-allowed');
    });
  }

  function setOptimisationStatus(status) {
    const el = document.getElementById('opt-connection-text');
    if (el) el.textContent = status;
  }

  function formatPattern(pattern) {
    return String(pattern || 'Signal Timing Suggestion')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function getRecommendationJunctionName(rawJunctionId) {
    if (!recommendationJunctionNames.has(rawJunctionId)) {
      const nextNumber = recommendationJunctionNames.size + 1;
      recommendationJunctionNames.set(rawJunctionId, `Junction ${String(nextNumber).padStart(2, '0')}`);
    }
    return recommendationJunctionNames.get(rawJunctionId);
  }

  function formatRecommendationText(text, rawJunctionId, displayJunctionId) {
    return String(text).split(rawJunctionId).join(displayJunctionId);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

})();

(function () {
  const WS_URL = 'ws://localhost:8000/traffic';
  const RECONNECT_DELAY_MS = 3000;

  let map;
  let socket;
  let reconnectTimer;
  let selectedJunctionId = null;
  let junctionOrder = [];
  const junctionMarkers = new Map();
  const junctionData = new Map();
  const vehicleMarkers = new Map();

  document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('map')) {
      initialiseDashboard();
    }
  });

  function initialiseDashboard() {
    if (typeof L === 'undefined') {
      console.error('Leaflet is not loaded. Please check the Leaflet script tag in index.html.');
      return;
    }

    map = L.map('map', {
      zoomControl: false
    }).setView([53.3498, -6.2603], 14);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    connectWebSocket();
  }

  function connectWebSocket() {
    clearTimeout(reconnectTimer);
    setConnectionStatus('CONNECTING');

    socket = new WebSocket(WS_URL);

    socket.addEventListener('open', () => {
      setConnectionStatus('CONNECTED');
    });

    socket.addEventListener('message', (event) => {
      try {
        const message = JSON.parse(event.data);
        handleSocketMessage(message);
      } catch (error) {
        console.error('Invalid WebSocket message:', error);
      }
    });

    socket.addEventListener('close', () => {
      setConnectionStatus('DISCONNECTED');
      reconnectTimer = setTimeout(connectWebSocket, RECONNECT_DELAY_MS);
    });

    socket.addEventListener('error', () => {
      setConnectionStatus('DISCONNECTED');
      socket.close();
    });
  }

  function handleSocketMessage(message) {
    if (message.type === 'junction_state') {
      updateJunctions(message.junctions || []);
    }

    if (message.type === 'vehicle_positions') {
      updateVehicles(message.vehicles || [], message.vehicle_count);
    }
  }

  function setConnectionStatus(status) {
    const dot = document.getElementById('connection-dot');
    const text = document.getElementById('connection-text');

    if (text) text.textContent = status;
    if (!dot) return;

    dot.classList.remove('bg-green-500', 'bg-amber-500', 'bg-red-500');
    if (status === 'CONNECTED') dot.classList.add('bg-green-500');
    else if (status === 'CONNECTING') dot.classList.add('bg-amber-500');
    else dot.classList.add('bg-red-500');
  }

  function updateJunctions(junctions) {
    junctions.forEach((junction) => {
      if (!junction || junction.id == null || junction.lat == null || junction.lng == null) return;

      const rawId = String(junction.id);
      const metrics = getJunctionMetrics(junction);
      const severity = getTrafficSeverity(junction, metrics.totalQueue);
      const displayName = getJunctionDisplayName(rawId);
      const latLng = [Number(junction.lat), Number(junction.lng)];

      junctionData.set(rawId, {
        ...junction,
        rawId,
        displayName,
        metrics,
        severity
      });

      if (junctionMarkers.has(rawId)) {
        const marker = junctionMarkers.get(rawId);
        marker.setLatLng(latLng);
        marker.setIcon(createJunctionIcon(severity));
        marker.setPopupContent(createJunctionPopup(displayName, rawId, metrics, severity));
      } else {
        const marker = L.marker(latLng, {
          icon: createJunctionIcon(severity)
        }).addTo(map);

        marker.bindPopup(createJunctionPopup(displayName, rawId, metrics, severity));
        marker.on('click', () => {
          selectedJunctionId = rawId;
          updateJunctionPanel(rawId);
        });
        junctionMarkers.set(rawId, marker);
      }
    });

    if (!selectedJunctionId && junctions.length > 0) {
      selectedJunctionId = String(junctions[0].id);
      updateJunctionPanel(selectedJunctionId);
      fitMapToJunctions();
    } else if (selectedJunctionId && junctionData.has(selectedJunctionId)) {
      updateJunctionPanel(selectedJunctionId);
    }
  }

  function updateVehicles(vehicles, vehicleCountFromServer) {
    const currentVehicleIds = new Set();

    vehicles.forEach((vehicle) => {
      if (!vehicle || vehicle.id == null || vehicle.lat == null || vehicle.lng == null) return;

      const vehicleId = String(vehicle.id);
      const latLng = [Number(vehicle.lat), Number(vehicle.lng)];
      currentVehicleIds.add(vehicleId);

      if (vehicleMarkers.has(vehicleId)) {
        vehicleMarkers.get(vehicleId).setLatLng(latLng);
      } else {
        const marker = L.marker(latLng, {
          icon: createVehicleIcon()
        }).addTo(map);
        vehicleMarkers.set(vehicleId, marker);
      }

      vehicleMarkers.get(vehicleId).bindPopup(createVehiclePopup(vehicle));
    });

    vehicleMarkers.forEach((marker, vehicleId) => {
      if (!currentVehicleIds.has(vehicleId)) {
        map.removeLayer(marker);
        vehicleMarkers.delete(vehicleId);
      }
    });

    const vehicleCount = Number.isFinite(Number(vehicleCountFromServer))
      ? Number(vehicleCountFromServer)
      : vehicles.length;
    updateText('map-vehicle-count', vehicleCount);
  }

  function getJunctionMetrics(junction) {
    const approaches = Array.isArray(junction.approaches) ? junction.approaches : [];
    let totalQueue = 0;
    let totalVehicles = 0;
    let weightedWaitTotal = 0;

    approaches.forEach((lane) => {
      const queue = Number(lane.queue_length) || 0;
      const vehicles = Number(lane.vehicle_count) || 0;
      const wait = Number(lane.waiting_time_avg) || 0;

      totalQueue += queue;
      totalVehicles += vehicles;
      weightedWaitTotal += wait * vehicles;
    });

    const averageWait = totalVehicles > 0 ? weightedWaitTotal / totalVehicles : 0;

    return {
      totalQueue,
      totalVehicles,
      averageWait,
      phase: Number.isFinite(Number(junction.current_phase)) ? Number(junction.current_phase) : null
    };
  }

  function getTrafficSeverity(junction, totalQueue) {
    const backendSeverity = String(junction.congestion_severity || '').toLowerCase();

    if (backendSeverity.includes('heavy') || backendSeverity.includes('critical') || backendSeverity === 'red') {
      return { label: 'HEAVY QUEUE', popupLabel: 'Heavy Queue', color: '#ef4444', bgClass: 'bg-error-container', textClass: 'text-error', icon: 'warning' };
    }

    if (backendSeverity.includes('delay') || backendSeverity.includes('medium') || backendSeverity === 'orange') {
      return { label: 'SOME DELAY', popupLabel: 'Some Delay', color: '#f59e0b', bgClass: 'bg-amber-100', textClass: 'text-amber-700', icon: 'traffic' };
    }

    if (totalQueue >= 15) {
      return { label: 'HEAVY QUEUE', popupLabel: 'Heavy Queue', color: '#ef4444', bgClass: 'bg-error-container', textClass: 'text-error', icon: 'warning' };
    }

    if (totalQueue >= 5) {
      return { label: 'SOME DELAY', popupLabel: 'Some Delay', color: '#f59e0b', bgClass: 'bg-amber-100', textClass: 'text-amber-700', icon: 'traffic' };
    }

    return { label: 'NORMAL', popupLabel: 'Normal Traffic', color: '#22c55e', bgClass: 'bg-green-100', textClass: 'text-green-700', icon: 'traffic' };
  }

  function getJunctionDisplayName(rawId) {
    if (!junctionOrder.includes(rawId)) {
      junctionOrder.push(rawId);
    }

    const number = junctionOrder.indexOf(rawId) + 1;
    return `Junction ${String(number).padStart(2, '0')}`;
  }

  function updateJunctionPanel(rawId) {
    const data = junctionData.get(rawId);
    if (!data) return;

    updateText('junction-id', `Junction ID: ${data.displayName}`);
    updateText('junction-raw-id', `Raw ID: ${data.rawId}`);
    updateText('queue-value', Math.round(data.metrics.totalQueue));
    updateText('wait-value', Math.round(data.metrics.averageWait));
    updateText('phase-value', data.metrics.phase === null ? 'Phase --' : `Phase ${data.metrics.phase}`);
    updateText('vehicle-value', Math.round(data.metrics.totalVehicles));
    updateTrafficStatus(data.severity);
  }

  function updateTrafficStatus(severity) {
    const status = document.getElementById('traffic-status');
    if (!status) return;

    status.classList.remove('bg-green-100', 'text-green-700', 'bg-amber-100', 'text-amber-700', 'bg-error-container', 'text-error');
    status.classList.add(severity.bgClass, severity.textClass);
    status.innerHTML = `<span class="material-symbols-outlined text-[16px]">${severity.icon}</span> ${severity.label}`;
  }

  function updateText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function fitMapToJunctions() {
    const points = Array.from(junctionData.values()).map((junction) => [junction.lat, junction.lng]);
    if (points.length === 0) return;
    map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
  }

  function createJunctionIcon(severity) {
    return L.divIcon({
      className: '',
      html: `<div class="live-junction-marker" style="border-color: ${severity.color};"><div style="background: ${severity.color};"></div></div>`,
      iconSize: [22, 22],
      iconAnchor: [11, 11],
      popupAnchor: [0, -10]
    });
  }

  function createVehicleIcon() {
    return L.divIcon({
      className: '',
      html: '<div class="live-vehicle-marker"></div>',
      iconSize: [12, 12],
      iconAnchor: [6, 6],
      popupAnchor: [0, -6]
    });
  }

  function createJunctionPopup(displayName, rawId, metrics, severity) {
    return `
      <strong>${displayName}</strong><br>
      Raw ID: ${rawId}<br>
      Status: ${severity.popupLabel}<br>
      Queue: ${Math.round(metrics.totalQueue)}<br>
      Avg Wait: ${Math.round(metrics.averageWait)}s<br>
      Vehicles: ${Math.round(metrics.totalVehicles)}
    `;
  }

  function createVehiclePopup(vehicle) {
    const speed = Number.isFinite(Number(vehicle.speed)) ? `${Number(vehicle.speed).toFixed(1)} m/s` : '--';
    return `
      <strong>Vehicle ${vehicle.id}</strong><br>
      Speed: ${speed}<br>
      Road ID: ${vehicle.road_id || '--'}
    `;
  }
})();
