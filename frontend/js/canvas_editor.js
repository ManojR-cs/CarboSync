/**
 * TraceTwin — canvas_editor.js
 * Interactive HTML5 Canvas bounding-box drawing, selection,
 * deletion, reclassification, and manual drawing.
 */

const CanvasEditor = (() => {

  // ── State ──────────────────────────────────────────────────
  let canvas, ctx, svgOverlay;
  let imageObj    = null;
  let detections  = [];   // [{detection_id, category, confidence, box:{x_min,y_min,x_max,y_max}}]
  let scale       = 1;    // canvas scale relative to original image
  let offsetX     = 0;
  let offsetY     = 0;
  let imgW = 0, imgH = 0; // original image dimensions

  // Interaction state
  let selectedId  = null;
  let isDrawing   = false;
  let drawStart   = null;
  let drawRect    = null;
  let mode        = 'select'; // 'select' | 'draw'

  // DOM refs
  let popup, popupSelect, popupConf;
  let countChips = {};

  // ── Category Config ────────────────────────────────────────
  const CATEGORIES = [
    { name: 'Cars',                       color: '#38bdf8', chipClass: 'chip-car'  },
    { name: 'Motorcycles and scooters',   color: '#f97316', chipClass: 'chip-moto' },
    { name: 'Buses and campus shuttles',  color: '#22c55e', chipClass: 'chip-bus'  },
    { name: 'Other fuel-burning vehicles',color: '#a855f7', chipClass: 'chip-other'},
    { name: 'Bicycles',                   color: '#06b6d4', chipClass: 'chip-bicycle'}
  ];

  function categoryColor(cat) {
    const found = CATEGORIES.find(c => c.name === cat);
    return found ? found.color : '#94a3b8';
  }

  // ── Initialise ─────────────────────────────────────────────
  function init(canvasEl, svgEl) {
    canvas    = canvasEl;
    ctx       = canvas.getContext('2d');
    svgOverlay = svgEl;
    popup     = document.getElementById('canvas-popup');
    popupSelect = document.getElementById('popup-class-select');
    popupConf = document.getElementById('popup-confidence');

    // Populate select options
    if (popupSelect) {
      popupSelect.innerHTML = CATEGORIES
        .map(c => `<option value="${c.name}">${c.name}</option>`)
        .join('');
    }

    // Events
    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mousemove', onMouseMove);
    canvas.addEventListener('mouseup',   onMouseUp);
    canvas.addEventListener('click',     onCanvasClick);
    document.addEventListener('keydown', onKeyDown);

    updateChips();
  }

  // ── Load Image ─────────────────────────────────────────────
  function loadImage(src, detectionData, width, height) {
    imageObj = new Image();
    imgW = width;
    imgH = height;

    imageObj.onload = () => {
      fitCanvas();
      drawAll();
    };
    imageObj.src = src;

    if (detectionData) {
      detections = detectionData.map(d => ({ ...d }));
    }
    updateChips();
  }

  function fitCanvas() {
    const maxW = canvas.parentElement.clientWidth;
    const maxH = Math.min(window.innerHeight * 0.6, 600);

    scale   = Math.min(maxW / imgW, maxH / imgH, 1);
    canvas.width  = imgW * scale;
    canvas.height = imgH * scale;
    offsetX = 0;
    offsetY = 0;

    // Sync SVG size
    if (svgOverlay) {
      svgOverlay.setAttribute('width',  canvas.width);
      svgOverlay.setAttribute('height', canvas.height);
      svgOverlay.setAttribute('viewBox', `0 0 ${canvas.width} ${canvas.height}`);
    }
  }

  // ── Draw ───────────────────────────────────────────────────
  function drawAll() {
    if (!ctx || !imageObj) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imageObj, 0, 0, canvas.width, canvas.height);

    if (svgOverlay) {
      renderSVGBoxes();
    } else {
      // fallback: draw on canvas
      drawBoxesOnCanvas();
    }
  }

  function renderSVGBoxes() {
    svgOverlay.innerHTML = '';
    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    svgOverlay.appendChild(defs);

    detections.forEach(det => {
      const { x_min, y_min, x_max, y_max } = det.box;
      const sx = x_min * scale;
      const sy = y_min * scale;
      const sw = (x_max - x_min) * scale;
      const sh = (y_max - y_min) * scale;
      const color = categoryColor(det.category);
      const isSelected = det.detection_id === selectedId;

      // Rect
      const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', sx);
      rect.setAttribute('y', sy);
      rect.setAttribute('width', sw);
      rect.setAttribute('height', sh);
      rect.setAttribute('fill', 'transparent');
      rect.setAttribute('stroke', color);
      rect.setAttribute('stroke-width', isSelected ? 3 : 2);
      rect.setAttribute('rx', 3);
      rect.setAttribute('data-id', det.detection_id);
      rect.style.cursor = 'pointer';
      if (isSelected) rect.setAttribute('filter', `drop-shadow(0 0 6px ${color})`);
      rect.addEventListener('click', (e) => { e.stopPropagation(); selectDetection(det.detection_id, e); });
      svgOverlay.appendChild(rect);

      // Label bg
      const labelText = det.category.split(' ')[0];
      const labelW = Math.max(labelText.length * 6.5 + 8, 60);
      const labelH = 18;
      const lx = sx;
      const ly = sy - labelH - 2;

      if (ly >= 0) {
        const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        labelBg.setAttribute('x', lx);
        labelBg.setAttribute('y', ly);
        labelBg.setAttribute('width', labelW);
        labelBg.setAttribute('height', labelH);
        labelBg.setAttribute('fill', color);
        labelBg.setAttribute('opacity', '0.9');
        labelBg.setAttribute('rx', 3);
        svgOverlay.appendChild(labelBg);

        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('x', lx + 4);
        label.setAttribute('y', ly + 12);
        label.setAttribute('fill', '#0f172a');
        label.setAttribute('font-size', '10');
        label.setAttribute('font-weight', '700');
        label.setAttribute('font-family', 'Inter, sans-serif');
        label.textContent = `${labelText} ${Math.round(det.confidence * 100)}%`;
        svgOverlay.appendChild(label);
      }

      // Drawing preview
      if (drawRect && isDrawing) {
        const pr = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const dx = Math.min(drawStart.x, drawRect.x);
        const dy = Math.min(drawStart.y, drawRect.y);
        const dw = Math.abs(drawRect.x - drawStart.x);
        const dh = Math.abs(drawRect.y - drawStart.y);
        pr.setAttribute('x', dx);
        pr.setAttribute('y', dy);
        pr.setAttribute('width', dw);
        pr.setAttribute('height', dh);
        pr.setAttribute('fill', 'rgba(56,189,248,0.1)');
        pr.setAttribute('stroke', '#38bdf8');
        pr.setAttribute('stroke-width', '2');
        pr.setAttribute('stroke-dasharray', '5 3');
        pr.setAttribute('rx', 3);
        svgOverlay.appendChild(pr);
      }
    });
  }

  function drawBoxesOnCanvas() {
    detections.forEach(det => {
      const { x_min, y_min, x_max, y_max } = det.box;
      const color = categoryColor(det.category);
      const isSelected = det.detection_id === selectedId;

      ctx.strokeStyle = color;
      ctx.lineWidth   = isSelected ? 3 : 2;
      ctx.strokeRect(x_min * scale, y_min * scale, (x_max - x_min) * scale, (y_max - y_min) * scale);

      // Label
      ctx.fillStyle = color;
      ctx.font      = 'bold 11px Inter';
      const label   = det.category.split(' ')[0];
      ctx.fillText(label, x_min * scale + 4, y_min * scale + 14);
    });
  }

  // ── Mouse Events ───────────────────────────────────────────
  function canvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function onMouseDown(e) {
    if (mode !== 'draw') return;
    isDrawing = true;
    drawStart = canvasCoords(e);
    drawRect  = { ...drawStart };
  }

  function onMouseMove(e) {
    if (!isDrawing || mode !== 'draw') return;
    drawRect = canvasCoords(e);
    renderSVGBoxes();
  }

  function onMouseUp(e) {
    if (!isDrawing || mode !== 'draw') return;
    isDrawing = false;
    const end = canvasCoords(e);

    const w = Math.abs(end.x - drawStart.x);
    const h = Math.abs(end.y - drawStart.y);
    if (w < 10 || h < 10) { drawRect = null; return; }

    // Normalize to original image coords
    const newDet = {
      detection_id: 'det_manual_' + Date.now(),
      category: 'Cars',
      confidence: 1.0,
      is_manually_added: true,
      box: {
        x_min: Math.min(drawStart.x, end.x) / scale,
        y_min: Math.min(drawStart.y, end.y) / scale,
        x_max: Math.max(drawStart.x, end.x) / scale,
        y_max: Math.max(drawStart.y, end.y) / scale
      }
    };

    detections.push(newDet);
    drawRect = null;
    selectDetection(newDet.detection_id, e);
    updateChips();
    renderSVGBoxes();
  }

  function onCanvasClick(e) {
    if (mode === 'draw') return;
    closePopup();
    selectedId = null;
    renderSVGBoxes();
  }

  function onKeyDown(e) {
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (selectedId && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'SELECT') {
        deleteSelected();
      }
    }
    if (e.key === 'Escape') {
      closePopup();
      selectedId = null;
      renderSVGBoxes();
    }
  }

  // ── Selection & Popup ──────────────────────────────────────
  function selectDetection(id, event) {
    selectedId = id;
    const det = detections.find(d => d.detection_id === id);
    if (!det) return;

    if (popup) {
      // Position popup near click but within viewport
      const rect = canvas.getBoundingClientRect();
      let px = (event.clientX - rect.left) + 12;
      let py = (event.clientY - rect.top)  + 12;

      // Clamp to canvas
      const pw = 210, ph = 150;
      if (px + pw > canvas.width)  px = canvas.width  - pw - 12;
      if (py + ph > canvas.height) py = canvas.height - ph - 12;

      popup.style.left = px + 'px';
      popup.style.top  = py + 'px';
      popup.classList.add('visible');

      if (popupConf) popupConf.textContent = `${det.category} · ${Math.round(det.confidence * 100)}% confidence`;
      if (popupSelect) popupSelect.value = det.category;
    }

    renderSVGBoxes();
  }

  function closePopup() {
    if (popup) popup.classList.remove('visible');
  }

  // ── Actions ────────────────────────────────────────────────
  function deleteSelected() {
    if (!selectedId) return;
    detections = detections.filter(d => d.detection_id !== selectedId);
    selectedId = null;
    closePopup();
    updateChips();
    renderSVGBoxes();
    showToast('Detection removed', 'info');
  }

  function reclassifySelected(newCategory) {
    const det = detections.find(d => d.detection_id === selectedId);
    if (det) {
      det.category = newCategory;
      updateChips();
      renderSVGBoxes();
    }
  }

  function setMode(newMode) {
    mode = newMode;
    canvas.style.cursor = newMode === 'draw' ? 'crosshair' : 'default';
  }

  // ── Summary Chips ──────────────────────────────────────────
  function updateChips() {
    const counts = {
      'Bicycles': 0,
      'Cars': 0,
      'Motorcycles and scooters': 0,
      'Buses and campus shuttles': 0,
      'Other fuel-burning vehicles': 0
    };

    detections.forEach(d => {
      if (counts.hasOwnProperty(d.category)) counts[d.category]++;
    });

    const total = Object.values(counts).reduce((a, b) => a + b, 0);

    const chipMap = {
      'Bicycles':                   'chip-count-bicycle',
      'Cars':                       'chip-count-car',
      'Motorcycles and scooters':   'chip-count-moto',
      'Buses and campus shuttles':  'chip-count-bus',
      'Other fuel-burning vehicles':'chip-count-other'
    };

    Object.entries(chipMap).forEach(([cat, elId]) => {
      const el = document.getElementById(elId);
      if (el) el.textContent = counts[cat];
    });

    const totalEl = document.getElementById('chip-count-total');
    if (totalEl) totalEl.textContent = total;

    // Update app state
    if (window.AppState) AppState.cvCounts = counts;
  }

  // ── Get Verified Counts ────────────────────────────────────
  function getVerifiedCounts() {
    const counts = {
      'Cars': 0, 'Motorcycles and scooters': 0,
      'Buses and campus shuttles': 0, 'Other fuel-burning vehicles': 0
    };
    detections.forEach(d => {
      if (counts.hasOwnProperty(d.category)) counts[d.category]++;
    });
    return counts;
  }

  function getDetections() { return [...detections]; }

  // ── Public API ─────────────────────────────────────────────
  return { init, loadImage, deleteSelected, reclassifySelected, setMode, getVerifiedCounts, getDetections, updateChips, renderSVGBoxes };
})();
