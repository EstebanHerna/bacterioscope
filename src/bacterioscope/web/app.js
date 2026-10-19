"use strict";

(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const SCALE_MAX_MM = 40;
  const DISK_MM = 6;
  const NEAR_BREAKPOINT_MM = 2;
  const MIN_MM = 6;
  const MAX_MM = 60;

  const CODES = {
    meropenem: "MEM", imipenem: "IPM", ertapenem: "ETP", doripenem: "DOR",
    ampicillin: "AMP", "amoxicillin-clavulanate": "AMC", "piperacillin-tazobactam": "TZP",
    ceftriaxone: "CRO", ceftazidime: "CAZ", cefepime: "FEP", ciprofloxacin: "CIP",
    levofloxacin: "LVX", gentamicin: "GEN", amikacin: "AMK",
    "trimethoprim-sulfamethoxazole": "SXT",
  };

  const NAMES_ES = {
    ampicillin: "ampicilina", "amoxicillin-clavulanate": "amoxicilina-clavulanato",
    "piperacillin-tazobactam": "piperacilina-tazobactam", ceftriaxone: "ceftriaxona",
    ceftazidime: "ceftazidima", cefepime: "cefepima", ciprofloxacin: "ciprofloxacino",
    levofloxacin: "levofloxacino", gentamicin: "gentamicina", amikacin: "amikacina",
    "trimethoprim-sulfamethoxazole": "trimetoprim-sulfametoxazol",
  };

  const DANGLING = new Set([
    "a", "al", "de", "del", "el", "la", "las", "los", "en", "y", "o", "para", "por", "sobre", "con",
    "the", "of", "to", "and", "for", "in", "on",
  ]);
  const ACRONYMS = new Set(["whonet", "ops", "oms", "ins", "paho", "who", "kpc", "ndm", "blee", "esbl", "amr", "cdc", "clsi"]);

  const LOUPE_ZOOM = 3;
  const TAG_TURNS = [0, 0.35, -0.35, 0.7, -0.7, 1.05, -1.05, 1.4, -1.4, 1.75, -1.75, 2.1, -2.1, 2.45, -2.45, 2.8, -2.8, Math.PI];

  const I18N = {
    es: {
      title: "BacterioScope · Lectura de placa",
      stageTitle: "Placa de antibiograma",
      newPlate: "Nueva placa",
      intakeLead: "Suelta aquí la foto de la placa",
      intakeSub: "Una foto desde arriba, con el borde del plato visible. Se calibra contra el borde de 90 mm.",
      choosePhoto: "Elegir foto",
      samplesTitle: "Placas de muestra",
      sampleSynthetic: "sintética",
      sampleReal: "foto real",
      toggleGrid: "Retícula mm",
      toggleContours: "Contornos",
      legendFlag: "Medición marcada por el sistema",
      dragHint: "Arrastra la manija de un halo para corregir su diámetro.",
      benchTitle: "Lectura por antibiótico",
      organism: "Organismo",
      panel: "Antibióticos",
      panelManual: "Asignación manual",
      panelSample: "Distribución de la muestra",
      benchNote: "Categorías CLSI M100-Ed33 (2023) para Enterobacterales. Las reglas expertas candidatas (Ed36) siguen desactivadas hasta su revisión.",
      unassigned: "Sin asignar",
      useAlerts: "Incluir alertas públicas del INS y la OPS",
      reviewBtn: "Revisar con Nemotron",
      reviewing: "Revisando…",
      reviewTitle: "Revisión de la placa",
      reviewer: "Revisado por",
      download: "Firmar y descargar JSON",
      coverageTitle: "Cobertura de reglas",
      alertsTitle: "Alertas públicas",
      traceTitle: "Trazabilidad",
      disclaimer: "Herramienta de apoyo a la decisión, no un dispositivo médico. Cada resultado debe revisarlo y firmarlo un profesional de microbiología. La exactitud sobre fotos clínicas reales aún está lejos del objetivo clínico (EA 32,9 % frente a ≥ 90 %).",
      measuring: "Midiendo halos…",
      calibration: "1 mm = {px} px · borde del plato = 90 mm · {n} discos",
      flag_low_circularity: "Contorno irregular",
      flag_small_zone: "Halo menor que el disco",
      flag_boundary: "Toca el borde de la foto",
      flag_crop_boundary: "Borde del recorte, no del halo",
      flag_overlap: "Se cruza con un halo vecino",
      nearBreakpoint: "A menos de 2 mm de un punto de corte",
      corrected: "Corregido · medido {mm} mm",
      restore: "Restaurar",
      corrections: "{n} corrección(es) manual(es). La revisión del agente queda bloqueada hasta restaurarlas: el reporte todavía no puede rastrear un diámetro corregido.",
      assignFirst: "Asigna el antibiótico de este disco para clasificarlo.",
      diskLabel: "Disco {pos}",
      diskAria: "Disco {pos}, {drug}, {mm} milímetros, categoría {cat}. Flechas para corregir el diámetro.",
      statusGrounded: "Narrativa de Nemotron (Nebius Token Factory), validada contra la evidencia.",
      statusFallback: "Sin narrativa del modelo: {reason}. Todo lo determinístico de abajo sigue completo.",
      fallback_token_factory_unavailable: "Nemotron no está disponible en este servidor",
      fallback_model_output_not_json: "la respuesta del modelo no fue JSON",
      fallback_model_output_malformed: "la respuesta del modelo vino incompleta",
      fallback_citation_not_in_evidence: "el modelo citó evidencia que no existe",
      fallback_schema_validation_failed: "el reporte no cumplió el contrato",
      fallback_rule_claim_conflicts_with_catalog_status: "el modelo afirmó algo sobre reglas que no se evaluaron",
      catalog_no_rules_configured: "No hay reglas configuradas: no se evaluó.",
      catalog_rules_not_enabled_for_standard_or_review: "Hay candidatas, desactivadas hasta su revisión.",
      catalog_rules_available: "Reglas evaluadas.",
      cov_intrinsic_resistance: "Resistencia intrínseca",
      cov_phenotype: "Fenotipo",
      cov_cascade: "Reporte en cascada",
      cov_esbl: "Tamizaje BLEE",
      cov_esbl_off: "No ejecutado: requiere la potencia del disco y el contexto del ensayo.",
      cov_rule_standard: "Edición de reglas",
      cov_alerts: "Búsqueda de alertas",
      alert_not_requested: "No solicitada.",
      alert_provided: "Aportadas por el usuario.",
      alert_available: "Resultados oficiales encontrados.",
      alert_no_results: "Sin resultados elegibles (no significa que no haya alertas).",
      alert_partial: "Una fuente no respondió.",
      alert_unavailable: "Fuentes no disponibles.",
      noAlerts: "Sin alertas en este reporte.",
      trace_analysis: "Análisis",
      trace_image: "SHA-256 imagen",
      trace_commit: "Commit",
      trace_version: "Versión",
      trace_measurement: "Medición",
      errorGeneric: "Algo falló: {detail}",
      needReviewer: "Escribe quién revisa antes de firmar.",
      downloaded: "Reporte firmado descargado.",
      panelApplied: "Antibióticos asignados por posición.",
      s_plate_pan_susceptible: "Pansensible",
      s_plate_mdr_organism: "Multirresistente",
      s_plate_mixed_sir: "Perfil mixto",
      s_plate_12disk_panel: "Panel de 12 discos",
      s_plate_carbapenem_resistant: "Resistente a carbapenémicos",
      s_plate_uneven_light: "Luz despareja",
      s_plate_large_zones: "Halos grandes",
      s_plate_esbl_like: "Perfil tipo BLEE",
      s_real_plate_box4: "Placa real, 16 discos",
      resultsTitle: "Resultados del reporte",
      colDrug: "Antibiótico",
      colMm: "mm",
      colCat: "Cat.",
      colNote: "Nota",
      ex_unresolved: "Sin antibiótico asignado",
      ex_duplicate: "Antibiótico repetido en otro disco",
      ex_flags: "Excluido de las reglas: medición marcada",
      inRules: "Apto para reglas",
      syntheticSample: "muestra sintética",
      legendOrder: "Disco 1 y sentido de lectura",
      intakeLeadTouch: "Toma o elige la foto de la placa",
      loupeZoom: "borde ×3",
    },
    en: {
      title: "BacterioScope · Plate reading",
      stageTitle: "Antibiogram plate",
      newPlate: "New plate",
      intakeLead: "Drop the plate photo here",
      intakeSub: "One photo from above with the plate rim visible. It is calibrated against the 90 mm rim.",
      choosePhoto: "Choose photo",
      samplesTitle: "Sample plates",
      sampleSynthetic: "synthetic",
      sampleReal: "real photo",
      toggleGrid: "mm graticule",
      toggleContours: "Contours",
      legendFlag: "Measurement flagged by the system",
      dragHint: "Drag a zone's handle to correct its diameter.",
      benchTitle: "Reading per antibiotic",
      organism: "Organism",
      panel: "Antibiotics",
      panelManual: "Manual assignment",
      panelSample: "Sample layout",
      benchNote: "CLSI M100-Ed33 (2023) categories for Enterobacterales. Candidate expert rules (Ed36) stay disabled until reviewed.",
      unassigned: "Unassigned",
      useAlerts: "Include INS and PAHO public alerts",
      reviewBtn: "Review with Nemotron",
      reviewing: "Reviewing…",
      reviewTitle: "Plate review",
      reviewer: "Reviewed by",
      download: "Sign and download JSON",
      coverageTitle: "Rule coverage",
      alertsTitle: "Public alerts",
      traceTitle: "Traceability",
      disclaimer: "Decision-support tool, not a medical device. A qualified microbiologist must review and sign every result. Accuracy on real clinical photos is still far from the clinical target (EA 32.9% vs ≥ 90%).",
      measuring: "Measuring zones…",
      calibration: "1 mm = {px} px · plate rim = 90 mm · {n} disks",
      flag_low_circularity: "Irregular contour",
      flag_small_zone: "Zone smaller than the disk",
      flag_boundary: "Touches the photo edge",
      flag_crop_boundary: "Search-crop edge, not the zone edge",
      flag_overlap: "Overlaps a neighbouring zone",
      nearBreakpoint: "Within 2 mm of a breakpoint",
      corrected: "Corrected · measured {mm} mm",
      restore: "Restore",
      corrections: "{n} manual correction(s). The agent review is blocked until they are restored: the report cannot trace a corrected diameter yet.",
      assignFirst: "Assign this disk's antibiotic to classify it.",
      diskLabel: "Disk {pos}",
      diskAria: "Disk {pos}, {drug}, {mm} millimetres, category {cat}. Arrow keys correct the diameter.",
      statusGrounded: "Nemotron narrative (Nebius Token Factory), validated against the evidence.",
      statusFallback: "No model narrative: {reason}. Everything deterministic below is complete.",
      fallback_token_factory_unavailable: "Nemotron is not available on this server",
      fallback_model_output_not_json: "the model reply was not JSON",
      fallback_model_output_malformed: "the model reply was incomplete",
      fallback_citation_not_in_evidence: "the model cited evidence that does not exist",
      fallback_schema_validation_failed: "the report broke its contract",
      fallback_rule_claim_conflicts_with_catalog_status: "the model claimed something about rules that were not evaluated",
      catalog_no_rules_configured: "No rules configured: not evaluated.",
      catalog_rules_not_enabled_for_standard_or_review: "Candidates exist, disabled until reviewed.",
      catalog_rules_available: "Rules evaluated.",
      cov_intrinsic_resistance: "Intrinsic resistance",
      cov_phenotype: "Phenotype",
      cov_cascade: "Cascade reporting",
      cov_esbl: "ESBL screen",
      cov_esbl_off: "Not run: needs disk potency and assay context.",
      cov_rule_standard: "Rule edition",
      cov_alerts: "Alert search",
      alert_not_requested: "Not requested.",
      alert_provided: "Supplied by the user.",
      alert_available: "Official results found.",
      alert_no_results: "No eligible results (not proof that no alert exists).",
      alert_partial: "One source did not respond.",
      alert_unavailable: "Sources unavailable.",
      noAlerts: "No alerts in this report.",
      trace_analysis: "Analysis",
      trace_image: "Image SHA-256",
      trace_commit: "Commit",
      trace_version: "Version",
      trace_measurement: "Measurement",
      errorGeneric: "Something failed: {detail}",
      needReviewer: "Enter who is reviewing before signing.",
      downloaded: "Signed report downloaded.",
      panelApplied: "Antibiotics assigned by position.",
      s_plate_pan_susceptible: "Pan-susceptible",
      s_plate_mdr_organism: "Multidrug-resistant",
      s_plate_mixed_sir: "Mixed profile",
      s_plate_12disk_panel: "12-disk panel",
      s_plate_carbapenem_resistant: "Carbapenem-resistant",
      s_plate_uneven_light: "Uneven light",
      s_plate_large_zones: "Large zones",
      s_plate_esbl_like: "ESBL-like profile",
      s_real_plate_box4: "Real plate, 16 disks",
      resultsTitle: "Report results",
      colDrug: "Antibiotic",
      colMm: "mm",
      colCat: "Cat.",
      colNote: "Note",
      ex_unresolved: "No antibiotic assigned",
      ex_duplicate: "Antibiotic repeated on another disk",
      ex_flags: "Excluded from rules: flagged measurement",
      inRules: "Eligible for rules",
      syntheticSample: "synthetic sample",
      legendOrder: "Disk 1 and reading direction",
      intakeLeadTouch: "Take or choose the plate photo",
      loupeZoom: "edge ×3",
    },
  };

  const state = {
    lang: "es",
    samples: [],
    plate: null,
    image: null,
    labels: [],
    overrides: {},
    rows: [],
    order: [],
    selected: null,
    grid: false,
    contours: true,
    review: null,
    sampleLayout: false,
    tagPlace: {},
    synthetic: false,
  };

  const $ = (id) => document.getElementById(id);

  function t(key, vars = {}) {
    const table = I18N[state.lang] || I18N.es;
    const text = table[key] ?? I18N.es[key] ?? key;
    return text.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
  }

  function locale() {
    return state.lang === "es" ? "es-CO" : "en-US";
  }

  function num(value, digits) {
    return Number(value).toLocaleString(locale(), { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function fmt(mm) {
    return num(mm, 1);
  }

  function drugName(label) {
    return state.lang === "es" ? NAMES_ES[label] || label : label;
  }

  function store(key, value) {
    try { localStorage.setItem(key, value); } catch { /* storage unavailable */ }
  }

  function recall(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  }

  function svg(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "style") node.style.cssText = String(v);
      else node.setAttribute(k, String(v));
    }
    return node;
  }

  function html(tag, attrs = {}, text) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "style") node.style.cssText = String(v);
      else node.setAttribute(k, String(v));
    }
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(name) {
    const node = svg("svg", { class: "icon", "aria-hidden": "true" });
    node.append(svg("use", { href: `#i-${name}` }));
    return node;
  }

  function code(label, index) {
    if (!label) return `#${index + 1}`;
    return CODES[label] || label.slice(0, 3).toUpperCase();
  }

  let toastTimer = 0;
  function toast(message, isError = false) {
    const node = $("toast");
    node.textContent = message;
    node.classList.toggle("is-error", isError);
    node.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("is-on"), 4200);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    let body = null;
    try { body = await response.json(); } catch { body = null; }
    if (!response.ok) {
      const detail = body && typeof body.detail === "string" ? body.detail : `HTTP ${response.status}`;
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  /* ---------- language ---------- */

  function applyLanguage() {
    document.documentElement.lang = state.lang;
    document.title = t("title");
    for (const node of document.querySelectorAll("[data-i18n]")) {
      node.textContent = t(node.dataset.i18n);
    }
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
      document.querySelector(".intake-lead").textContent = t("intakeLeadTouch");
    }
    for (const button of document.querySelectorAll(".lang button")) {
      button.setAttribute("aria-pressed", String(button.dataset.lang === state.lang));
    }
    renderSamples();
    if (state.plate) {
      renderCalibration();
      renderPanelSelect();
      drawOverlay(false);
      renderRulers();
      renderCorrections();
      if (state.selected !== null) drawLoupe(state.selected);
    }
    if (state.review) renderReview();
  }

  function setLanguage(lang) {
    state.lang = lang === "en" ? "en" : "es";
    store("bs-lang", state.lang);
    applyLanguage();
  }

  /* ---------- intake ---------- */

  async function loadSamples() {
    try {
      state.samples = await api("/api/samples");
    } catch {
      state.samples = [];
    }
    renderSamples();
  }

  function renderSamples() {
    const list = $("sample-list");
    list.replaceChildren();
    for (const sample of state.samples) {
      const key = `s_${sample.id}`;
      const name = I18N.es[key] ? t(key) : sample.id.replace(/^(real_)?plate_/, "").replace(/_/g, " ");
      const button = html("button", { type: "button", class: "sample" });
      const img = html("img", { src: sample.image_url, alt: "", decoding: "async" });
      button.append(img, html("span", {}, name),
        html("span", { class: "sample-tag" }, sample.synthetic ? t("sampleSynthetic") : t("sampleReal")));
      button.addEventListener("click", () => analyze({ sampleId: sample.id, imageUrl: sample.image_url }));
      const item = html("li");
      item.append(button);
      list.append(item);
    }
  }

  function setBusy(busy) {
    $("dropzone").classList.toggle("is-busy", busy);
    for (const node of document.querySelectorAll(".sample, #file-input")) node.disabled = busy;
  }

  function showIntakeError(message) {
    const node = $("intake-error");
    node.textContent = message;
    node.hidden = !message;
  }

  async function analyze({ file, sampleId, imageUrl }) {
    showIntakeError("");
    setBusy(true);
    toast(t("measuring"));
    const form = new FormData();
    if (file) form.append("image", file);
    else form.append("sample_id", sampleId);
    try {
      const plate = await api("/api/plates", { method: "POST", body: form });
      const url = file ? URL.createObjectURL(file) : imageUrl;
      state.synthetic = Boolean(!file && state.samples.find((s) => s.id === sampleId)?.synthetic);
      await openPlate(plate, url);
      $("toast").classList.remove("is-on");
    } catch (error) {
      showIntakeError(t("errorGeneric", { detail: error.message }));
    } finally {
      setBusy(false);
    }
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.alt = "";
      img.draggable = false;
      img.decoding = "async";
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("image"));
      img.src = url;
    });
  }

  async function openPlate(plate, url) {
    if (state.image && state.image.src.startsWith("blob:")) URL.revokeObjectURL(state.image.src);
    state.image = await loadImage(url);
    state.plate = plate;
    state.labels = plate.suggested_labels.slice();
    state.sampleLayout = state.labels.some(Boolean);
    state.overrides = {};
    state.selected = null;
    state.review = null;
    state.order = clockwiseOrder(plate);
    state.tagPlace = {};
    $("loupe").hidden = true;
    $("review").hidden = true;
    const frame = $("plate-frame");
    frame.querySelector("img")?.remove();
    frame.prepend(state.image);
    frame.style.setProperty("--ar", plate.image.width / plate.image.height || 1);
    $("box").dataset.state = "plate";
    $("intake").hidden = true;
    $("plate").hidden = false;
    $("bench").hidden = false;
    $("new-plate").hidden = false;
    renderCalibration();
    renderPanelSelect();
    await classify();
    drawOverlay(true);
  }

  function resetToIntake() {
    state.plate = null;
    state.review = null;
    $("box").dataset.state = "intake";
    $("intake").hidden = false;
    $("plate").hidden = true;
    $("bench").hidden = true;
    $("review").hidden = true;
    $("new-plate").hidden = true;
    $("calibration").textContent = "";
    $("strip-sample").hidden = true;
    $("file-input").value = "";
  }

  function bindIntake() {
    const zone = $("dropzone");
    $("file-input").addEventListener("change", (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) analyze({ file });
    });
    zone.addEventListener("dragover", (event) => { event.preventDefault(); zone.classList.add("is-over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("is-over"));
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      zone.classList.remove("is-over");
      const file = event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) analyze({ file });
    });
    $("new-plate").addEventListener("click", resetToIntake);
  }

  /* ---------- geometry ---------- */

  function clockwiseOrder(plate) {
    const { cx, cy } = plate.calibration.plate;
    const angle = (disk) => {
      const a = Math.atan2(disk.center[0] - cx, -(disk.center[1] - cy));
      return (a + 2 * Math.PI) % (2 * Math.PI);
    };
    return plate.disks.map((d) => d.index).sort((a, b) => angle(plate.disks[a]) - angle(plate.disks[b]));
  }

  function pxPerMm() {
    return state.plate.calibration.px_per_mm;
  }

  function diameterMm(index) {
    const override = state.overrides[index];
    return override !== undefined ? override : state.plate.disks[index].diameter_mm;
  }

  function radiusPx(index) {
    return (diameterMm(index) / 2) * pxPerMm();
  }

  /* ---------- classification ---------- */

  function categoryFor(mm, bp) {
    if (!bp || bp.S === undefined) return "UNKNOWN";
    const whole = Math.floor(mm + 0.5);
    if (whole >= bp.S) return "S";
    if (bp.SDD_low !== undefined && whole >= bp.SDD_low && whole <= bp.SDD_high) return "SDD";
    if (bp.R !== undefined && whole <= bp.R) return "R";
    if (bp.I_low !== undefined && whole >= bp.I_low && whole <= bp.I_high) return "I";
    return "UNKNOWN";
  }

  function currentCategory(index) {
    const row = state.rows[index];
    if (!row || !state.labels[index]) return "UNKNOWN";
    return categoryFor(diameterMm(index), row.breakpoints);
  }

  async function classify() {
    const body = { labels: state.labels, overrides: state.overrides };
    try {
      const result = await api(`/api/plates/${state.plate.analysis_id}/classify`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      state.rows = result.disks;
    } catch (error) {
      toast(t("errorGeneric", { detail: error.message }), true);
    }
    renderRulers();
    renderCorrections();
  }

  /* ---------- overlay ---------- */

  function renderCalibration() {
    const node = $("calibration");
    node.replaceChildren(t("calibration", { px: num(pxPerMm(), 2), n: state.plate.disks.length }));
    if (state.synthetic) node.append(" · ", html("span", { class: "badge" }, t("syntheticSample")));
    $("strip-sample").hidden = !state.synthetic;
  }

  function drawRim(group) {
    const { cx, cy, r } = state.plate.calibration.plate;
    const { width, height } = state.plate.image;
    group.append(svg("path", {
      class: "outside", "fill-rule": "evenodd",
      d: `M0 0H${width}V${height}H0Z M${cx - r} ${cy} a${r} ${r} 0 1 0 ${2 * r} 0 a${r} ${r} 0 1 0 ${-2 * r} 0Z`,
    }));
    group.append(svg("circle", { class: "rim", cx, cy, r }));
    for (let i = 0; i < 72; i += 1) {
      const a = (i / 72) * 2 * Math.PI;
      const major = i % 6 === 0;
      const inner = r * (major ? 0.955 : 0.975);
      group.append(svg("line", {
        class: major ? "tick major" : "tick",
        x1: cx + Math.sin(a) * inner, y1: cy - Math.cos(a) * inner,
        x2: cx + Math.sin(a) * r, y2: cy - Math.cos(a) * r,
      }));
    }
    const s = r * 0.03;
    group.append(svg("path", {
      class: "origin",
      d: `M ${cx} ${cy - r - s * 0.4} l ${-s} ${-s * 1.6} h ${2 * s} z`,
    }));
    const arcR = r * 1.045;
    const end = Math.PI / 7;
    group.append(svg("path", {
      class: "order-arc",
      d: `M ${cx + Math.sin(0.06) * arcR} ${cy - Math.cos(0.06) * arcR} A ${arcR} ${arcR} 0 0 1 ${cx + Math.sin(end) * arcR} ${cy - Math.cos(end) * arcR}`,
    }));
  }

  function drawGraticule(group) {
    const { cx, cy, r } = state.plate.calibration.plate;
    const step = pxPerMm();
    const clip = svg("clipPath", { id: "plate-clip" });
    clip.append(svg("circle", { cx, cy, r }));
    const grid = svg("g", { class: "graticule", "clip-path": "url(#plate-clip)" });
    const count = Math.ceil(r / step);
    for (let i = -count; i <= count; i += 1) {
      const major = i % 10 === 0;
      const cls = major ? "grid-line major" : "grid-line";
      if (!major && i % 2 !== 0) continue;
      grid.append(svg("line", { class: cls, x1: cx + i * step, y1: cy - r, x2: cx + i * step, y2: cy + r }));
      grid.append(svg("line", { class: cls, x1: cx - r, y1: cy + i * step, x2: cx + r, y2: cy + i * step }));
    }
    group.append(clip, grid);
  }

  function zonePath(disk) {
    if (!disk.contour.length) return "";
    return `M ${disk.contour.map((p) => p.join(" ")).join(" L ")} Z`;
  }

  function drawZone(group, disk, position, animate) {
    const flagged = disk.flags.length > 0;
    const g = svg("g", {
      class: `zone${flagged ? " is-flagged" : ""}${state.overrides[disk.index] !== undefined ? " is-corrected" : ""}${state.selected === disk.index ? " is-selected" : ""}`,
      "data-index": disk.index,
      style: `--delay:${position * 70}ms`,
    });
    const [x, y] = disk.center;
    const path = zonePath(disk);
    if (path && flagged) g.append(svg("path", { class: "hatch", d: path }));
    if (path) g.append(svg("path", { class: "contour", d: path, ...(animate ? { pathLength: 1 } : {}) }));
    g.append(svg("circle", { class: "caliper", cx: x, cy: y, r: radiusPx(disk.index), ...(animate ? { pathLength: 1 } : {}) }));
    g.append(svg("circle", { class: "disk", cx: x, cy: y, r: disk.disk_radius }));
    g.append(svg("circle", { class: "focus-ring", cx: x, cy: y, r: radiusPx(disk.index) + disk.disk_radius * 0.35 }));
    g.append(svg("circle", { class: "hit", cx: x, cy: y, r: Math.max(radiusPx(disk.index), disk.disk_radius * 2) }));
    g.addEventListener("click", () => select(disk.index));
    group.append(g);
  }

  function pct(value, total) {
    return `${(value / total) * 100}%`;
  }

  function fillTag(tag, index, position) {
    const disk = state.plate.disks[index];
    const cat = currentCategory(index);
    tag.replaceChildren();
    if (disk.flags.length) tag.append(icon("flag"));
    tag.append(
      html("span", { class: "tag-code" }, code(state.labels[index], position)),
      html("span", { class: "tag-mm" }, fmt(diameterMm(index))),
    );
    if (cat !== "UNKNOWN") tag.append(html("span", { class: "tag-cat", "data-cat": cat }, cat));
  }

  function frameScale() {
    const width = $("plate-frame").getBoundingClientRect().width;
    return width > 0 ? width / state.plate.image.width : 1;
  }

  function tagSpot(index, size, place) {
    const s = frameScale();
    const { cx, cy } = state.plate.calibration.plate;
    const [x, y] = state.plate.disks[index].center;
    const dist = Math.hypot(x - cx, y - cy);
    const [bx, by] = dist > 1 ? [(x - cx) / dist, (y - cy) / dist] : [0, -1];
    const cos = Math.cos(place.turn);
    const sin = Math.sin(place.turn);
    const ux = bx * cos - by * sin;
    const uy = bx * sin + by * cos;
    const w = size.w / s;
    const h = size.h / s;
    const reach = (Math.abs(ux) * w) / 2 + (Math.abs(uy) * h) / 2;
    const d = radiusPx(index) + (6 + place.k * 14) / s + reach;
    return { x: x + ux * d, y: y + uy * d, w, h };
  }

  function leaderSegment(index, spot) {
    const [x, y] = state.plate.disks[index].center;
    const len = Math.hypot(spot.x - x, spot.y - y) || 1;
    const vx = (spot.x - x) / len;
    const vy = (spot.y - y) / len;
    const exit = Math.min(vx ? spot.w / 2 / Math.abs(vx) : Infinity, vy ? spot.h / 2 / Math.abs(vy) : Infinity);
    const r = radiusPx(index);
    return {
      x1: x + vx * r, y1: y + vy * r, x2: spot.x - vx * exit, y2: spot.y - vy * exit,
      visible: (len - exit - r) * frameScale() > 4,
    };
  }

  function drawLeader(index, spot) {
    const group = $("leaders");
    if (!group) return;
    let line = group.querySelector(`[data-index="${index}"]`);
    if (!line) {
      line = svg("line", { class: "leader", "data-index": index, style: `--delay:${state.order.indexOf(index) * 70}ms` });
      group.append(line);
    }
    const seg = leaderSegment(index, spot);
    for (const key of ["x1", "y1", "x2", "y2"]) line.setAttribute(key, seg[key]);
    line.style.visibility = seg.visible ? "" : "hidden";
  }

  function placeMark(index) {
    const { width, height } = state.plate.image;
    const [x, y] = state.plate.disks[index].center;
    const r = radiusPx(index);
    const position = state.order.indexOf(index);
    const tag = document.querySelector(`.tag[data-index="${index}"]`);
    const handle = document.querySelector(`.handle[data-index="${index}"]`);
    if (tag) {
      fillTag(tag, index, position);
      const size = { w: tag.offsetWidth, h: tag.offsetHeight };
      const spot = tagSpot(index, size, state.tagPlace[index] || { turn: 0, k: 0 });
      tag.style.left = pct(spot.x, width);
      tag.style.top = pct(spot.y, height);
      drawLeader(index, spot);
    }
    if (handle) {
      handle.style.left = pct(x + r, width);
      handle.style.top = pct(y, height);
      const cat = currentCategory(index);
      const label = state.labels[index];
      handle.setAttribute("aria-label", t("diskAria", {
        pos: position + 1, drug: label ? drugName(label) : t("unassigned"),
        mm: fmt(diameterMm(index)), cat: cat === "UNKNOWN" ? "–" : cat,
      }));
    }
  }

  function drawMarks(animate) {
    const layer = document.querySelector(".marks") || html("div", { class: "marks" });
    layer.replaceChildren();
    layer.classList.toggle("draw-in-tags", animate);
    state.order.forEach((index, position) => {
      const selected = state.selected === index;
      layer.append(html("div", {
        class: `tag${selected ? " is-selected" : ""}`, "data-index": index, style: `--delay:${position * 70}ms`,
      }));
      const handle = html("button", {
        type: "button", class: `handle${selected ? " is-visible" : ""}`, "data-index": index,
      });
      bindHandle(handle, index);
      layer.append(handle);
    });
    if (!layer.isConnected) $("plate-frame").append(layer);
    layoutTags();
  }

  function overlaps(a, b) {
    return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  }

  function tagRect(spot, pad) {
    return {
      left: spot.x - spot.w / 2 - pad, right: spot.x + spot.w / 2 + pad,
      top: spot.y - spot.h / 2 - pad, bottom: spot.y + spot.h / 2 + pad,
    };
  }

  function circleHitsRect(x, y, r, rect) {
    const nx = Math.max(rect.left, Math.min(x, rect.right));
    const ny = Math.max(rect.top, Math.min(y, rect.bottom));
    return Math.hypot(nx - x, ny - y) < r;
  }

  function segmentHitsCircle(seg, x, y, r) {
    const dx = seg.x2 - seg.x1;
    const dy = seg.y2 - seg.y1;
    const t = Math.max(0, Math.min(1, ((x - seg.x1) * dx + (y - seg.y1) * dy) / (dx * dx + dy * dy || 1)));
    return Math.hypot(seg.x1 + t * dx - x, seg.y1 + t * dy - y) < r;
  }

  function segmentsCross(a, b) {
    const side = (s, x, y) => (s.x2 - s.x1) * (y - s.y1) - (s.y2 - s.y1) * (x - s.x1);
    return side(a, b.x1, b.y1) * side(a, b.x2, b.y2) < 0 && side(b, a.x1, a.y1) * side(b, a.x2, a.y2) < 0;
  }

  function spotCost(spot, index, placed, pad) {
    const { width, height } = state.plate.image;
    const rect = tagRect(spot, pad);
    const seg = leaderSegment(index, spot);
    let cost = 0;
    if (rect.left < 0 || rect.top < 0 || rect.right > width || rect.bottom > height) cost += 1000;
    for (const other of placed) {
      if (overlaps(rect, other.rect)) cost += 1000;
      if (seg.visible && other.seg.visible && segmentsCross(seg, other.seg)) cost += 600;
      if (other.seg.visible && segmentHitsCircle(other.seg, spot.x, spot.y, Math.min(spot.w, spot.h) / 2)) cost += 1000;
    }
    for (const other of state.order) {
      if (other === index) continue;
      const [x, y] = state.plate.disks[other].center;
      if (circleHitsRect(x, y, state.plate.disks[other].disk_radius * 1.3, rect)) cost += 3000;
      if (circleHitsRect(x, y, radiusPx(other), rect)) cost += 1000;
      if (seg.visible && segmentHitsCircle(seg, x, y, radiusPx(other))) cost += 400;
    }
    return cost;
  }

  function bestPlace(index, size, placed, pad) {
    let best = { turn: 0, k: 0, cost: Infinity };
    for (let k = 0; k < 8; k += 1) {
      for (const turn of TAG_TURNS) {
        const hits = spotCost(tagSpot(index, size, { turn, k }), index, placed, pad);
        const cost = hits + k * 30 + Math.abs(turn) * 10;
        if (cost < best.cost) best = { turn, k, cost };
        if (hits === 0) return best;
      }
    }
    return best;
  }

  function layoutTags() {
    if (!state.plate) return;
    const pad = 2 / frameScale();
    const placed = [];
    for (const index of state.order) {
      const tag = document.querySelector(`.tag[data-index="${index}"]`);
      if (!tag) continue;
      fillTag(tag, index, state.order.indexOf(index));
      const size = { w: tag.offsetWidth, h: tag.offsetHeight };
      const { turn, k } = bestPlace(index, size, placed, pad);
      state.tagPlace[index] = { turn, k };
      placeMark(index);
      const spot = tagSpot(index, size, { turn, k });
      placed.push({ rect: tagRect(spot, pad), seg: leaderSegment(index, spot) });
    }
  }

  function drawOverlay(animate) {
    if (!state.plate) return;
    const overlay = $("overlay");
    const { width, height } = state.plate.image;
    overlay.setAttribute("viewBox", `0 0 ${width} ${height}`);
    overlay.setAttribute("aria-label", t("stageTitle"));
    overlay.dataset.grid = state.grid ? "on" : "off";
    overlay.dataset.contours = state.contours ? "on" : "off";
    overlay.replaceChildren();
    drawGraticule(overlay);
    const rim = svg("g");
    drawRim(rim);
    overlay.append(rim);
    const zones = svg("g", { class: animate ? "draw-in" : "" });
    state.order.forEach((index, position) => drawZone(zones, state.plate.disks[index], position, animate));
    const leaders = svg("g", { id: "leaders", class: animate ? "leaders is-entering" : "leaders" });
    overlay.append(zones, leaders);
    drawMarks(animate);
    if (animate) {
      const total = state.order.length * 70 + 900;
      setTimeout(() => {
        zones.classList.remove("draw-in");
        leaders.classList.remove("is-entering");
        for (const node of zones.querySelectorAll("[pathLength]")) node.removeAttribute("pathLength");
        document.querySelector(".marks")?.classList.remove("draw-in-tags");
      }, total);
    }
  }

  function updateZone(index) {
    const disk = state.plate.disks[index];
    const r = radiusPx(index);
    const g = document.querySelector(`.zone[data-index="${index}"]`);
    if (g) {
      g.querySelector(".caliper").setAttribute("r", r);
      g.querySelector(".focus-ring").setAttribute("r", r + disk.disk_radius * 0.35);
      g.classList.toggle("is-corrected", state.overrides[index] !== undefined);
    }
    placeMark(index);
  }

  /* ---------- caliper drag ---------- */

  function svgPoint(clientX, clientY) {
    const overlay = $("overlay");
    const point = overlay.createSVGPoint();
    point.x = clientX;
    point.y = clientY;
    return point.matrixTransform(overlay.getScreenCTM().inverse());
  }

  function setOverride(index, mm) {
    const clamped = Math.min(MAX_MM, Math.max(MIN_MM, Math.round(mm * 10) / 10));
    const measured = state.plate.disks[index].diameter_mm;
    if (Math.abs(clamped - measured) < 0.05) delete state.overrides[index];
    else state.overrides[index] = clamped;
    updateZone(index);
    renderRow(index);
    renderCorrections();
    if (state.selected === index) drawLoupe(index);
  }

  function bindHandle(handle, index) {
    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      select(index);
      handle.setPointerCapture?.(event.pointerId);
      handle.classList.add("is-dragging");
      const [cx, cy] = state.plate.disks[index].center;
      const move = (e) => {
        const p = svgPoint(e.clientX, e.clientY);
        setOverride(index, (2 * Math.hypot(p.x - cx, p.y - cy)) / pxPerMm());
      };
      const up = () => {
        handle.classList.remove("is-dragging");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        classify();
        layoutTags();
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
    handle.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? 1 : 0.1;
      const delta = { ArrowRight: step, ArrowUp: step, ArrowLeft: -step, ArrowDown: -step }[event.key];
      if (delta !== undefined) {
        event.preventDefault();
        setOverride(index, diameterMm(index) + delta);
        clearTimeout(handle.syncTimer);
        handle.syncTimer = setTimeout(() => { classify(); layoutTags(); }, 400);
      } else if (event.key === "Backspace" || event.key === "Delete") {
        restore(index);
      }
    });
    handle.addEventListener("focus", () => select(index, false));
  }

  function restore(index) {
    delete state.overrides[index];
    updateZone(index);
    classify();
    layoutTags();
  }

  /* ---------- selection and loupe ---------- */

  function select(index, scroll = true) {
    state.selected = index;
    for (const g of document.querySelectorAll(".zone")) g.classList.toggle("is-selected", Number(g.dataset.index) === index);
    for (const h of document.querySelectorAll(".handle")) h.classList.toggle("is-visible", Number(h.dataset.index) === index);
    for (const tag of document.querySelectorAll(".tag")) tag.classList.toggle("is-selected", Number(tag.dataset.index) === index);
    for (const row of document.querySelectorAll(".ruler-row")) {
      const on = Number(row.dataset.index) === index;
      row.classList.toggle("is-selected", on);
      if (on && scroll) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
    drawLoupe(index);
  }

  function loupeContour(ctx, disk, map, u) {
    ctx.beginPath();
    disk.contour.forEach((p, i) => { const [a, b] = map(p); if (i) ctx.lineTo(a, b); else ctx.moveTo(a, b); });
    ctx.closePath();
    ctx.strokeStyle = disk.flags.length ? "#b4a259" : "#bdbdb4";
    ctx.lineWidth = 1.25 * u;
    ctx.stroke();
  }

  function loupeScale(ctx, cx, x0, k, u) {
    const { width: W, height: H } = ctx.canvas;
    const base = H * 0.74;
    const ppm = pxPerMm();
    const step = (ppm / 2) * k / u < 5 ? 5 : 1;
    ctx.fillStyle = "rgba(7, 8, 8, 0.72)";
    ctx.fillRect(0, base - 2 * u, W, 22 * u);
    ctx.strokeStyle = "#ece9e1";
    ctx.fillStyle = "#ece9e1";
    ctx.lineWidth = u;
    ctx.font = `${10 * u}px "Atkinson Hyperlegible Mono", ui-monospace, monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const from = Math.max(0, Math.floor((2 * (x0 - cx)) / ppm));
    const to = Math.ceil((2 * (x0 + W / k - cx)) / ppm);
    ctx.beginPath();
    ctx.moveTo(0, base);
    ctx.lineTo(W, base);
    for (let d = from; d <= to; d += 1) {
      if (d % step !== 0) continue;
      const X = (cx + (d / 2) * ppm - x0) * k;
      const major = d % 5 === 0;
      ctx.moveTo(X, base);
      ctx.lineTo(X, base + (major ? 8 : 4) * u);
      if (major) ctx.fillText(String(d), X, base + 9 * u);
    }
    ctx.stroke();
  }

  function drawLoupe(index) {
    const loupe = $("loupe");
    if (index === null || !state.image || !state.plate) { loupe.hidden = true; return; }
    loupe.hidden = false;
    const disk = state.plate.disks[index];
    const canvas = $("loupe-canvas");
    const ctx = canvas.getContext("2d");
    const side = canvas.getBoundingClientRect().width || 112;
    const u = canvas.width / side;
    const r = radiusPx(index);
    const [cx, cy] = disk.center;
    const half = side / 2 / (LOUPE_ZOOM * frameScale());
    const x0 = cx + r - half;
    const k = canvas.width / (2 * half);
    const map = ([px, py]) => [(px - x0) * k, (py - cy + half) * k];
    ctx.fillStyle = "#070808";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(state.image, x0, cy - half, 2 * half, 2 * half, 0, 0, canvas.width, canvas.height);
    if (disk.contour.length && state.contours) loupeContour(ctx, disk, map, u);
    const [mx, my] = map([cx, cy]);
    ctx.beginPath();
    ctx.arc(mx, my, r * k, 0, 2 * Math.PI);
    ctx.strokeStyle = "#ece9e1";
    ctx.lineWidth = 1.75 * u;
    ctx.stroke();
    loupeScale(ctx, cx, x0, k, u);
    const position = state.order.indexOf(index);
    $("loupe-label").replaceChildren(
      html("span", {}, `${t("diskLabel", { pos: position + 1 })} · ${code(state.labels[index], position)}`),
      html("span", {}, `${fmt(diameterMm(index))} mm · ${t("loupeZoom")}`),
    );
  }

  /* ---------- rulers ---------- */

  function segments(bp) {
    if (!bp || bp.S === undefined) return [];
    const r = (bp.R ?? 0) + 0.5;
    const s = bp.S - 0.5;
    const middle = bp.SDD_low !== undefined ? "SDD" : "I";
    return [
      { cat: "R", from: 0, to: r },
      { cat: middle, from: r, to: s },
      { cat: "S", from: s, to: SCALE_MAX_MM },
    ].filter((seg) => seg.to > seg.from);
  }

  function rulerSvg(index) {
    const W = 300;
    const clampMm = (mm) => Math.min(Math.max(mm, 0), SCALE_MAX_MM);
    const x = (mm) => (clampMm(mm) / SCALE_MAX_MM) * W;
    const share = (mm) => `${(clampMm(mm) / SCALE_MAX_MM) * 100}%`;
    const wrap = html("div", { class: "scale-wrap", "aria-hidden": "true" });
    const node = svg("svg", { class: "scale", viewBox: `0 0 ${W} 28`, preserveAspectRatio: "none" });
    const row = state.rows[index];
    const bp = state.labels[index] && row ? row.breakpoints : null;
    const mm = diameterMm(index);
    const lo = mm - NEAR_BREAKPOINT_MM;
    const hi = mm + NEAR_BREAKPOINT_MM;
    node.append(svg("rect", { class: "band", x: x(lo), y: 6, width: x(hi) - x(lo), height: 16 }));
    for (const seg of segments(bp)) {
      const color = `var(--cat-${seg.cat.toLowerCase()})`;
      node.append(svg("rect", { class: "seg", x: x(seg.from), y: 12, width: x(seg.to) - x(seg.from), height: 4, fill: color }));
      wrap.append(html("span", { class: "seg-letter", style: `left:${share((seg.from + seg.to) / 2)};color:${color}` }, seg.cat));
    }
    node.append(svg("rect", { class: "disk-zone", x: 0, y: 12, width: x(DISK_MM), height: 4 }));
    node.append(svg("line", { class: "base", x1: 0, y1: 18, x2: W, y2: 18 }));
    for (let tick = 0; tick <= SCALE_MAX_MM; tick += 1) {
      const five = tick % 5 === 0;
      node.append(svg("line", { class: five ? "mm five" : "mm", x1: x(tick), y1: 18, x2: x(tick), y2: five ? 25 : 21.5 }));
      if (tick % 10 === 0) {
        const edge = tick === 0 ? " first" : tick === SCALE_MAX_MM ? " last" : "";
        wrap.append(html("span", { class: `scale-num${edge}`, style: `left:${share(tick)}` }, String(tick)));
      }
    }
    if (state.overrides[index] !== undefined) {
      const m = state.plate.disks[index].diameter_mm;
      node.append(svg("line", { class: "ghost", x1: x(m), y1: 6, x2: x(m), y2: 26 }));
    }
    node.append(svg("line", { class: "jaw", x1: x(mm), y1: 6, x2: x(mm), y2: 26 }));
    node.append(svg("path", { class: "jaw-head", d: `M ${x(mm) - 4} 0 h 8 l -4 5 z` }));
    wrap.prepend(node);
    return wrap;
  }

  function nearBreakpoint(index) {
    const row = state.rows[index];
    if (!row || !state.labels[index]) return false;
    const mm = diameterMm(index);
    const bp = row.breakpoints;
    const edges = [bp.S - 0.5, (bp.R ?? -99) + 0.5];
    return edges.some((edge) => Math.abs(mm - edge) < NEAR_BREAKPOINT_MM);
  }

  function buildRow(index, position) {
    const disk = state.plate.disks[index];
    const cat = currentCategory(index);
    const li = html("li", { class: `ruler-row${state.selected === index ? " is-selected" : ""}`, "data-index": index });
    li.append(html("span", { class: "pos" }, String(position + 1)));

    const drug = html("div", { class: "drug" });
    drug.append(html("span", { class: "drug-code" }, code(state.labels[index], position)));
    const picker = html("select", { "aria-label": t("diskLabel", { pos: position + 1 }) });
    picker.append(html("option", { value: "" }, t("unassigned")));
    for (const name of state.plate.antibiotics) {
      const option = html("option", { value: name }, drugName(name));
      if (state.labels[index] === name) option.selected = true;
      picker.append(option);
    }
    picker.addEventListener("click", (e) => e.stopPropagation());
    picker.addEventListener("change", () => {
      state.labels[index] = picker.value || null;
      state.sampleLayout = false;
      renderPanelSelect();
      classify().then(layoutTags);
    });
    drug.append(picker);
    if (state.labels[index] && nearBreakpoint(index)) {
      drug.append(html("span", { class: "near", title: t("nearBreakpoint") }, "±2 mm"));
    }
    li.append(drug, rulerSvg(index));

    const read = html("div", { class: "read" });
    const mmNode = html("span", { class: "read-mm" }, fmt(diameterMm(index)));
    mmNode.append(html("small", {}, "mm"));
    read.append(mmNode, html("span", { class: "cat", "data-cat": cat }, cat === "UNKNOWN" ? "–" : cat));
    li.append(read);

    const note = html("div", { class: "note" });
    for (const flag of disk.flags) {
      const f = html("span", { class: "flag" });
      f.append(icon("flag"), document.createTextNode(t(`flag_${flag}`)));
      note.append(f);
    }
    if (!state.labels[index]) note.append(html("span", {}, t("assignFirst")));
    if (state.overrides[index] !== undefined) {
      note.append(html("span", { class: "corrected" }, t("corrected", { mm: fmt(disk.diameter_mm) })));
      const button = html("button", { type: "button", class: "restore" });
      button.append(icon("reset"), document.createTextNode(t("restore")));
      button.addEventListener("click", (e) => { e.stopPropagation(); restore(index); });
      note.append(button);
    }
    li.append(note);
    li.addEventListener("click", () => select(index, false));
    return li;
  }

  function renderRulers() {
    const list = $("ruler-list");
    list.replaceChildren(...state.order.map((index, position) => buildRow(index, position)));
  }

  function renderRow(index) {
    const old = document.querySelector(`.ruler-row[data-index="${index}"]`);
    if (old) old.replaceWith(buildRow(index, state.order.indexOf(index)));
  }

  function renderCorrections() {
    const n = Object.keys(state.overrides).length;
    const note = $("correction-note");
    note.hidden = n === 0;
    note.textContent = n ? t("corrections", { n }) : "";
    $("review-btn").disabled = n > 0;
  }

  /* ---------- panel ---------- */

  function renderPanelSelect() {
    const select = $("panel-select");
    select.replaceChildren();
    if (state.sampleLayout) select.append(html("option", { value: "__sample" }, t("panelSample")));
    select.append(html("option", { value: "" }, t("panelManual")));
    for (const name of state.plate.panels) select.append(html("option", { value: name }, name));
    select.value = state.sampleLayout ? "__sample" : "";
  }

  async function applyPanel(name) {
    if (!name || name === "__sample") return;
    try {
      const result = await api(`/api/plates/${state.plate.analysis_id}/panel`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
      });
      state.labels = result.labels;
      state.sampleLayout = false;
      await classify();
      layoutTags();
      toast(t("panelApplied"));
    } catch (error) {
      toast(t("errorGeneric", { detail: error.message }), true);
      $("panel-select").value = "";
    }
  }

  /* ---------- review ---------- */

  async function runReview() {
    const button = $("review-btn");
    button.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.querySelector("span").textContent = t("reviewing");
    try {
      state.review = await api(`/api/plates/${state.plate.analysis_id}/review`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ organism: $("organism").value.trim() || "Escherichia coli", alerts: $("use-alerts").checked }),
      });
      renderReview();
      $("review").hidden = false;
      $("review").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      toast(t("errorGeneric", { detail: error.message }), true);
    } finally {
      button.removeAttribute("aria-busy");
      button.querySelector("span").textContent = t("reviewBtn");
      renderCorrections();
    }
  }

  function safeUrl(value) {
    try {
      const url = new URL(value);
      return url.protocol === "https:" ? url.href : null;
    } catch { return null; }
  }

  function domainOf(url) {
    return new URL(url).hostname.replace(/^www\./, "");
  }

  function clip(text, max) {
    const loose = /[\s|·,.;:–-]+$/;
    let value = text.replace(/\s*(\.\.\.|…)\s*$/, "");
    const truncated = value !== text || value.length > max;
    if (value.length > max) {
      const cut = value.slice(0, max);
      const space = cut.lastIndexOf(" ");
      value = space > max * 0.6 ? cut.slice(0, space) : cut;
    }
    if (!truncated) return value;
    const words = value.replace(loose, "").split(" ");
    while (words.length > 3 && DANGLING.has(words[words.length - 1].toLowerCase())) words.pop();
    return `${words.join(" ").replace(loose, "")}…`;
  }

  function humanize(text) {
    let value = text;
    try { value = decodeURIComponent(text); } catch { /* keep the raw slug */ }
    value = value.replace(/\.[a-z0-9]{2,5}$/i, "").replace(/[-_+]+/g, " ").replace(/\s+/g, " ").trim();
    value = value.split(" ").map((word) => (ACRONYMS.has(word.toLowerCase()) ? word.toUpperCase() : word)).join(" ");
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function readableTitle(title) {
    const trimmed = (title || "").trim();
    const core = trimmed.replace(/\s*(\.\.\.|…)$/, "");
    if (/\s/.test(core)) return trimmed;
    return `${humanize(core)}${core === trimmed ? "" : "…"}`;
  }

  function citationText(id) {
    const url = safeUrl(id);
    if (!url) return id;
    const alerts = (state.review && state.review.report.public_alerts) || [];
    const alert = alerts.find((a) => a.url === id || a.url === url);
    const tail = new URL(url).pathname.split("/").filter(Boolean).pop() || "";
    const title = alert ? readableTitle(alert.title) : humanize(tail);
    return title ? `${clip(title, 56)} · ${domainOf(url)}` : domainOf(url);
  }

  function dl(target, entries) {
    target.replaceChildren();
    for (const [term, value] of entries) {
      target.append(html("dt", {}, term), html("dd", {}, value));
    }
  }

  function shortDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleDateString(state.lang === "es" ? "es-CO" : "en-US", {
      day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
    });
  }

  function exclusionText(reason) {
    if (!reason) return t("inRules");
    if (reason.startsWith("unresolved")) return t("ex_unresolved");
    if (reason.startsWith("duplicate")) return t("ex_duplicate");
    return t("ex_flags");
  }

  function renderResults(report) {
    const body = $("results").querySelector("tbody");
    const rank = (obs) => state.order.indexOf(obs.disk_index);
    const observations = report.measurement.observations.slice().sort((a, b) => rank(a) - rank(b));
    body.replaceChildren(...observations.map((obs) => {
      const position = rank(obs);
      const known = Boolean(state.labels[obs.disk_index]);
      const tr = html("tr");
      const drugCell = html("td", { class: "drug-cell" });
      drugCell.append(html("span", { class: "code" }, known ? code(obs.antibiotic_code, position) : `#${position + 1}`));
      if (known) drugCell.append(html("span", { class: "name" }, drugName(obs.antibiotic_code)));
      tr.append(html("td", {}, String(position + 1)), drugCell, html("td", { class: "num" }, fmt(obs.zone_mm)));
      const catCell = html("td");
      catCell.append(html("span", { class: "cat", "data-cat": obs.category }, obs.category === "UNKNOWN" ? "–" : obs.category));
      const note = html("td", { class: obs.included_in_rule_evaluation ? "" : "excluded" }, exclusionText(obs.exclusion_reason));
      tr.append(catCell, note);
      return tr;
    }));
  }

  function renderReview() {
    const { status, fallback_reason: reason, report } = state.review;
    $("review-sample").hidden = !state.synthetic;
    const statusNode = $("review-status");
    statusNode.textContent = status === "grounded_report"
      ? t("statusGrounded")
      : t("statusFallback", { reason: t(`fallback_${reason}`) });
    const explanation = $("explanation");
    explanation.textContent = report.model_explanation || "";
    explanation.classList.toggle("is-fallback", !report.model_explanation);
    explanation.hidden = !report.model_explanation;

    renderResults(report);

    const citations = $("citations");
    citations.replaceChildren(...(report.cited_evidence_ids || []).map((id) => (
      html("li", { title: id, class: safeUrl(id) ? "is-source" : "" }, citationText(id))
    )));

    const catalog = report.catalog_status || {};
    dl($("coverage"), [
      ...["intrinsic_resistance", "phenotype", "cascade"].map((k) => [t(`cov_${k}`), t(`catalog_${catalog[k]}`)]),
      [t("cov_esbl"), report.esbl_screen ? report.esbl_screen.status : t("cov_esbl_off")],
      [t("cov_rule_standard"), report.rule_standard || report.measurement.standard],
      [t("cov_alerts"), t(`alert_${report.alert_search_status || "not_requested"}`)],
    ]);

    const alerts = $("alerts");
    alerts.replaceChildren();
    for (const alert of report.public_alerts || []) {
      const li = html("li");
      const url = safeUrl(alert.url);
      const text = clip(readableTitle(alert.title), 110) || (url ? domainOf(url) : "—");
      const title = url ? html("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, text) : html("span", {}, text);
      if (url) title.append(icon("out"));
      const source = alert.source === "ops" && state.lang === "en" ? "PAHO" : alert.source.toUpperCase();
      const when = alert.published_date ? ` · ${shortDate(alert.published_date)}` : "";
      const where = url ? ` · ${domainOf(url)}` : "";
      li.append(title, html("span", { class: "alert-meta" }, `${source}${where}${when}`));
      alerts.append(li);
    }
    if (!alerts.children.length) alerts.append(html("li", { class: "empty-note" }, t("noAlerts")));

    const trace = report.traceability || {};
    dl($("trace"), [
      [t("trace_analysis"), report.analysis_id],
      [t("trace_image"), trace.image_sha256 || "—"],
      [t("trace_commit"), trace.commit_hash || "—"],
      [t("trace_version"), trace.software_version || "—"],
      [t("trace_measurement"), report.measurement.standard],
    ]);
  }

  function download() {
    const reviewer = $("reviewer").value.trim();
    if (!reviewer) { toast(t("needReviewer"), true); $("reviewer").focus(); return; }
    const payload = {
      report: state.review.report,
      antibiotic_assignment: state.order.map((index, position) => ({
        position: position + 1, disk_index: index, antibiotic: state.labels[index],
      })),
      signoff: { reviewer, signed_at: new Date().toISOString(), note: "Human review required; not a medical device." },
      generated_by: "BacterioScope light box",
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const link = html("a", { href: URL.createObjectURL(blob), download: `bacterioscope-${state.review.report.analysis_id}.json` });
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    toast(t("downloaded"));
  }

  /* ---------- wiring ---------- */

  function bindTools() {
    $("toggle-grid").addEventListener("click", (e) => {
      state.grid = !state.grid;
      e.currentTarget.setAttribute("aria-pressed", String(state.grid));
      $("overlay").dataset.grid = state.grid ? "on" : "off";
    });
    $("toggle-contours").addEventListener("click", (e) => {
      state.contours = !state.contours;
      e.currentTarget.setAttribute("aria-pressed", String(state.contours));
      $("overlay").dataset.contours = state.contours ? "on" : "off";
      if (state.selected !== null) drawLoupe(state.selected);
    });
    $("panel-select").addEventListener("change", (e) => applyPanel(e.target.value));
    $("review-btn").addEventListener("click", runReview);
    $("download-btn").addEventListener("click", download);
    for (const button of document.querySelectorAll(".lang button")) {
      button.addEventListener("click", () => setLanguage(button.dataset.lang));
    }
  }

  async function openFromLink(params) {
    const sample = state.samples.find((s) => s.id === params.get("sample"));
    if (!sample) return;
    await analyze({ sampleId: sample.id, imageUrl: sample.image_url });
    if (params.get("review") === "1" && state.plate && !$("review-btn").disabled) await runReview();
  }

  async function init() {
    const params = new URLSearchParams(location.search);
    const saved = params.get("lang") || recall("bs-lang");
    state.lang = saved === "en" || saved === "es" ? saved : (navigator.language || "es").startsWith("en") ? "en" : "es";
    bindIntake();
    bindTools();
    let resizeFrame = 0;
    new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        if (!state.plate || $("plate").hidden) return;
        layoutTags();
        if (state.selected !== null) drawLoupe(state.selected);
      });
    }).observe($("plate-frame"));
    applyLanguage();
    await loadSamples();
    await openFromLink(params);
  }

  init();
})();
