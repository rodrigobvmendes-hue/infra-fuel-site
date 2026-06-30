// ── State ──────────────────────────────────────────────────────
const state = {
  search: "",
  types: [],
  regions: [],
  states: [],
  statuses: [],
  hideRailDuplicates: true,
};
const MULTI_ALL_VALUE = "__ALL__";

const REGION_CODE_BY_STATE = {
  AC: "NO", AM: "NO", AP: "NO", PA: "NO", RO: "NO", RR: "NO", TO: "NO",
  AL: "NNE", BA: "NNE", CE: "NNE", MA: "NNE", PB: "NNE", PE: "NNE", PI: "NNE", RN: "NNE", SE: "NNE",
  DF: "CO", GO: "CO", MT: "CO", MS: "CO",
  PR: "SU", SC: "SU", RS: "SU",
  ES: "SSE", MG: "SSE", RJ: "SSE", SP: "SSE",
};

function getRegionCodeFromProject(project) {
  const uf = String(project.state || "").toUpperCase().trim();
  if (REGION_CODE_BY_STATE[uf]) return REGION_CODE_BY_STATE[uf];

  const regionName = String(project.region || "").toLowerCase();
  if (regionName.includes("centro")) return "CO";
  if (regionName.includes("norte")) return "NO";
  if (regionName.includes("sul")) return "SU";
  if (regionName.includes("sudeste")) return "SSE";
  if (regionName.includes("nordeste")) return "NNE";
  return "";
}

function statusMatches(projectStatus, selectedStatus) {
  if (selectedStatus === "Em Desenvolvimento") {
    return projectStatus === "Em Construção" || projectStatus === "Planejado";
  }
  return projectStatus === selectedStatus;
}

function filteredExcluding(excludeKey) {
  const q = state.search.toLowerCase();
  return PROJECTS.filter(p => {
    const rc = getRegionCodeFromProject(p);
    const matchSearch = !q ||
      p.name.toLowerCase().includes(q) ||
      p.state.toLowerCase().includes(q) ||
      p.fuel.toLowerCase().includes(q) ||
      p.companies.join(" ").toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q);
    const matchType   = excludeKey === "types"    || state.types.length === 0    || state.types.includes(p.type);
    const matchRegion = excludeKey === "regions"   || state.regions.length === 0   || state.regions.includes(rc);
    const matchState  = excludeKey === "states"    || state.states.length === 0    || state.states.includes(p.state);
    const matchStatus = excludeKey === "statuses"  || state.statuses.length === 0   || state.statuses.some(s => statusMatches(p.status, s));
    return matchSearch && matchType && matchRegion && matchState && matchStatus;
  });
}

function getSelectedValues(selectId) {
  const select = document.getElementById(selectId);
  if (!select) return [];
  const selected = Array.from(select.selectedOptions).map(option => option.value);
  return selected.includes(MULTI_ALL_VALUE)
    ? []
    : selected.filter(value => value !== MULTI_ALL_VALUE);
}

function normalizeAllSelection(selectId, clickedValue = null) {
  const select = document.getElementById(selectId);
  if (!select) return;

  const allOption = Array.from(select.options).find(option => option.value === MULTI_ALL_VALUE);
  if (!allOption) return;

  if (clickedValue === MULTI_ALL_VALUE) {
    Array.from(select.options).forEach(option => {
      option.selected = option.value === MULTI_ALL_VALUE;
    });
    return;
  }

  // Specific item clicked (or called from code) — remove TODOS from selection
  allOption.selected = false;

  // If nothing remains selected, re-select TODOS
  if (Array.from(select.selectedOptions).length === 0) {
    allOption.selected = true;
  }
}

function rebuildSelect(selectId, allLabel, entries) {
  const select = document.getElementById(selectId);
  if (!select) return;
  const prevSelected = new Set(getSelectedValues(selectId));
  select.innerHTML = [
    `<option value="${MULTI_ALL_VALUE}">${allLabel}</option>`,
    ...entries.map(e => `<option value="${e.value}">${e.label}</option>`),
  ].join("");
  let restoredCount = 0;
  Array.from(select.options).forEach(opt => {
    if (opt.value !== MULTI_ALL_VALUE && prevSelected.has(opt.value)) {
      opt.selected = true;
      restoredCount++;
    }
  });
  if (restoredCount === 0) select.options[0].selected = true;
  updateSelectBtnText(selectId);
}

function updateFilterOptions() {
  const TYPE_ORDER = ["Refinaria", "Oleoduto", "Terminal", "Etanol", "Ferrovia", "Base"];
  const REGION_ORDER = [
    { value: "NNE", label: "Nordeste" },
    { value: "CO",  label: "Centro-Oeste" },
    { value: "NO",  label: "Norte" },
    { value: "SU",  label: "Sul" },
    { value: "SSE", label: "Sudeste" },
  ];
  const STATUS_ORDER = [
    { value: "Em Operação",        label: "Em Operação",              raw: ["Em Operação"] },
    { value: "Em Desenvolvimento", label: "Em Construção / Planejado", raw: ["Em Construção", "Planejado"] },
    { value: "Suspenso",           label: "Suspenso",                  raw: ["Suspenso"] },
  ];

  const typePool   = filteredExcluding("types");
  const availTypes = new Set(typePool.map(p => p.type));
  rebuildSelect("type-select", "TODOS",
    TYPE_ORDER.filter(t => availTypes.has(t)).map(t => ({ value: t, label: `${TYPE_META[t].icon} ${t}` }))
  );

  const regionPool   = filteredExcluding("regions");
  const availRegions = new Set(regionPool.map(p => getRegionCodeFromProject(p)).filter(Boolean));
  rebuildSelect("region-select", "TODAS",
    REGION_ORDER.filter(r => availRegions.has(r.value))
  );

  const statePool   = filteredExcluding("states");
  const availStates = new Set(statePool.map(p => p.state).filter(Boolean));
  const allUfs      = Object.keys(REGION_CODE_BY_STATE).sort((a, b) => a.localeCompare(b, "pt-BR"));
  const scopedUfs   = state.regions.length === 0
    ? allUfs
    : allUfs.filter(uf => state.regions.includes(REGION_CODE_BY_STATE[uf]));
  rebuildSelect("state-select", "TODAS",
    scopedUfs.filter(uf => availStates.has(uf)).map(uf => ({ value: uf, label: uf }))
  );

  const statusPool  = filteredExcluding("statuses");
  const rawStatuses = new Set(statusPool.map(p => p.status));
  rebuildSelect("status-select", "TODOS",
    STATUS_ORDER.filter(s => s.raw.some(r => rawStatuses.has(r)))
  );
}

// ── Type metadata ──────────────────────────────────────────────
const TYPE_META = {
  "Refinaria": { color: "#a855f7", icon: "🏭" },
  "Oleoduto":  { color: "#f97316", icon: "🛢" },
  "Terminal":  { color: "#0ea5e9", icon: "🚢" },
  "Etanol":    { color: "#22c55e", icon: "🌿" },
  "Ferrovia":  { color: "#eab308", icon: "🚆" },
  "Base":      { color: "#ec4899", icon: "📦" },
};

const STATUS_META = {
  "Em Operação":    { color: "#22c55e", bg: "#dcfce7" },
  "Em Construção":  { color: "#f59e0b", bg: "#fef3c7" },
  "Planejado":      { color: "#6366f1", bg: "#ede9fe" },
  "Suspenso":       { color: "#ef4444", bg: "#fee2e2" },
  "Concluído":      { color: "#64748b", bg: "#f1f5f9" },
};

// ── Render hero stats ──────────────────────────────────────────
function renderStats() {
  document.getElementById("stat-total").textContent = PROJECTS.length;
  document.getElementById("stat-active").textContent =
    PROJECTS.filter(p => p.status === "Em Operação").length;
  document.getElementById("stat-construction").textContent =
    PROJECTS.filter(p => p.status === "Em Construção").length;
  document.getElementById("stat-planned").textContent =
    PROJECTS.filter(p => p.status === "Planejado").length;
}

// ── Filter logic ───────────────────────────────────────────────
function filtered() {
  const q = state.search.toLowerCase();

  const normalizeText = (value) => value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const railwayGroupKey = (name) => {
    const normalized = normalizeText(name);

    if (normalized.includes("rumo malha oeste")) return "rumo-malha-oeste";
    if (normalized.includes("ferrovia centro atlantica") || normalized.includes(" fca ")) return "fca";
    if (normalized.includes("tereza cristina") || normalized.includes(" ftc ")) return "ftc";

    return normalized
      .replace(/\b(concessao|vigente|projeto|novo|relicitacao|prorrogacao|antecipada|s a)\b/g, "")
      .replace(/\s+/g, " ")
      .trim();
  };

  const railwayPriority = (project) => {
    if (project.status === "Em Operação") return 2;
    if (project.status === "Planejado" || project.status === "Em Construção") return 1;
    return 0;
  };

  const dedupeRailways = (projects) => {
    const output = [];
    const railIndexByKey = new Map();

    projects.forEach((project) => {
      if (project.type !== "Ferrovia") {
        output.push(project);
        return;
      }

      const key = railwayGroupKey(project.name);
      if (!railIndexByKey.has(key)) {
        railIndexByKey.set(key, output.length);
        output.push(project);
        return;
      }

      const currentIndex = railIndexByKey.get(key);
      const current = output[currentIndex];
      if (railwayPriority(project) > railwayPriority(current)) {
        output[currentIndex] = project;
      }
    });

    return output;
  };

  const base = PROJECTS.filter(p => {
    const projectRegionCode = getRegionCodeFromProject(p);
    const matchSearch = !q ||
      p.name.toLowerCase().includes(q) ||
      p.state.toLowerCase().includes(q) ||
      p.fuel.toLowerCase().includes(q) ||
      p.companies.join(" ").toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q);
    const matchType   = state.types.length === 0 || state.types.includes(p.type);
    const matchRegion = state.regions.length === 0 || state.regions.includes(projectRegionCode);
    const matchState  = state.states.length === 0 || state.states.includes(p.state);
    const matchStatus = state.statuses.length === 0 || state.statuses.some(s => statusMatches(p.status, s));

    return matchSearch && matchType && matchRegion && matchState && matchStatus;
  });

  return state.hideRailDuplicates ? dedupeRailways(base) : base;
}

// ── Card template ──────────────────────────────────────────────
function cardHTML(p) {
  const tm = TYPE_META[p.type]  || { color: "#94a3b8", icon: "📋" };
  const sm = STATUS_META[p.status] || { color: "#64748b", bg: "#f1f5f9" };
  const companies = p.companies.join(", ");

  return `
    <article class="card" data-id="${p.id}">
      <div class="card-top" style="border-top-color: ${tm.color}">
        <div class="card-badges">
          <span class="badge-type" style="background:${tm.color}20; color:${tm.color}; border-color:${tm.color}40">
            ${tm.icon} ${p.type}
          </span>
          <span class="badge-status" style="background:${sm.bg}; color:${sm.color}">
            ${p.status}
          </span>
        </div>
        <span class="card-flag" title="${p.country}">${p.flag}</span>
      </div>

      <div class="card-body">
        <h3 class="card-title">${p.name}</h3>
        <p class="card-country">📍 ${p.state}</p>
        <p class="card-description">${p.description}</p>
      </div>

      <div class="card-details">
        <div class="detail-row">
          <span class="detail-icon">⛽</span>
          <span class="detail-label">Combustíveis</span>
          <span class="detail-value">${p.fuel}</span>
        </div>
        <div class="detail-row">
          <span class="detail-icon">🏢</span>
          <span class="detail-label">Empresas</span>
          <span class="detail-value">${companies}</span>
        </div>
        <div class="detail-row">
          <span class="detail-icon">📊</span>
          <span class="detail-label">Capacidade</span>
          <span class="detail-value">${p.capacity}</span>
        </div>
        <div class="detail-row">
          <span class="detail-icon">📅</span>
          <span class="detail-label">Período</span>
          <span class="detail-value">${p.year}</span>
        </div>
      </div>

      ${p.link ? `<a class="card-link" href="${p.link}" target="_blank" rel="noopener">Ver mais ↗</a>` : ""}
    </article>
  `;
}

// ── Render grid ────────────────────────────────────────────────
function render() {
  const data = filtered();
  const grid  = document.getElementById("project-grid");
  const empty = document.getElementById("empty-state");
  const info  = document.getElementById("results-info");

  grid.innerHTML = data.map(cardHTML).join("");
  empty.classList.toggle("hidden", data.length > 0);
  grid.classList.toggle("hidden", data.length === 0);

  const total = PROJECTS.length;
  info.textContent = data.length === total
    ? `Exibindo todos os ${total} projetos`
    : `${data.length} de ${total} projetos`;

  // Animate cards in
  requestAnimationFrame(() => {
    grid.querySelectorAll(".card").forEach((el, i) => {
      el.style.animationDelay = `${i * 40}ms`;
      el.classList.add("card-enter");
    });
  });

  renderMapMarkers();
}

// ── Custom dropdown button text ────────────────────────────────
const SELECT_WRAP_IDS = {
  "type-select":   "type-wrap",
  "region-select": "region-wrap",
  "state-select":  "state-wrap",
  "status-select": "status-wrap",
};

function updateSelectBtnText(selectId) {
  const wrap = document.getElementById(SELECT_WRAP_IDS[selectId]);
  if (!wrap) return;
  const btnText = wrap.querySelector(".custom-select-text");
  if (!btnText) return;
  const select = document.getElementById(selectId);
  const values = getSelectedValues(selectId);
  if (values.length === 0) {
    const allOpt = Array.from(select.options).find(o => o.value === MULTI_ALL_VALUE);
    btnText.textContent = allOpt ? allOpt.text : "TODOS";
  } else if (values.length === 1) {
    const opt = Array.from(select.options).find(o => o.value === values[0]);
    btnText.textContent = opt ? opt.text : values[0];
  } else {
    btnText.textContent = `${values.length} selecionados`;
  }
}

function initCustomDropdowns() {
  const wrapIds = Object.values(SELECT_WRAP_IDS);

  wrapIds.forEach(wrapId => {
    const wrap = document.getElementById(wrapId);
    if (!wrap) return;
    wrap.addEventListener("click", e => e.stopPropagation());
    const btn = wrap.querySelector(".custom-select-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const isOpen = wrap.classList.contains("open");
      wrapIds.forEach(id => document.getElementById(id)?.classList.remove("open"));
      if (!isOpen) wrap.classList.add("open");
    });
  });

  document.addEventListener("click", () => {
    wrapIds.forEach(id => document.getElementById(id)?.classList.remove("open"));
  });
}

// ── Select helpers ─────────────────────────────────────────────
function initSelect(selectId, stateKey) {
  document.getElementById(selectId).addEventListener("change", e => {
    state[stateKey] = e.target.value;
    render();
  });
}

function initMultiSelect(selectId, stateKey) {
  const element = document.getElementById(selectId);
  if (!element) return;

  let prevSelected = new Set(Array.from(element.selectedOptions).map(o => o.value));

  element.addEventListener("change", () => {
    const currSelected = new Set(Array.from(element.selectedOptions).map(o => o.value));
    const added = [...currSelected].filter(v => !prevSelected.has(v));
    const clickedValue = added.length > 0 ? added[0] : null;

    normalizeAllSelection(selectId, clickedValue);
    prevSelected = new Set(Array.from(element.selectedOptions).map(o => o.value));

    state[stateKey] = getSelectedValues(selectId);
    updateSelectBtnText(selectId);

    updateFilterOptions();

    state.types    = getSelectedValues("type-select");
    state.regions  = getSelectedValues("region-select");
    state.states   = getSelectedValues("state-select");
    state.statuses = getSelectedValues("status-select");

    prevSelected = new Set(Array.from(element.selectedOptions).map(o => o.value));

    render();
  });
}

// ── Search ─────────────────────────────────────────────────────
function initSearch() {
  const input = document.getElementById("search-input");
  const clear = document.getElementById("clear-search");

  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      state.search = input.value.trim();
      clear.style.opacity = state.search ? "1" : "0";
      render();
    }, 200);
  });

  clear.addEventListener("click", () => {
    input.value = "";
    state.search = "";
    clear.style.opacity = "0";
    input.focus();
    render();
  });
}

// ── Reset all filters ──────────────────────────────────────────
function resetAll() {
  state.search = "";
  state.types = [];
  state.regions = [];
  state.states = [];
  state.statuses = [];
  state.hideRailDuplicates = true;
  document.getElementById("search-input").value = "";
  document.getElementById("clear-search").style.opacity = "0";
  ["type-select", "region-select", "state-select", "status-select"].forEach(id => {
    const select = document.getElementById(id);
    if (select) Array.from(select.options).forEach(o => { o.selected = o.value === MULTI_ALL_VALUE; });
  });
  updateFilterOptions();
  document.getElementById("toggle-hide-rail-duplicates").checked = true;
  render();
}

function initRailDuplicateToggle() {
  const toggle = document.getElementById("toggle-hide-rail-duplicates");
  if (!toggle) return;

  toggle.checked = state.hideRailDuplicates;

  toggle.addEventListener("change", e => {
    state.hideRailDuplicates = e.target.checked;
    render();
  });
}

// ── Map ────────────────────────────────────────────────────────
let map = null;
const mapMarkers = [];

const STATUS_COLORS = {
  "Em Operação":   { bg: "#dcfce720", border: "#22c55e" },
  "Em Construção": { bg: "#fef3c720", border: "#f59e0b" },
  "Planejado":     { bg: "#ede9fe20", border: "#6366f1" },
  "Suspenso":      { bg: "#fee2e220", border: "#ef4444" },
};

function initMap() {
  if (!document.getElementById("map")) return;
  map = L.map("map", { scrollWheelZoom: false, zoomControl: true })
    .setView([-15.5, -52.0], 4);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
    maxZoom: 18,
  }).addTo(map);
}

function renderMapMarkers() {
  if (!map) return;
  mapMarkers.forEach(m => map.removeLayer(m));
  mapMarkers.length = 0;

  filtered()
    .filter(p => p.lat && p.lng)
    .forEach(p => {
      const tm = TYPE_META[p.type] || { color: "#94a3b8" };
      const sm = STATUS_COLORS[p.status] || { bg: "#ffffff10", border: "#94a3b8" };

      const marker = L.circleMarker([p.lat, p.lng], {
        radius: 5,
        fillColor: tm.color,
        color: "#fff",
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.85,
      }).addTo(map);

      const smFull = STATUS_META[p.status] || { color: "#64748b", bg: "#f1f5f9" };
      marker.bindPopup(`
        <div class="map-popup">
          <strong>${p.flag} ${p.name}</strong>
          <div class="popup-state">📍 ${p.state} · ${p.type}</div>
          <div class="popup-fuel">⛽ ${p.fuel}</div>
          <span class="popup-status" style="background:${smFull.bg};color:${smFull.color}">${p.status}</span>
        </div>
      `, { maxWidth: 260 });

      mapMarkers.push(marker);
    });
}

// ── Scroll-based header shadow ─────────────────────────────────
window.addEventListener("scroll", () => {
  document.querySelector(".site-header").classList.toggle("scrolled", window.scrollY > 10);
}, { passive: true });

// ── Init ────────────────────────────────────────────────────────
renderStats();
initSearch();
initCustomDropdowns();
initMultiSelect("type-select",   "types");
initMultiSelect("region-select", "regions");
initMultiSelect("state-select",  "states");
initMultiSelect("status-select", "statuses");
initRailDuplicateToggle();
document.getElementById("btn-reset").addEventListener("click", resetAll);
updateFilterOptions();
initMap();
render();
