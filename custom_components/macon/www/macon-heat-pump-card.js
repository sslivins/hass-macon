/*
 * Macon heat pump card
 *
 * A live vapour-compression circuit diagram for the `macon` integration.
 * Vanilla custom element - no build step, no external dependencies.
 *
 * The refrigerant ring is drawn in its heating-mode flow direction; when the
 * reversing valve flips, each segment's animation direction and thermodynamic
 * state (hot gas / liquid / two-phase / suction) swap accordingly.
 *
 * Usage:
 *   type: custom:macon-heat-pump-card
 *   device_id: <ha device id>      # optional, auto-detected if only one
 *   demo: true                     # optional, synthetic animated data
 */

const CARD_VERSION = "0.2.5";

/* Macon brand mark, inlined from custom_components/macon/brand/icon.png so the
 * card renders correctly no matter how it is served. */
const MACON_MARK =
  "data:image/png;base64,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";

/* ------------------------------------------------------------------ *
 * Entity resolution
 * ------------------------------------------------------------------ */

// Matched against the tail of the entity_id, so user renames of the device
// prefix (e.g. "office_macon_...") still resolve correctly.
const SENSOR_KEYS = {
  tank: "tank_temperature",
  inlet: "inlet_temperature",
  outlet: "outlet_temperature",
  outdoor: "outdoor_temperature",
  discharge: "discharge_temperature",
  suction: "suction_temperature",
  outdoorCoil: "outdoor_coil_temperature",
  indoorCoil: "indoor_coil_temperature",
  ipm: "ipm_temperature",
  heatingSetpoint: "heating_setpoint",
  coolingSetpoint: "cooling_setpoint",
  hotWaterSetpoint: "hot_water_setpoint",
  operation: "operation",
  mode: "working_mode",
  frequency: "compressor_frequency",
  fanRpm: "fan_speed",
  fanLevel: "fan_level",
  power: "power",
  thermal: "thermal_output",
  cop: "coefficient_of_performance",
  eev: "expansion_valve_position",
  faultCode: "fault_code",
};

const TEXT_KEYS = new Set(["operation", "mode", "faultCode"]);

// Sensor keys whose values are temperatures and therefore need unit
// normalisation. Everything else (Hz, rpm, W, COP) is unit-agnostic.
const TEMP_KEYS = new Set([
  "tank",
  "inlet",
  "outlet",
  "outdoor",
  "discharge",
  "suction",
  "outdoorCoil",
  "indoorCoil",
  "ipm",
  "heatingSetpoint",
  "coolingSetpoint",
  "hotWaterSetpoint",
]);

const BINARY_KEYS = {
  connected: "heat_pump_connected",
  unitOn: "unit_power",
  defrosting: "defrosting",
  fault: "active_error",
  compressor: "compressor",
  fan: "fan",
  waterPump: "water_pump",
  backupHeater: "backup_heater",
  reversing: "reversing_valve_request",
};

function resolveEntities(hass, deviceId) {
  const map = {};
  const registry = hass.entities || {};
  for (const [entityId, entry] of Object.entries(registry)) {
    if (entry.platform !== "macon") continue;
    if (deviceId && entry.device_id !== deviceId) continue;
    const domain = entityId.split(".")[0];
    const table =
      domain === "sensor" ? SENSOR_KEYS : domain === "binary_sensor" ? BINARY_KEYS : null;
    if (!table) continue;
    for (const [key, suffix] of Object.entries(table)) {
      if (map[key]) continue;
      if (entityId.endsWith(`_${suffix}`)) map[key] = entityId;
    }
  }
  return map;
}

function findMaconDevices(hass) {
  const seen = new Set();
  for (const entry of Object.values(hass.entities || {})) {
    if (entry.platform === "macon" && entry.device_id) seen.add(entry.device_id);
  }
  return [...seen];
}

/* ------------------------------------------------------------------ *
 * Value helpers
 * ------------------------------------------------------------------ */

function num(hass, entityId) {
  if (!entityId) return null;
  const st = hass.states[entityId];
  if (!st) return null;
  const v = Number(st.state);
  return Number.isFinite(v) ? v : null;
}

// Entity states arrive already converted to the user's display unit, so a
// temperature may be delivered in F. All internal maths (colour ramp,
// superheat, water delta-T) is defined in C, so normalise on read and convert
// back only when formatting. The per-entity unit attribute is used rather than
// the global unit system because a single entity can be overridden in its
// settings.
function numTemp(hass, entityId) {
  const v = num(hass, entityId);
  if (v === null) return null;
  const st = hass.states[entityId];
  const unit = (st && st.attributes && st.attributes.unit_of_measurement) || "";
  return unit.includes("F") ? ((v - 32) * 5) / 9 : v;
}

function str(hass, entityId) {
  if (!entityId) return null;
  const st = hass.states[entityId];
  if (!st || st.state === "unknown" || st.state === "unavailable") return null;
  return st.state;
}

function bool(hass, entityId) {
  if (!entityId) return null;
  const st = hass.states[entityId];
  if (!st) return null;
  if (st.state === "on") return true;
  if (st.state === "off") return false;
  return null;
}

function isLive(hass, entityId) {
  const st = entityId ? hass.states[entityId] : null;
  return !!st && st.state !== "unavailable";
}

// Cold -> neutral -> hot. Deliberately avoids green/yellow, which read as
// status colours rather than temperature.
const TEMP_STOPS = [
  [-10, [30, 136, 229]],
  [25, [120, 144, 156]],
  [80, [229, 57, 53]],
];

function tempColor(c) {
  if (c === null || c === undefined) return "var(--disabled-text-color, #888)";
  const s = TEMP_STOPS;
  if (c <= s[0][0]) return `rgb(${s[0][1].join(",")})`;
  if (c >= s[s.length - 1][0]) return `rgb(${s[s.length - 1][1].join(",")})`;
  for (let i = 0; i < s.length - 1; i++) {
    const [x0, c0] = s[i];
    const [x1, c1] = s[i + 1];
    if (c >= x0 && c <= x1) {
      const t = (c - x0) / (x1 - x0);
      return `rgb(${c0.map((v, j) => Math.round(v + (c1[j] - v) * t)).join(",")})`;
    }
  }
  return "var(--primary-text-color)";
}

function fmtTemp(c, unit) {
  if (c === null || c === undefined) return "--";
  const v = unit === "F" ? (c * 9) / 5 + 32 : c;
  return `${v.toFixed(1)}\u00b0`;
}

// Temperature *differences* convert without the 32 offset.
function fmtDelta(k, unit) {
  if (k === null || k === undefined) return "--";
  const v = unit === "F" ? (k * 9) / 5 : k;
  return `${v.toFixed(1)} ${unit === "F" ? "\u0394\u00b0F" : "K"}`;
}

function fmtPower(w) {
  if (w === null || w === undefined) return "--";
  return Math.abs(w) >= 1000 ? `${(w / 1000).toFixed(2)} kW` : `${w.toFixed(0)} W`;
}

function titleCase(s) {
  if (!s) return "--";
  return s.replace(/_/g, " ").replace(/\b\w/g, (m) => m.toUpperCase());
}

function modeOf(values, flags) {
  const op = (values.operation || "").toLowerCase();
  const wm = (values.mode || "").toLowerCase();
  if (op === "defrost" || flags.defrosting) return "defrost";
  if (op === "cooling" || wm === "cooling") return "cool";
  if (wm === "hot_water") return "dhw";
  if (op === "heating" || wm.includes("heat")) return "heat";
  if (op === "fault") return "fault";
  return "idle";
}

const MODE_LABEL = {
  heat: "Heating",
  cool: "Cooling",
  dhw: "Hot water",
  defrost: "Defrosting",
  fault: "Fault",
  idle: "Idle",
};

const MODE_ICON = {
  heat: "mdi:fire",
  cool: "mdi:snowflake",
  dhw: "mdi:water-boiler",
  defrost: "mdi:snowflake-melt",
  fault: "mdi:alert",
  idle: "mdi:power-standby",
};

/* ------------------------------------------------------------------ *
 * Demo data
 * ------------------------------------------------------------------ */

function demoState(tick) {
  const w = (period, lo, hi, phase = 0) => {
    const t = (Math.sin((tick / period) * Math.PI * 2 + phase) + 1) / 2;
    return lo + (hi - lo) * t;
  };
  // Cycle heating -> defrost -> cooling so both valve positions are visible.
  const phase = tick % 180;
  const cooling = phase >= 100 && phase < 170;
  const defrosting = phase >= 80 && phase < 100;
  // Defrost is a reverse-cycle run: the compressor works hard while the
  // outdoor fan is stopped, and no useful heat reaches the water.
  const running = true;

  const inlet = cooling ? w(60, 18, 21) : w(60, 32, 36);
  // During defrost the plate HX is the evaporator, so the water leaves colder
  // than it arrived - the same sign as cooling.
  const outlet =
    inlet + (cooling || defrosting ? -w(37, 3.4, 5.0, 1.1) : w(37, 4.2, 6.4, 1.1));

  return {
    values: {
      tank: cooling ? w(90, 20, 24) : w(90, 46, 50),
      inlet,
      outlet,
      outdoor: cooling ? w(160, 26, 32) : w(160, 2, 7),
      discharge: defrosting ? w(20, 45, 55) : cooling ? w(43, 62, 72) : w(43, 72, 84),
      // Suction must sit a few K above the evaporating coil, otherwise the
      // derived superheat would be negative (liquid returning to the
      // compressor), which a healthy unit never does.
      suction: defrosting ? w(20, 26, 32) : cooling ? w(51, 14, 18) : w(51, 4, 9),
      outdoorCoil: defrosting ? w(20, 8, 14) : cooling ? w(47, 38, 46) : w(47, -4, 2),
      indoorCoil: defrosting ? w(55, 20, 26) : cooling ? w(55, 8, 12) : w(55, 38, 44),
      ipm: w(70, 40, 52),
      heatingSetpoint: 40,
      coolingSetpoint: 18,
      hotWaterSetpoint: 50,
      frequency: defrosting ? w(20, 50, 60) : w(35, 42, 62),
      fanRpm: defrosting ? 0 : w(35, 520, 700),
      power: defrosting ? w(20, 1400, 1800) : w(35, 900, 1450),
      thermal: defrosting ? 0 : w(35, 3600, 5400),
      cop: defrosting ? 0 : w(35, 3.6, 4.6),
      // Valve opens wide during defrost to flood the outdoor coil, and modulates
      // around a narrower band in steady-state operation.
      eev: defrosting ? w(20, 400, 460) : w(40, 180, 280),
      operation: defrosting ? "defrost" : cooling ? "cooling" : "heating",
      mode: cooling ? "cooling" : "heating",
      faultCode: "ok",
    },
    flags: {
      connected: true,
      unitOn: true,
      compressor: running,
      fan: !defrosting,
      waterPump: true,
      defrosting,
      backupHeater: false,
      reversing: cooling,
      fault: false,
    },
    live: true,
  };
}

/* ------------------------------------------------------------------ *
 * Card
 * ------------------------------------------------------------------ */

class MaconHeatPumpCard extends HTMLElement {
  static getStubConfig(hass) {
    const devices = findMaconDevices(hass);
    return devices.length ? { device_id: devices[0] } : {};
  }

  constructor() {
    super();
    this._built = false;
    this._demoTick = 0;
    this._demoTimer = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._entities = null;
    this._built = false;
    this.innerHTML = "";
    if (this._config.demo) this._startDemo();
    else this._stopDemo();
  }

  disconnectedCallback() {
    this._stopDemo();
  }

  _startDemo() {
    if (this._demoTimer) return;
    this._demoTimer = setInterval(() => {
      this._demoTick += 1;
      this._update();
    }, 1000);
  }

  _stopDemo() {
    if (this._demoTimer) clearInterval(this._demoTimer);
    this._demoTimer = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._entities || Object.keys(this._entities).length === 0) {
      this._entities = resolveEntities(
        hass,
        this._config.device_id || this._autoDevice(hass)
      );
    }
    if (!this._built) this._build();
    this._update();
  }

  _autoDevice(hass) {
    const devices = findMaconDevices(hass);
    return devices.length === 1 ? devices[0] : null;
  }

  getCardSize() {
    return 9;
  }

  /* ---------------- data ---------------- */

  _readState() {
    if (this._config.demo) return demoState(this._demoTick);
    const hass = this._hass;
    const e = this._entities || {};
    const values = {};
    for (const key of Object.keys(SENSOR_KEYS)) {
      const id = e[key];
      values[key] = TEXT_KEYS.has(key)
        ? str(hass, id)
        : TEMP_KEYS.has(key)
          ? numTemp(hass, id)
          : num(hass, id);
    }
    const flags = {};
    for (const key of Object.keys(BINARY_KEYS)) flags[key] = bool(hass, e[key]);
    const live = Object.values(e).some((id) => isLive(hass, id));
    return { values, flags, live };
  }

  _tempUnit() {
    const sys = this._hass && this._hass.config && this._hass.config.unit_system;
    return sys && sys.temperature && sys.temperature.includes("F") ? "F" : "C";
  }

  /* ---------------- DOM ---------------- */

  _build() {
    this.innerHTML = `
      <ha-card>
        <style>${STYLES}</style>
        <div class="hdr">
          <div class="title">
            <img class="brand" src="${MACON_MARK}" alt="Macon" />
            <span id="title-text">${this._config.title || "Heat pump"}</span>
            <span class="uom-hdr" id="uom">\u00b0C</span>
          </div>
          <div class="badges" id="badges"></div>
          <span class="chip" id="mode-chip" data-entity-key="operation"></span>
        </div>
        <div class="offline" id="offline">Waiting for controller data...</div>
        <div class="body">
          ${SCHEMATIC}
          <div class="legend">
            <span><i class="sw hot"></i>Hot gas</span>
            <span><i class="sw liquid"></i>Liquid</span>
            <span><i class="sw twophase"></i>Two-phase</span>
            <span><i class="sw suction"></i>Suction</span>
          </div>
          <div class="stats" id="stats"></div>
        </div>
      </ha-card>`;
    this._built = true;

    // Delegated so elements rendered later (stats, badges) are clickable too.
    this.addEventListener("click", (ev) => {
      const target = ev.target.closest && ev.target.closest("[data-entity-key]");
      if (!target || !this.contains(target)) return;
      const entityId = (this._entities || {})[target.getAttribute("data-entity-key")];
      if (!entityId) return;
      ev.stopPropagation();
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId },
          bubbles: true,
          composed: true,
        })
      );
    });
  }

  _setText(id, text) {
    const el = this.querySelector(`#${id}`);
    if (el && el.textContent !== text) el.textContent = text;
  }

  _setTemp(id, value) {
    this._setText(id, fmtTemp(value, this._tempUnit()));
    const node = this.querySelector(`#${id}`);
    if (node) node.style.fill = tempColor(value);
  }

  _update() {
    if (!this._built || !this._hass) return;
    const { values: v, flags: f, live } = this._readState();
    const unit = this._tempUnit();
    const mode = live ? modeOf(v, f) : "idle";
    // Defrost runs the cycle backwards, same as cooling.
    const heating = mode === "heat" || mode === "dhw";

    this.querySelector("#offline").style.display = live ? "none" : "block";
    this.querySelector(".body").style.opacity = live ? "1" : "0.35";
    this.querySelector("ha-card").className = `mode-${mode}${live ? "" : " offline-state"}`;
    this._setText("uom", unit === "F" ? "\u00b0F" : "\u00b0C");

    const chip = this.querySelector("#mode-chip");
    const chipHtml = `<ha-icon icon="${MODE_ICON[mode]}"></ha-icon>${
      live ? MODE_LABEL[mode] : "No data"
    }`;
    if (chip.innerHTML !== chipHtml) chip.innerHTML = chipHtml;

    // Temperatures on the diagram
    this._setTemp("t-outdoor-coil", v.outdoorCoil);
    this._setTemp("t-outdoor", v.outdoor);
    this._setTemp("t-hx", v.indoorCoil);
    this._setTemp("t-discharge", v.discharge);
    this._setTemp("t-suction", v.suction);
    this._setTemp("t-inlet", v.inlet);
    this._setTemp("t-outlet", v.outlet);
    this._setTemp("t-tank", v.tank);

    // Each exchanger swaps role with the reversing valve.
    this._setText("role-outdoor", heating ? "Evaporator" : "Condenser");
    this._setText("role-hx", heating ? "Condenser" : "Evaporator");

    this._setText("c-freq", v.frequency === null ? "-- Hz" : `${v.frequency.toFixed(0)} Hz`);
    this._setText("c-fan", v.fanRpm === null ? "-- rpm" : `${v.fanRpm.toFixed(0)} rpm`);
    // Reported in valve steps. The controller does not publish the valve's
    // full-scale step count, so this cannot honestly be shown as a percentage
    // or a fill level - the raw step count is all we can stand behind.
    this._setText("c-eev", v.eev === null ? "--" : `${v.eev.toFixed(0)} steps`);

    // Water-side delta across the plate heat exchanger.
    const dt = v.inlet !== null && v.outlet !== null ? v.outlet - v.inlet : null;
    this._setText("t-delta", `\u0394T ${fmtDelta(dt, unit)}`);

    // Approximate superheat: suction minus the *evaporating* coil temperature.
    // Without a suction pressure transducer this is the standard coil-thermistor
    // approximation, not true superheat. It is only meaningful while the
    // compressor is circulating refrigerant, so it is suppressed otherwise.
    const evapCoil = heating ? v.outdoorCoil : v.indoorCoil;
    const sh =
      f.compressor && v.suction !== null && evapCoil !== null
        ? v.suction - evapCoil
        : null;
    this._setText("t-sh", sh === null ? "SH ~ --" : `SH ~ ${fmtDelta(sh, unit)}`);

    // Valve position
    this.querySelector("#valve-heat").style.display = heating ? "" : "none";
    this.querySelector("#valve-cool").style.display = heating ? "none" : "";

    // Component activity
    this.querySelector("#fan-blades").classList.toggle("spin", !!f.fan);
    this.querySelector("#compressor-body").classList.toggle("active", !!f.compressor);
    this.querySelector("#pump-body").classList.toggle("active", !!f.waterPump);
    this.querySelector("#frost").style.opacity = f.defrosting ? "0.55" : "0";

    // Flow segments. Paths are drawn in the heating direction, so cooling and
    // defrost simply run the animation in reverse. The compressor's own two
    // legs never reverse - the valve reroutes the loop, not the compressor.
    const running = !!f.compressor;
    const segments = {
      "f-discharge": ["hot", true],
      "f-suction": ["suction", true],
      "f-top-right": [heating ? "hot" : "suction", heating],
      "f-top-left": [heating ? "suction" : "hot", heating],
      "f-liq-right": [heating ? "liquid" : "twophase", heating],
      "f-liq-left": [heating ? "twophase" : "liquid", heating],
      "f-hx-ref": [heating ? "hot" : "suction", heating],
    };
    for (const [id, [state, forward]] of Object.entries(segments)) {
      this._setFlow(id, running, state, forward, v.frequency);
    }
    const pumping = !!f.waterPump;
    for (const id of ["f-water-out", "f-water-ret", "f-hx-water"]) {
      this._setFlow(id, pumping, "water", true, 40);
    }

    // Badges for genuine exceptions only; the chip carries normal state.
    const badges = [];
    if (live) {
      if (f.fault) badges.push(["fault", "mdi:alert", titleCase(v.faultCode || "fault"), "faultCode"]);
      if (f.backupHeater) badges.push(["aux", "mdi:radiator", "Backup heat", "backupHeater"]);
      if (f.connected === false) badges.push(["fault", "mdi:lan-disconnect", "Pump offline", "connected"]);
      if (f.unitOn === false) badges.push(["idle", "mdi:power-standby", "Off", "unitOn"]);
    }
    const badgeHtml = badges
      .map(
        ([cls, icon, label, key]) =>
          `<span class="badge ${cls}" data-entity-key="${key}"><ha-icon icon="${icon}"></ha-icon>${label}</span>`
      )
      .join("");
    const badgeEl = this.querySelector("#badges");
    if (badgeEl.innerHTML !== badgeHtml) badgeEl.innerHTML = badgeHtml;

    // Water dT and superheat are derived from other readings, so they have no
    // entity of their own and are deliberately not clickable.
    const stats = [
      ["Power in", fmtPower(v.power), "power"],
      ["Heat out", fmtPower(v.thermal), "thermal"],
      ["COP", v.cop === null ? "--" : v.cop.toFixed(2), "cop"],
      ["Water \u0394T", fmtDelta(dt, unit), null],
      ["Superheat", sh === null ? "--" : `~${fmtDelta(sh, unit)}`, null],
      ["IPM", fmtTemp(v.ipm, unit), "ipm"],
    ];
    const statHtml = stats
      .map(
        ([label, value, key]) =>
          `<div class="stat"${key ? ` data-entity-key="${key}"` : ""}>` +
          `<span class="k">${label}</span><span class="v">${value}</span></div>`
      )
      .join("");
    const statEl = this.querySelector("#stats");
    if (statEl.innerHTML !== statHtml) statEl.innerHTML = statHtml;
  }

  _setFlow(id, running, state, forward, rate) {
    const el = this.querySelector(`#${id}`);
    if (!el) return;
    el.setAttribute("class", `pipe-flow st-${state}${running ? " flowing" : ""}`);
    const speed = running ? Math.max(0.5, 3.2 - (rate || 40) / 30) : 0;
    el.style.animationDuration = running ? `${speed.toFixed(2)}s` : "0s";
    el.style.animationDirection = forward ? "normal" : "reverse";
  }
}

/* ------------------------------------------------------------------ *
 * Markup
 * ------------------------------------------------------------------ */

const SCHEMATIC = `
<svg viewBox="0 0 640 360" class="schem" preserveAspectRatio="xMidYMid meet">
  <!-- ============ static pipe bodies (flow dashes are drawn over these) === -->
  <path d="M270,178 V82" class="pipe"/>
  <path d="M220,82 V178" class="pipe"/>
  <path d="M290,60 H420 V103" class="pipe"/>
  <path d="M60,88 V57 H200" class="pipe"/>
  <path d="M420,217 V300 H257" class="pipe"/>
  <path d="M233,300 H60 V270" class="pipe"/>
  <path d="M470,103 V70 H600 V150" class="pipe"/>
  <path d="M600,200 V265 H470 V217" class="pipe"/>
  <path d="M420,103 V217" class="pipe thin"/>
  <path d="M470,217 V103" class="pipe thin"/>

  <!-- ============ outdoor coil ============ -->
  <g data-entity-key="outdoorCoil" class="hit">
    <text x="154" y="80" class="lbl" text-anchor="end">Outdoor unit</text>
    <rect x="26" y="88" width="128" height="182" rx="10" class="unitbox"/>
    <path d="M40 104 h100 M40 118 h100 M40 132 h100" class="coil"/>
    <rect id="frost" x="34" y="96" width="112" height="44" rx="6" class="frost"/>
    <text id="t-outdoor-coil" x="90" y="162" class="val" text-anchor="middle">--</text>
    <text id="role-outdoor" x="90" y="180" class="role" text-anchor="middle">Evaporator</text>
  </g>

  <g transform="translate(90,222)" data-entity-key="fan" class="hit">
    <circle r="26" class="fan-ring"/>
    <g id="fan-blades">
      <path d="M0,-21 C9,-10 9,-3 0,0 C-9,-3 -9,-10 0,-21Z" class="blade"/>
      <path d="M0,-21 C9,-10 9,-3 0,0 C-9,-3 -9,-10 0,-21Z" class="blade" transform="rotate(120)"/>
      <path d="M0,-21 C9,-10 9,-3 0,0 C-9,-3 -9,-10 0,-21Z" class="blade" transform="rotate(240)"/>
    </g>
    <g data-entity-key="fanRpm" class="hit">
      <text y="41" class="lbl" text-anchor="middle" id="c-fan">-- rpm</text>
    </g>
  </g>

  <g data-entity-key="outdoor" class="hit">
    <text x="16" y="340" class="lbl">Ambient</text>
    <text id="t-outdoor" x="164" y="340" class="val sm" text-anchor="end">--</text>
  </g>

  <!-- ============ 4-way reversing valve ============ -->
  <g data-entity-key="reversing" class="hit">
    <text x="245" y="32" class="lbl" text-anchor="middle">4-way valve</text>
    <rect x="200" y="40" width="90" height="40" rx="6" class="valve"/>
    <g id="valve-heat">
      <path d="M270,76 C270,64 280,60 290,60" class="valve-port"/>
      <path d="M220,76 C220,64 210,60 200,60" class="valve-port"/>
    </g>
    <g id="valve-cool" style="display:none">
      <path d="M270,76 C270,62 235,60 200,60" class="valve-port"/>
      <path d="M220,76 C220,62 255,60 290,60" class="valve-port"/>
    </g>
  </g>

  <!-- discharge / suction annotations -->
  <g data-entity-key="discharge" class="hit">
    <text x="281" y="120" class="lbl">Discharge</text>
    <text id="t-discharge" x="281" y="136" class="val sm">--</text>
  </g>
  <g data-entity-key="suction" class="hit">
    <text x="209" y="120" class="lbl" text-anchor="end">Suction</text>
    <text id="t-suction" x="209" y="136" class="val sm" text-anchor="end">--</text>
  </g>
  <text id="t-sh" x="209" y="154" class="delta" text-anchor="end">SH ~ --</text>

  <!-- ============ compressor ============ -->
  <g data-entity-key="frequency" class="hit">
    <circle id="compressor-body" cx="245" cy="197" r="32" class="comp"/>
    <path d="M233,203 A12,12 0 1 1 257,191" class="comp-swirl"/>
    <text x="245" y="248" class="lbl" text-anchor="middle">Compressor</text>
    <text x="245" y="262" class="val sm" text-anchor="middle" id="c-freq">-- Hz</text>
  </g>

  <!-- ============ EEV ============ -->
  <g data-entity-key="eev" class="hit">
    <path d="M245,288 L257,300 L245,312 L233,300 Z" class="eev"/>
    <text x="245" y="328" class="lbl" text-anchor="middle">EEV</text>
    <text x="245" y="342" class="val sm" text-anchor="middle" id="c-eev">--</text>
  </g>

  <!-- ============ plate heat exchanger ============ -->
  <g data-entity-key="indoorCoil" class="hit">
    <text x="490" y="88" class="lbl" text-anchor="end">Plate HX</text>
    <rect x="400" y="95" width="90" height="130" rx="8" class="unitbox"/>
    <text id="t-hx" x="445" y="165" class="val" text-anchor="middle">--</text>
    <text id="role-hx" x="445" y="189" class="role" text-anchor="middle">Condenser</text>
  </g>

  <!-- ============ water side ============ -->
  <g data-entity-key="outlet" class="hit">
    <text x="478" y="52" class="lbl">Outlet</text>
    <text id="t-outlet" x="600" y="52" class="val sm" text-anchor="end">--</text>
  </g>
  <g data-entity-key="inlet" class="hit">
    <text x="478" y="294" class="lbl">Inlet</text>
    <text id="t-inlet" x="620" y="294" class="val sm" text-anchor="end">--</text>
  </g>
  <text id="t-delta" x="600" y="316" class="delta" text-anchor="middle">\u0394T --</text>

  <g data-entity-key="tank" class="hit">
    <rect x="540" y="150" width="92" height="50" rx="6" class="unitbox"/>
    <text x="548" y="168" class="lbl">Tank</text>
    <text id="t-tank" x="624" y="188" class="val" text-anchor="end">--</text>
  </g>

  <g transform="translate(540,265)" data-entity-key="waterPump" class="hit">
    <circle id="pump-body" r="17" class="pump"/>
    <path d="M-6,-6 L7,0 L-6,6 Z" class="pump-tri"/>
    <text x="0" y="-25" class="lbl" text-anchor="middle">Pump</text>
  </g>

  <!-- ============ animated flow overlays ============ -->
  <path id="f-discharge" d="M270,178 V82" class="pipe-flow st-hot"/>
  <path id="f-suction"   d="M220,82 V178" class="pipe-flow st-suction"/>
  <path id="f-top-right" d="M290,60 H420 V103" class="pipe-flow st-hot"/>
  <path id="f-top-left"  d="M60,88 V57 H200" class="pipe-flow st-suction"/>
  <path id="f-liq-right" d="M420,217 V300 H257" class="pipe-flow st-liquid"/>
  <path id="f-liq-left"  d="M233,300 H60 V270" class="pipe-flow st-twophase"/>
  <path id="f-hx-ref"    d="M420,103 V217" class="pipe-flow st-hot"/>
  <path id="f-hx-water"  d="M470,217 V103" class="pipe-flow st-water"/>
  <path id="f-water-out" d="M470,103 V70 H600 V150" class="pipe-flow st-water"/>
  <path id="f-water-ret" d="M600,200 V265 H470 V217" class="pipe-flow st-water"/>
</svg>
`;

const STYLES = `
  macon-heat-pump-card ha-card {
    --hot: #e53935;
    --liquid: #fb8c00;
    --twophase: #4dd0e1;
    --suction: #1e88e5;
    --water: #26a69a;
    --accent: var(--hot);
    padding: 16px;
    overflow: hidden;
  }
  macon-heat-pump-card ha-card.mode-cool { --accent: var(--suction); }
  macon-heat-pump-card ha-card.mode-defrost { --accent: #7e57c2; }
  macon-heat-pump-card ha-card.mode-dhw { --accent: #fb8c00; }
  macon-heat-pump-card ha-card.mode-idle,
  macon-heat-pump-card ha-card.mode-off { --accent: var(--secondary-text-color); }

  macon-heat-pump-card .hdr {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 4px;
  }
  macon-heat-pump-card .title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 1.15rem;
    font-weight: 500;
    color: var(--primary-text-color);
    flex: 1 1 auto;
    min-width: 0;
  }
  macon-heat-pump-card .title .brand {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    flex: 0 0 auto;
    display: block;
  }
  macon-heat-pump-card #title-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  macon-heat-pump-card .uom-hdr {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--secondary-text-color);
    border: 1px solid var(--divider-color);
    border-radius: 10px;
    padding: 1px 7px;
    flex: 0 0 auto;
  }

  macon-heat-pump-card .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.2px;
    color: #fff;
    background: var(--accent);
    white-space: nowrap;
  }
  macon-heat-pump-card .chip ha-icon { --mdc-icon-size: 16px; }

  macon-heat-pump-card .badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  macon-heat-pump-card .badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 600;
    background: var(--secondary-background-color);
    color: var(--secondary-text-color);
  }
  macon-heat-pump-card .badge ha-icon { --mdc-icon-size: 14px; }
  macon-heat-pump-card .badge.fault { background: #e53935; color: #fff; }
  macon-heat-pump-card .badge.aux { background: #fb8c00; color: #fff; }

  macon-heat-pump-card .offline {
    display: none;
    margin: 8px 0 0;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 0.82rem;
    background: var(--secondary-background-color);
    color: var(--secondary-text-color);
  }
  macon-heat-pump-card ha-card.offline-state .offline { display: block; }
  macon-heat-pump-card ha-card.offline-state .schem { opacity: 0.45; }

  macon-heat-pump-card .schem {
    width: 100%;
    height: auto;
    display: block;
    margin: 4px 0 2px;
    overflow: visible;
  }

  /* ---- schematic primitives ---- */
  macon-heat-pump-card .pipe {
    fill: none;
    stroke: var(--divider-color, #d0d0d0);
    stroke-width: 6;
    stroke-linecap: round;
    stroke-linejoin: round;
    opacity: 0.55;
  }
  macon-heat-pump-card .pipe.thin { stroke-width: 5; }

  macon-heat-pump-card .unitbox {
    fill: var(--secondary-background-color, #f2f3f5);
    stroke: var(--divider-color, #d0d0d0);
    stroke-width: 1.5;
  }
  macon-heat-pump-card .coil {
    fill: none;
    stroke: var(--divider-color, #c4c4c4);
    stroke-width: 3;
    stroke-linecap: round;
  }
  macon-heat-pump-card .frost {
    fill: #4dd0e1;
    opacity: 0;
    transition: opacity 0.5s ease;
    pointer-events: none;
  }

  macon-heat-pump-card .lbl {
    font-size: 10px;
    fill: var(--secondary-text-color);
  }
  macon-heat-pump-card .role {
    font-size: 9.5px;
    font-style: italic;
    fill: var(--secondary-text-color);
    opacity: 0.85;
  }
  macon-heat-pump-card .val {
    font-size: 16px;
    font-weight: 600;
    fill: var(--primary-text-color);
  }
  macon-heat-pump-card .val.sm { font-size: 13px; }
  macon-heat-pump-card .delta {
    font-size: 11px;
    font-weight: 600;
    fill: var(--secondary-text-color);
  }

  macon-heat-pump-card .fan-ring {
    fill: var(--card-background-color, #fff);
    stroke: var(--divider-color, #d0d0d0);
    stroke-width: 1.5;
  }
  macon-heat-pump-card .blade { fill: var(--secondary-text-color); opacity: 0.75; }
  macon-heat-pump-card #fan-blades { transform-origin: 0 0; }
  macon-heat-pump-card #fan-blades.spin { animation: macon-spin 1.6s linear infinite; }
  @keyframes macon-spin { to { transform: rotate(360deg); } }

  macon-heat-pump-card .valve {
    fill: var(--card-background-color, #fff);
    stroke: var(--divider-color, #b0b0b0);
    stroke-width: 1.5;
  }
  macon-heat-pump-card .valve-port {
    fill: none;
    stroke: var(--primary-text-color);
    stroke-width: 3.5;
    stroke-linecap: round;
    opacity: 0.75;
  }

  macon-heat-pump-card .comp {
    fill: var(--card-background-color, #fff);
    stroke: var(--divider-color, #b0b0b0);
    stroke-width: 2;
    transition: stroke 0.3s ease;
  }
  macon-heat-pump-card .comp.active { stroke: var(--accent); stroke-width: 3; }
  macon-heat-pump-card .comp-swirl {
    fill: none;
    stroke: var(--secondary-text-color);
    stroke-width: 3;
    stroke-linecap: round;
    opacity: 0.7;
  }

  macon-heat-pump-card .eev {
    fill: var(--card-background-color, #fff);
    stroke: var(--liquid);
    stroke-width: 2.5;
  }

  macon-heat-pump-card .pump {
    fill: var(--card-background-color, #fff);
    stroke: var(--divider-color, #b0b0b0);
    stroke-width: 2;
    transition: stroke 0.3s ease;
  }
  macon-heat-pump-card .pump.active { stroke: var(--water); stroke-width: 3; }
  macon-heat-pump-card .pump-tri { fill: var(--secondary-text-color); }

  macon-heat-pump-card .hit { cursor: pointer; }
  macon-heat-pump-card .hit:hover .val { text-decoration: underline; }
  macon-heat-pump-card .hit:hover .lbl { text-decoration: underline; }
  macon-heat-pump-card .stat[data-entity-key],
  macon-heat-pump-card .badge[data-entity-key],
  macon-heat-pump-card .chip[data-entity-key] { cursor: pointer; }
  macon-heat-pump-card .stat[data-entity-key]:hover .v { text-decoration: underline; }

  /* ---- animated flow ---- */
  macon-heat-pump-card .pipe-flow {
    fill: none;
    stroke-width: 4;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 9 11;
    opacity: 0.25;
    transition: stroke 0.4s ease, opacity 0.4s ease;
  }
  macon-heat-pump-card .pipe-flow.flowing {
    opacity: 1;
    animation-name: macon-flow;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
  }
  @keyframes macon-flow { to { stroke-dashoffset: -20; } }

  macon-heat-pump-card .st-hot { stroke: var(--hot); }
  macon-heat-pump-card .st-liquid { stroke: var(--liquid); }
  macon-heat-pump-card .st-twophase { stroke: var(--twophase); }
  macon-heat-pump-card .st-suction { stroke: var(--suction); }
  macon-heat-pump-card .st-water { stroke: var(--water); }

  /* ---- legend ---- */
  macon-heat-pump-card .legend {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px 18px;
    margin: 6px 0 2px;
    font-size: 0.76rem;
    color: var(--secondary-text-color);
  }
  macon-heat-pump-card .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  macon-heat-pump-card .legend .sw {
    width: 16px;
    height: 4px;
    border-radius: 2px;
    display: inline-block;
  }
  macon-heat-pump-card .legend .sw.hot { background: var(--hot); }
  macon-heat-pump-card .legend .sw.liquid { background: var(--liquid); }
  macon-heat-pump-card .legend .sw.twophase { background: var(--twophase); }
  macon-heat-pump-card .legend .sw.suction { background: var(--suction); }

  /* ---- stats ---- */
  macon-heat-pump-card .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px 6px;
    margin-top: 10px;
    padding-top: 12px;
    border-top: 1px solid var(--divider-color);
  }
  macon-heat-pump-card .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    cursor: pointer;
    min-width: 0;
  }
  macon-heat-pump-card .stat .k {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--secondary-text-color);
    text-align: center;
  }
  macon-heat-pump-card .stat .v {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--primary-text-color);
    white-space: nowrap;
  }
  macon-heat-pump-card .stat:hover .v { text-decoration: underline; }

  @media (max-width: 420px) {
    macon-heat-pump-card .stats { grid-template-columns: repeat(2, 1fr); }
  }
`;


// Home Assistant swaps window.customElements for a scoped-registry shim while
// the frontend boots. This module is injected via extra_module_url so it runs
// first: our definition lands on the native registry and the shim never sees
// it, making every card fail with "Custom element doesn't exist". Re-register
// against whatever registry is current until the frontend has settled.
const CARD_TAG = "macon-heat-pump-card";
let definedRegistry = null;

function defineMaconCard() {
  const registry = window.customElements;
  if (!registry || definedRegistry === registry) return;
  definedRegistry = registry;
  try {
    if (!registry.get(CARD_TAG)) registry.define(CARD_TAG, MaconHeatPumpCard);
  } catch (err) {
    // Another copy of the card already claimed the tag on this registry.
  }
}

defineMaconCard();
const maconDefineTimer = setInterval(defineMaconCard, 200);
setTimeout(() => clearInterval(maconDefineTimer), 60000);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === CARD_TAG)) {
  window.customCards.push({
    type: "macon-heat-pump-card",
    name: "Macon Heat Pump",
    description: "Live vapour-compression circuit diagram for a Macon heat pump controller.",
    preview: true,
  });
}

console.info(
  `%c MACON-HEAT-PUMP-CARD %c ${CARD_VERSION} `,
  "background:#0288d1;color:#fff;border-radius:3px 0 0 3px",
  "background:#455a64;color:#fff;border-radius:0 3px 3px 0"
);
