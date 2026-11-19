const statusList = document.querySelector("#status");
const statusNote = document.querySelector("#status-note");
const devicesEl = document.querySelector("#devices");
const detail = document.querySelector("#detail");
const refresh = document.querySelector("#refresh");
const screenNote = document.querySelector("#screen-note");
const showScreen = document.querySelector("#show-screen");
const screenView = document.querySelector("#screen-view");
const phoneShell = document.querySelector("#phone-shell");
const placeholderHint = document.querySelector("#placeholder-hint");
const pillConnection = document.querySelector("#pill-connection");
const pillDevice = document.querySelector("#pill-device");
const toggleGuide = document.querySelector("#toggle-guide");
const runGuide = document.querySelector("#run-guide");
const workspace = document.querySelector("#workspace");
const remotePanel = document.querySelector("#remote-panel");
const restartScreen = document.querySelector("#restart-screen");
const phoneScreen = document.querySelector("#phone-screen");
const kbToggle = document.querySelector("#kb-toggle");
const wifiState = document.querySelector("#wifi-state");
const wifiPair = document.querySelector("#wifi-pair");
const MIRROR_PAGE = "/mirror.html";
const MIRROR_API = "/mirror";

function mirrorPageUrl(screen) {
  const params = new URLSearchParams();
  if (screen?.iosMajor != null && screen.iosMajor !== "") {
    params.set("iosMajor", String(screen.iosMajor));
  }
  const qs = params.toString();
  return qs ? `${MIRROR_PAGE}?${qs}` : MIRROR_PAGE;
}

let selectedUdid = null;
let screenTimer = 0;
let lastScreenIosMajor = null;
let transport = localStorage.getItem("handset-transport") === "wifi" ? "wifi" : "usb";
let wifiPaired = [];
let usbConnected = false;

document.querySelectorAll("[data-transport]").forEach((btn) => {
  btn.addEventListener("click", () => setTransport(btn.dataset.transport));
});
wifiPair.addEventListener("click", () => setUpWifi());
setTransport(transport, false);

function setTransport(value, reload = true) {
  transport = value === "wifi" ? "wifi" : "usb";
  localStorage.setItem("handset-transport", transport);
  document.querySelectorAll("[data-transport]").forEach((btn) => {
    const active = btn.dataset.transport === transport;
    btn.classList.toggle("is-active", active);
    btn.setAttribute("aria-checked", String(active));
  });
  if (reload) load();
}

function renderWifi() {
  const ready = selectedUdid ? wifiPaired.includes(selectedUdid) : wifiPaired.length > 0;
  wifiState.textContent = ready ? "✓ Wi‑Fi ready" : "Wi‑Fi not set up";
  wifiState.classList.toggle("ok", ready);
  wifiPair.hidden = ready;
  wifiPair.disabled = !usbConnected;
  wifiPair.title = usbConnected ? "One-time setup over the cable" : "Plug in the cable once to set up Wi‑Fi";
}

async function setUpWifi() {
  wifiPair.disabled = true;
  wifiPair.textContent = "Setting up…";
  try {
    const result = await postJson("/api/wifi/pair", { udid: selectedUdid });
    if (!result.ok) throw new Error(result.error || "Wi‑Fi setup failed.");
    screenNote.textContent = "Wi‑Fi is set up. You can unplug the cable and choose Wi‑Fi.";
    screenNote.className = "";
  } catch (error) {
    screenNote.textContent = error.message;
    screenNote.className = "warn";
  } finally {
    wifiPair.textContent = "Set up Wi‑Fi";
    load();
  }
}

refresh.addEventListener("click", () => load());
showScreen.addEventListener("click", () => showPhone());
restartScreen.addEventListener("click", () => restartMirror());
wireRemoteControls();

toggleGuide.addEventListener("click", () => {
  const open = runGuide.hidden;
  runGuide.hidden = !open;
  toggleGuide.setAttribute("aria-expanded", String(open));
  if (open) runGuide.scrollIntoView({ behavior: "smooth", block: "start" });
});

async function load() {
  refresh.disabled = true;
  detail.hidden = true;
  detail.replaceChildren();
  try {
    const state = await getJson("/api/status");
    wifiPaired = state.wifi?.paired || [];
    usbConnected = (state.devices || []).length > 0;
    renderStatus(state);
    renderDevices(state.devices || []);
    renderWifi();
    renderScreen(state.screen);
    renderPills(state);
  } catch (error) {
    setPill(pillConnection, "Offline", "bad");
    statusNote.textContent = error.message;
    statusNote.className = "warn";
  } finally {
    refresh.disabled = false;
  }
}

function renderPills(state) {
  const driver = state.driver || {};
  const connected = (state.devices || []).length > 0;
  const overWifi = transport === "wifi" && wifiPaired.length > 0;
  if (state.screen?.phase === "running") {
    setPill(pillConnection, state.screen.transport === "wifi" ? "Mirroring · Wi‑Fi" : "Mirroring", "ok");
  } else if (overWifi) {
    setPill(pillConnection, "Wi‑Fi ready", "ok");
  } else if (connected) {
    setPill(pillConnection, "Connected", "ok");
  } else if (driver.running) {
    setPill(pillConnection, "Driver running", "");
  } else {
    setPill(pillConnection, "No connection", "warn");
  }

  const first = (state.devices || [])[0];
  if (first) {
    pillDevice.hidden = false;
    pillDevice.textContent = first.name || first.model || "iPhone";
  } else if (overWifi) {
    pillDevice.hidden = false;
    pillDevice.textContent = "iPhone (Wi‑Fi)";
  } else {
    pillDevice.hidden = true;
  }
}

function setPill(pill, text, kind) {
  pill.textContent = text;
  pill.className = `pill ${kind ? `pill-${kind}` : ""}`.trim();
}

function renderStatus(state) {
  statusList.replaceChildren();
  const driver = state.driver || {};
  addRow(statusList, "Apple Mobile Device service", driver.running ? "Running" : "Stopped");
  addRow(statusList, "Driver DLL", driver.dll_found ? "Found" : "Missing");
  const count = (state.devices || []).length;
  addRow(statusList, "USB devices", `${count} attached`);
  const wifiCount = wifiPaired.length;
  addRow(statusList, "Wi‑Fi paired", `${wifiCount} remembered`);
  if (!driver.running) {
    statusNote.textContent =
      "Apple Mobile Device service is not running. Install 'Apple Devices' from Microsoft Store or iTunes.";
    statusNote.className = "warn";
  } else {
    statusNote.textContent = "";
    statusNote.className = "";
  }
}

function renderDevices(devices) {
  devicesEl.replaceChildren();
  if (devices.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent =
      transport === "wifi" && wifiPaired.length > 0
        ? "No cable connected. iPhone is ready to mirror over Wi‑Fi."
        : "No iPhone connected over USB yet. Plug it in and tap Trust.";
    devicesEl.appendChild(li);
    selectedUdid = null;
    return;
  }
  devices.forEach((dev) => {
    const li = document.createElement("li");
    li.className = "device-item";
    const name = document.createElement("p");
    name.className = "device-name";
    name.textContent = dev.name || "iPhone";
    const meta = document.createElement("p");
    meta.className = "device-meta";
    meta.textContent = [dev.model, dev.connection_type].filter(Boolean).join(" · ");
    li.appendChild(name);
    li.appendChild(meta);
    li.addEventListener("click", () => selectDevice(dev.udid));
    devicesEl.appendChild(li);
  });
  if (!selectedUdid || !devices.some((d) => d.udid === selectedUdid)) {
    selectDevice(devices[0].udid);
  }
}

async function selectDevice(udid) {
  selectedUdid = udid;
  renderWifi();
  try {
    const dev = await getJson(`/api/devices/${encodeURIComponent(udid)}`);
    renderDetail(dev);
  } catch (error) {
    detail.hidden = false;
    detail.textContent = error.message;
  }
}

function renderDetail(device) {
  detail.hidden = false;
  detail.replaceChildren();
  const dl = document.createElement("dl");
  dl.className = "kv";
  addRow(dl, "Name", device.DeviceName);
  addRow(dl, "Model", device.ProductType);
  addRow(dl, "iOS version", device.ProductVersion);
  addRow(dl, "Serial", device.SerialNumber);
  addRow(dl, "UDID", device.UniqueDeviceID);
  addRow(dl, "Wi‑Fi address", device.WiFiAddress);
  addRow(dl, "Developer mode", device.DeveloperModeStatus ? "Enabled" : "Disabled");
  detail.appendChild(dl);
}

function renderScreen(screen) {
  if (!screen) return;
  if (screen.iosMajor != null) lastScreenIosMajor = screen.iosMajor;
  const mirroring = screen.phase === "running";
  if (mirroring) {
    workspace.classList.add("is-live");
    phoneShell.classList.add("live");
    remotePanel.hidden = false;
    restartScreen.hidden = false;
    kbToggle.hidden = false;
    screenNote.textContent = "";
    screenNote.className = "";
    showScreen.textContent = "Mirroring…";
    showScreen.disabled = true;
    const mirrorSrc = mirrorPageUrl(screen);
    const src = screenView.getAttribute("src") || "";
    if (!src.includes("/mirror.html")) {
      screenView.src = mirrorSrc;
    }
    screenView.hidden = false;
    const compactName = document.querySelector("#compact-device-name");
    if (compactName && screen.transport) {
      compactName.textContent = screen.transport === "wifi" ? "iPhone (Wi‑Fi)" : "iPhone (Cable)";
    }
    return;
  }

  workspace.classList.remove("is-live");
  phoneShell.classList.remove("live", "is-landscape");
  remotePanel.hidden = true;
  restartScreen.hidden = true;
  kbToggle.hidden = true;
  screenView.hidden = true;
  screenView.src = "about:blank";

  if (screen.phase === "starting") {
    showScreen.disabled = true;
    showScreen.textContent = "Starting…";
    screenNote.textContent = screen.note || "Starting screen stream…";
    screenNote.className = "";
  } else if (screen.phase === "error") {
    showScreen.disabled = false;
    showScreen.textContent = "Start mirroring";
    screenNote.textContent = screen.error || "Failed to start mirroring.";
    screenNote.className = "warn";
  } else {
    showScreen.disabled = false;
    showScreen.textContent = "Start mirroring";
    screenNote.textContent = "";
    screenNote.className = "";
  }
}

async function showPhone() {
  screenNote.textContent =
    transport === "wifi" ? "Connecting over Wi‑Fi…" : "Starting screen stream…";
  screenNote.className = "";
  showScreen.disabled = true;
  showScreen.textContent = "Starting…";
  try {
    const screen = await postJson("/api/screen", { udid: selectedUdid, transport });
    renderScreen(screen);
    pollScreen();
  } catch (error) {
    screenNote.textContent = error.message;
    screenNote.className = "warn";
    showScreen.disabled = false;
    showScreen.textContent = "Start mirroring";
  }
}

function pollScreen() {
  window.clearTimeout(screenTimer);
  screenTimer = window.setTimeout(async () => {
    try {
      const screen = await getJson("/api/screen");
      renderScreen(screen);
      if (screen.phase === "starting") {
        pollScreen();
      }
    } catch (_) {
      pollScreen();
    }
  }, 1000);
}

function addRow(container, key, value) {
  if (value === undefined || value === null || value === "") return;
  const dt = document.createElement("dt");
  dt.textContent = key;
  const dd = document.createElement("dd");
  dd.textContent = String(value);
  container.appendChild(dt);
  container.appendChild(dd);
}

async function getJson(url) {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function postJson(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

async function mirrorPost(path, data) {
  return fetch(`${MIRROR_API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data || {}),
  }).catch(() => {});
}

function mirrorMessage(cmd, extra = {}) {
  if (!screenView.contentWindow) return;
  screenView.contentWindow.postMessage({ source: "handset", cmd, ...extra }, window.location.origin);
}

window.addEventListener("message", (e) => {
  if (e.origin !== window.location.origin) return;
  if (e.data?.source !== "handset-mirror") return;
  phoneShell.classList.toggle("is-landscape", Boolean(e.data.landscape));
});

function reloadMirrorIframe() {
  if (screenView.hidden) return;
  const stamp = `t=${Date.now()}`;
  screenView.src = "about:blank";
  requestAnimationFrame(() => {
    const base = mirrorPageUrl({ iosMajor: lastScreenIosMajor });
    const sep = base.includes("?") ? "&" : "?";
    screenView.src = `${base}${sep}${stamp}`;
  });
}

async function restartMirror() {
  restartScreen.disabled = true;
  restartScreen.textContent = "Restarting…";
  screenNote.textContent = "Restarting screen stream…";
  screenNote.className = "";
  try {
    const res = await postJson("/api/screen/restart", { udid: selectedUdid });
    renderScreen(res);
    reloadMirrorIframe();
    pollScreen();
  } catch (error) {
    screenNote.textContent = error.message;
    screenNote.className = "warn";
  } finally {
    restartScreen.disabled = false;
    restartScreen.textContent = "Restart stream";
  }
}

async function gesture(name) {
  switch (name) {
    case "home":
      return mirrorPost("/button", { name: "home", state: "press" });
    case "switcher":
      return mirrorPost("/button", { name: "app-switch", state: "press" });
    case "notifications":
      return mirrorPost("/gesture", { kind: "notifications" });
    case "control-center":
      return mirrorPost("/gesture", { kind: "control-center" });
    default:
      break;
  }
}

async function swipe(dir) {
  const points = {
    left: { x1: 0.98, y1: 0.5, x2: 0.5, y2: 0.5 },
    right: { x1: 0.02, y1: 0.5, x2: 0.5, y2: 0.5 },
    up: { x1: 0.5, y1: 0.95, x2: 0.5, y2: 0.5 },
    down: { x1: 0.5, y1: 0.05, x2: 0.5, y2: 0.5 },
  }[dir];
  if (!points) return;
  return mirrorPost("/gesture", { kind: "drag", duration: 0.2, ...points });
}

function setKeyboard(on) {
  window.handsetKeyboardOn = Boolean(on);
  if (!kbToggle) return;
  kbToggle.setAttribute("aria-pressed", String(window.handsetKeyboardOn));
  const label = kbToggle.querySelector(".kb-state");
  if (label) label.textContent = window.handsetKeyboardOn ? "on" : "off";
  kbToggle.classList.toggle("ghost-active", window.handsetKeyboardOn);
}

function toggleFullscreen() {
  const el = phoneScreen;
  if (!el) return;
  if (!document.fullscreenElement) {
    (el.requestFullscreen || el.webkitRequestFullscreen || el.msRequestFullscreen).call(el);
  } else {
    (document.exitFullscreen || document.webkitExitFullscreen || document.msExitFullscreen).call(document);
  }
}

const keyboard = window.HandsetKeys.attach({
  target: window,
  post: (path, data) => mirrorPost(path, data),
  enabled: () => window.handsetKeyboardOn && workspace.classList.contains("is-live"),
});

const COMPACT_SIZE = { width: 440, height: 890 };
const STANDARD_SIZE = { width: 1280, height: 860 };

function postWindow(action, size = {}) {
  if (window.electronAPI) {
    if (action === "minimize" && window.electronAPI.minimize) {
      window.electronAPI.minimize();
      return Promise.resolve();
    }
    if (action === "close" && window.electronAPI.close) {
      window.electronAPI.close();
      return Promise.resolve();
    }
    if (action === "resize" && window.electronAPI.resize && size.width && size.height) {
      window.electronAPI.resize(size.width, size.height);
    }
  }
  return fetch(`/api/window/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(size),
  }).catch(() => {});
}

function setCompact(enable) {
  const on = document.body.classList.toggle("is-compact", enable);
  document.documentElement.classList.toggle("is-compact", on);
  const toggleCompact = document.querySelector("#toggle-compact");
  const compactBtn = document.querySelector("#compact-btn");
  const compactBar = document.querySelector("#compact-bar");
  if (toggleCompact) {
    toggleCompact.textContent = on ? "Expanded" : "Compact";
    toggleCompact.title = on ? "Return to full layout" : "Compact window layout";
  }
  if (compactBtn) {
    compactBtn.textContent = on ? "Expanded layout" : "Compact window";
  }
  if (compactBar) compactBar.hidden = !on;
  const size = on ? COMPACT_SIZE : STANDARD_SIZE;
  postWindow("resize", size);
}

async function refreshAirPlayUi() {
  const btn = document.querySelector("#compact-audio");
  const note = document.querySelector("#audio-popup-note");
  if (!btn) return;
  try {
    const data = await getJson("/api/airplay/status");
    btn.classList.toggle("is-connected", Boolean(data.connected));
    btn.classList.toggle("is-unavailable", !data.available);
    if (!data.available) {
      btn.title = "AirPlay receiver not installed (add handset/bin/shairport.exe)";
      if (note) {
        note.hidden = false;
        note.textContent =
          "Pane Audio is not bundled in this build. Place Shairport4w as handset/bin/shairport.exe to enable it.";
      }
    } else if (data.connected) {
      btn.title = "Audio streaming via Pane Audio";
      if (note) note.hidden = true;
    } else {
      btn.title = "Set up AirPlay audio (click for steps)";
      if (note) note.hidden = true;
    }
  } catch (_) {}
}

function wireRemoteControls() {
  const toggleCompact = () => setCompact(!document.body.classList.contains("is-compact"));
  document.querySelector("#toggle-compact")?.addEventListener("click", toggleCompact);
  document.querySelector("#compact-btn")?.addEventListener("click", toggleCompact);
  document.querySelector("#compact-close")?.addEventListener("click", () => setCompact(false));
  document.querySelector("#compact-min")?.addEventListener("click", () => postWindow("minimize"));
  document.querySelector("#compact-expand")?.addEventListener("click", toggleFullscreen);
  document.querySelector("#win-min")?.addEventListener("click", () => postWindow("minimize"));
  document.querySelector("#win-close")?.addEventListener("click", () => postWindow("close"));

  const audioPopup = document.querySelector("#audio-popup");
  const openAudio = async (e) => {
    e?.preventDefault?.();
    await refreshAirPlayUi();
    if (audioPopup) audioPopup.hidden = false;
  };
  document.querySelector("#compact-audio")?.addEventListener("click", openAudio);
  document.querySelector("#open-audio")?.addEventListener("click", openAudio);
  const closeAudio = () => {
    if (audioPopup) audioPopup.hidden = true;
  };
  document.querySelector("#audio-popup-close")?.addEventListener("click", closeAudio);
  document.querySelector("#audio-popup-ok")?.addEventListener("click", closeAudio);
  document.addEventListener("click", (e) => {
    if (audioPopup && !audioPopup.hidden && !e.target.closest("#audio-popup, #compact-audio")) {
      closeAudio();
    }
  });
  setInterval(refreshAirPlayUi, 4000);
  refreshAirPlayUi();

  const startDrag = (el) => {
    if (!el) return;
    el.addEventListener("mousedown", (e) => {
      if (e.button !== 0 || e.target.closest("button, a, input, select, textarea")) return;
      postWindow("drag");
    });
  };
  document.querySelectorAll(".bar-drag").forEach(startDrag);

  kbToggle.addEventListener("click", () => setKeyboard(!window.handsetKeyboardOn));
  setKeyboard(true);
  // A focused button would swallow Space and Enter instead of typing them.
  document.addEventListener("pointerup", (e) => {
    const btn = e.target.closest?.("button");
    if (btn) btn.blur();
  });
  document.querySelectorAll("[data-gesture]").forEach((btn) => {
    btn.addEventListener("click", () => gesture(btn.dataset.gesture));
  });
  document.querySelector("#fullscreen")?.addEventListener("click", toggleFullscreen);
  document.querySelector("#fs-exit")?.addEventListener("click", toggleFullscreen);
  document.addEventListener("fullscreenchange", () => {
    const btn = document.querySelector("#fullscreen");
    if (btn) btn.textContent = document.fullscreenElement ? "Exit full screen" : "⛶ Full screen";
  });
  document.querySelectorAll("[data-btn]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.btn;
      if (name) mirrorPost("/button", { name, state: "press" });
    });
  });
  document.querySelectorAll("[data-swipe]").forEach((btn) => {
    btn.addEventListener("click", () => swipe(btn.dataset.swipe));
  });
  document.querySelector("#zoom-in")?.addEventListener("click", () => mirrorMessage("zoom-in"));
  document.querySelector("#zoom-out")?.addEventListener("click", () => mirrorMessage("zoom-out"));
  document.querySelector("#zoom-reset")?.addEventListener("click", () => mirrorMessage("zoom-reset"));
  document.querySelector("#rotate-cw")?.addEventListener("click", () => mirrorMessage("rotate", { deg: 90 }));
  document.querySelector("#rotate-ccw")?.addEventListener("click", () => mirrorMessage("rotate", { deg: -90 }));
}

load();
if (window.electronAPI) {
  setCompact(true);
}
