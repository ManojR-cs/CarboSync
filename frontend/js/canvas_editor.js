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
  let rawSrc = null;
  let annotatedSrc = null;
  let isAnnotatedMode = false;

  function loadImage(src, detectionData, width, height, annotatedUrl = null) {
    imageObj = new Image();
    rawSrc = src;
    annotatedSrc = annotatedUrl;
    isAnnotatedMode = false;
    imgW = width || 0;
    imgH = height || 0;

    imageObj.onload = () => {
      if (!imgW || !imgH) {
        imgW = imageObj.naturalWidth || 1920;
        imgH = imageObj.naturalHeight || 1080;
      }
      fitCanvas();
      drawAll();
    };
    imageObj.src = src;

    if (detectionData) {
      detections = detectionData.map(d => ({ ...d }));
    }
    updateChips();
  }

  function setAnnotatedView(isAnnotated, annotatedUrl = null) {
    if (annotatedUrl) annotatedSrc = annotatedUrl;
    isAnnotatedMode = !!isAnnotated;

    if (isAnnotatedMode && annotatedSrc) {
      if (svgOverlay) svgOverlay.style.display = 'none';
      const img = new Image();
      img.onload = () => {
        if (!ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      };
      img.src = annotatedSrc;
    } else {
      if (svgOverlay) svgOverlay.style.display = 'block';
      drawAll();
    }
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
      rect.setAttribute('fill', isSelected ? `${color}40` : 'rgba(0,0,0,0.001)');
      rect.setAttribute('stroke', color);
      rect.setAttribute('stroke-width', isSelected ? 3.5 : 2);
      if (isSelected) {
        rect.setAttribute('stroke-dasharray', '6,3');
        rect.setAttribute('filter', `drop-shadow(0 0 8px ${color})`);
      }
      rect.setAttribute('rx', 3);
      rect.setAttribute('data-id', det.detection_id);
      rect.style.cursor = 'pointer';
      rect.style.pointerEvents = 'all';
      rect.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        selectDetection(det.detection_id, e);
      });
      svgOverlay.appendChild(rect);

      // Label bg & text
      const labelMap = {
        'Cars': 'Car',
        'Motorcycles and scooters': 'Motorcycle',
        'Buses and campus shuttles': 'Bus',
        'Other fuel-burning vehicles': 'Other',
        'Bicycles': 'Bicycle'
      };
      const shortName = labelMap[det.category] || det.category.split(' ')[0];
      const confPercent = Math.round(det.confidence * 100);
      const labelText = `${shortName} ${confPercent}%`;
      const labelW = Math.max(labelText.length * 7.2 + 14, 72);
      const labelH = 18;
      const lx = sx;
      const ly = (sy - labelH - 2 >= 0) ? (sy - labelH - 2) : (sy + 2);

      const labelBg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      labelBg.setAttribute('x', lx);
      labelBg.setAttribute('y', ly);
      labelBg.setAttribute('width', labelW);
      labelBg.setAttribute('height', labelH);
      labelBg.setAttribute('fill', color);
      labelBg.setAttribute('opacity', '0.92');
      labelBg.setAttribute('rx', 3);
      labelBg.style.cursor = 'pointer';
      labelBg.style.pointerEvents = 'all';
      labelBg.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        selectDetection(det.detection_id, e);
      });
      svgOverlay.appendChild(labelBg);

      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', lx + 6);
      label.setAttribute('y', ly + 13);
      label.setAttribute('fill', '#0f172a');
      label.setAttribute('font-size', '10.5');
      label.setAttribute('font-weight', '700');
      label.setAttribute('font-family', 'Inter, system-ui, sans-serif');
      label.textContent = labelText;
      label.style.cursor = 'pointer';
      label.style.pointerEvents = 'all';
      label.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        selectDetection(det.detection_id, e);
      });
      svgOverlay.appendChild(label);

      // Instant ✕ Delete Badge on top-right of selected box
      if (isSelected) {
        const btnX = sx + sw;
        const btnY = sy;
        const delCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        delCircle.setAttribute('cx', btnX);
        delCircle.setAttribute('cy', btnY);
        delCircle.setAttribute('r', 9);
        delCircle.setAttribute('fill', '#ef4444');
        delCircle.setAttribute('stroke', '#ffffff');
        delCircle.setAttribute('stroke-width', '2');
        delCircle.style.cursor = 'pointer';
        delCircle.style.pointerEvents = 'all';
        delCircle.setAttribute('title', 'Delete this detection');
        delCircle.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          deleteDetectionById(det.detection_id);
        });
        svgOverlay.appendChild(delCircle);

        const delText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        delText.setAttribute('x', btnX);
        delText.setAttribute('y', btnY + 3.5);
        delText.setAttribute('fill', '#ffffff');
        delText.setAttribute('font-size', '11');
        delText.setAttribute('font-weight', '900');
        delText.setAttribute('text-anchor', 'middle');
        delText.textContent = '✕';
        delText.style.cursor = 'pointer';
        delText.style.pointerEvents = 'all';
        delText.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          deleteDetectionById(det.detection_id);
        });
        svgOverlay.appendChild(delText);
      }
    });

    // Drawing preview outside loop
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
      pr.setAttribute('fill', 'rgba(56,189,248,0.15)');
      pr.setAttribute('stroke', '#38bdf8');
      pr.setAttribute('stroke-width', '2');
      pr.setAttribute('stroke-dasharray', '5 3');
      pr.setAttribute('rx', 3);
      svgOverlay.appendChild(pr);
    }
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
      // Position popup near click or top-left of box
      const rect = canvas.getBoundingClientRect();
      const clickX = event ? (event.clientX - rect.left) : (det.box.x_min * scale);
      const clickY = event ? (event.clientY - rect.top)  : (det.box.y_min * scale);
      let px = clickX + 12;
      let py = clickY + 12;

      // Clamp to canvas
      const pw = 220, ph = 160;
      px = Math.max(8, Math.min(px, canvas.width - pw - 8));
      py = Math.max(8, Math.min(py, canvas.height - ph - 8));

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
  function deleteDetectionById(id) {
    // If currently in annotated view, automatically return to interactive raw view
    if (isAnnotatedMode) {
      setAnnotatedView(false);
      document.getElementById('view-raw-btn')?.classList.add('active');
      document.getElementById('view-annotated-btn')?.classList.remove('active');
    }

    const victim = detections.find(d => d.detection_id === id);
    const cat = victim ? victim.category : 'Object';
    detections = detections.filter(d => d.detection_id !== id);
    if (selectedId === id) selectedId = null;
    closePopup();
    updateChips();
    renderDetectionsTable();
    renderSVGBoxes();
    if (typeof showToast === 'function') {
      showToast(`Deleted ${cat} detection`, 'info');
    }
  }

  function deleteSelected() {
    if (isAnnotatedMode) {
      setAnnotatedView(false);
      document.getElementById('view-raw-btn')?.classList.add('active');
      document.getElementById('view-annotated-btn')?.classList.remove('active');
    }

    if (!selectedId) {
      if (detections.length === 0) {
        if (typeof showToast === 'function') showToast('No vehicle detections to delete', 'info');
        return;
      }
      // If user clicks toolbar delete without selecting a box, delete the most recently added or first
      if (typeof showToast === 'function') {
        showToast('Click a bounding box on the image or use the 🗑 button in the table below', 'info');
      }
      return;
    }
    deleteDetectionById(selectedId);
  }

  function reclassifySelected(newCategory) {
    if (!selectedId) return;
    reclassifyDetection(selectedId, newCategory);
  }

  function reclassifyDetection(id, newCategory) {
    const det = detections.find(d => d.detection_id === id);
    if (det) {
      det.category = newCategory;
      updateChips();
      renderDetectionsTable();
      renderSVGBoxes();
      if (popup && popup.classList.contains('visible') && selectedId === id && popupSelect) {
        popupSelect.value = newCategory;
      }
    }
  }

  function highlightDetection(id, isHovered) {
    const rect = svgOverlay?.querySelector(`rect[data-id="${id}"]`);
    if (rect) {
      if (isHovered) {
        rect.setAttribute('stroke-width', '4');
        rect.setAttribute('filter', 'drop-shadow(0 0 10px #38bdf8)');
      } else if (id !== selectedId) {
        rect.setAttribute('stroke-width', '2');
        rect.removeAttribute('filter');
      }
    }
  }

  function setMode(newMode) {
    mode = newMode;
    canvas.style.cursor = newMode === 'draw' ? 'crosshair' : 'default';
  }

  // ── Detections Table Rendering ─────────────────────────────
  function renderDetectionsTable() {
    const tbody = document.getElementById('detections-table-body');
    const countEl = document.getElementById('detections-table-count');
    if (countEl) countEl.textContent = detections.length;
    if (!tbody) return;

    if (detections.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-muted text-center py-md">No vehicle detections active. Click "Draw Box" above to add one manually.</td></tr>`;
      return;
    }

    const catEmoji = {
      'Cars': '🚗',
      'Motorcycles and scooters': '🏍️',
      'Buses and campus shuttles': '🚌',
      'Other fuel-burning vehicles': '🛺',
      'Bicycles': '🚲'
    };

    tbody.innerHTML = detections.map((det, idx) => {
      const color = categoryColor(det.category);
      const emoji = catEmoji[det.category] || '🚗';
      const pct = Math.round(det.confidence * 100);
      const isSel = det.detection_id === selectedId;

      const options = CATEGORIES.map(c => `
        <option value="${c.name}" ${c.name === det.category ? 'selected' : ''}>${c.name}</option>
      `).join('');

      return `
        <tr class="det-table-row ${isSel ? 'table-active' : ''}" 
            data-id="${det.detection_id}"
            style="cursor:pointer; transition:background var(--transition-fast);"
            onmouseenter="CanvasEditor.highlightDetection('${det.detection_id}', true)"
            onmouseleave="CanvasEditor.highlightDetection('${det.detection_id}', false)"
            onclick="CanvasEditor.selectDetection('${det.detection_id}', event)">
          <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-muted);">#${idx + 1}</td>
          <td>
            <span style="display:inline-flex; align-items:center; gap:6px; font-weight:600; color:${color};">
              <span>${emoji}</span> ${det.category}
            </span>
          </td>
          <td>
            <span style="font-family:var(--font-mono); font-size:0.8rem; background:rgba(255,255,255,0.06); padding:2px 8px; border-radius:4px; font-weight:700; color:var(--text-primary);">
              ${pct}%
            </span>
          </td>
          <td onclick="event.stopPropagation()">
            <select style="width:100%; font-size:0.75rem; padding:3px 6px; background:var(--bg-card); border:1px solid var(--card-border); color:var(--text-primary); border-radius:var(--radius-sm);"
                    onchange="CanvasEditor.reclassifyDetection('${det.detection_id}', this.value)">
              ${options}
            </select>
          </td>
          <td style="text-align:center;" onclick="event.stopPropagation()">
            <button class="btn btn-danger btn-sm" 
                    style="padding:3px 10px; font-size:0.75rem;"
                    title="Delete vehicle detection"
                    onclick="CanvasEditor.deleteDetectionById('${det.detection_id}')">
              🗑 Delete
            </button>
          </td>
        </tr>
      `;
    }).join('');
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

    // Update table
    renderDetectionsTable();

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
  return { 
    init, 
    loadImage, 
    setAnnotatedView, 
    deleteSelected, 
    deleteDetectionById, 
    reclassifySelected, 
    reclassifyDetection, 
    highlightDetection, 
    selectDetection, 
    setMode, 
    getVerifiedCounts, 
    getDetections, 
    updateChips, 
    renderSVGBoxes, 
    renderDetectionsTable 
  };
})();
