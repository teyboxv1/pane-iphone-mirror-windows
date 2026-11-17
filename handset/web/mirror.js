const MIRROR = "/mirror";
const KNOWN_IOS_MAJOR = (() => {
  const raw = new URLSearchParams(window.location.search).get("iosMajor");
  if (raw == null || raw === "") return null;
  const n = parseInt(raw, 10);
  return Number.isFinite(n) ? n : null;
})();
const NO_PICTURE_IOS26 =
  "Live video needs iOS 27 or later. This iPhone can connect, but it does not send a picture on this iOS version.";
const NO_PICTURE_UNKNOWN =
  "No picture yet. Keep the iPhone unlocked and press Restart screen. If this phone is on iOS 26 or older, Apple does not send live video until iOS 27.";
const canvas = document.getElementById("c");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("mirror-status");

let visualRotation = 0;
let zoom = 1;
const ZOOM_STEP = 1.2;
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;

let pendingFrame = null;
let rafScheduled = false;
let lastFrame = null;
let lastFrameLandscape = null;
let frameCount = 0;
let runGeneration = 0;
let abortStream = null;

function setStatus(text, tone) {
  if (!statusEl) return;
  statusEl.textContent = text;
  statusEl.className = "mirror-status" + (tone ? ` ${tone}` : "");
}

function fitCanvas() {
  if (!canvas.width || !canvas.height) return;
  const parent = canvas.parentElement;
  if (!parent) return;
  const rect = parent.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return;
  const naturalW = canvas.width;
  const naturalH = canvas.height;
  const base = Math.min(rect.width / naturalW, rect.height / naturalH);
  const scale = base * zoom;
  canvas.style.width = `${naturalW * scale}px`;
  canvas.style.height = `${naturalH * scale}px`;
  publishOrientation();
}

function publishOrientation() {
  const landscape = canvas.width > canvas.height;
  try {
    window.parent.postMessage({ source: "handset-mirror", landscape }, window.location.origin);
  } catch (_) {}
}

window.addEventListener("resize", fitCanvas);

function setZoom(value) {
  zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, value));
  if (Math.abs(zoom - 1) < 0.02) zoom = 1;
  fitCanvas();
}

function touchCoords(e) {
  const rect = canvas.getBoundingClientRect();
  const sx = ((e.clientX - rect.left) * canvas.width) / rect.width;
  const sy = ((e.clientY - rect.top) * canvas.height) / rect.height;
  const cw = canvas.width;
  const ch = canvas.height;
  const sideways = Math.abs(visualRotation % 180) === 90;
  const dw = sideways ? ch : cw;
  const dh = sideways ? cw : ch;
  const dx = sx - cw / 2;
  const dy = sy - ch / 2;
  const rad = (-visualRotation * Math.PI) / 180;
  const cos = Math.cos(rad);
  const sin = Math.sin(rad);
  const bx = dx * cos - dy * sin + dw / 2;
  const by = dx * sin + dy * cos + dh / 2;
  return {
    x: Math.max(0, Math.min(65535, Math.round((bx / dw) * 65535))),
    y: Math.max(0, Math.min(65535, Math.round((by / dh) * 65535))),
  };
}

async function postJson(path, payload) {
  try {
    await fetch(`${MIRROR}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (_) {
    /* stream may be down */
  }
}

let activePointer = null;
let lastCoords = { x: 0, y: 0 };

// The proxy opens one connection per request, so concurrent fetches can land
// out of order and break drags. Send touches strictly in sequence, collapsing
// queued moves into the newest one.
const touchQueue = [];
let touchBusy = false;

function sendTouch(type, coords, isMove = false) {
  const last = touchQueue[touchQueue.length - 1];
  const event = { type, x: coords.x, y: coords.y, isMove };
  if (isMove && last && last.isMove) touchQueue[touchQueue.length - 1] = event;
  else touchQueue.push(event);
  pumpTouches();
}

async function pumpTouches() {
  if (touchBusy) return;
  touchBusy = true;
  while (touchQueue.length) {
    const { type, x, y } = touchQueue.shift();
    await postJson("/touch", { type, x, y });
  }
  touchBusy = false;
}

// iOS system gestures (Home bar, Control Center, Notification Center) only
// trigger when the contact begins on the screen edge itself.
const EDGE = 2500;
function snapToEdge(c) {
  return {
    x: c.x < EDGE ? 0 : c.x > 65535 - EDGE ? 65535 : c.x,
    y: c.y < EDGE ? 0 : c.y > 65535 - EDGE ? 65535 : c.y,
  };
}

// Injected touches arrive too slowly for iOS to read a bottom-edge flick as
// the Home gesture, so a drag that starts on the bottom edge is kept local and
// turned into the Home button (or a double press for the app switcher when
// the finger pauses before lifting).
const HOME_SWIPE_MIN = 5000;
const SWITCHER_HOLD_MS = 450;
let edgeSwipe = null;

async function pressHome(times = 1) {
  for (let i = 0; i < times; i++) {
    if (i) await new Promise((r) => setTimeout(r, 120));
    await postJson("/button", { name: "home", state: "press" });
  }
}

function releaseActive() {
  if (activePointer === null) return;
  activePointer = null;
  if (edgeSwipe) {
    const swipe = edgeSwipe;
    edgeSwipe = null;
    if (swipe.armed) {
      const paused = performance.now() - swipe.lastMoveAt > SWITCHER_HOLD_MS;
      pressHome(paused ? 2 : 1);
    } else {
      sendTouch("contact", swipe.start);
      sendTouch("release", swipe.start);
    }
    return;
  }
  sendTouch("release", lastCoords);
}

// Listen on the whole document so a drag can start on the black margin just
// below the picture; coordinates clamp onto the screen edge.
document.addEventListener("pointerdown", (e) => {
  if (e.button !== 0) return;
  e.preventDefault();
  canvas.focus({ preventScroll: true });
  try {
    document.body.setPointerCapture(e.pointerId);
  } catch (_) {}
  activePointer = e.pointerId;
  lastCoords = snapToEdge(touchCoords(e));
  if (lastCoords.y === 65535) {
    edgeSwipe = { start: lastCoords, armed: false, lastMoveAt: performance.now(), lastY: lastCoords.y };
    return;
  }
  sendTouch("contact", lastCoords);
});

function onMove(e) {
  if (e.pointerId !== activePointer) return;
  e.preventDefault();
  lastCoords = touchCoords(e);
  if (edgeSwipe) {
    if (edgeSwipe.start.y - lastCoords.y > HOME_SWIPE_MIN) edgeSwipe.armed = true;
    if (Math.abs(lastCoords.y - edgeSwipe.lastY) > 600) {
      edgeSwipe.lastMoveAt = performance.now();
      edgeSwipe.lastY = lastCoords.y;
    }
    return;
  }
  sendTouch("contact", lastCoords, true);
}

function onUp(e) {
  if (e.pointerId !== activePointer) return;
  e.preventDefault();
  lastCoords = touchCoords(e);
  releaseActive();
}

window.addEventListener("pointermove", onMove);
window.addEventListener("pointerup", onUp);
window.addEventListener("pointercancel", onUp);
document.body.addEventListener("lostpointercapture", (e) => {
  if (e.pointerId === activePointer) releaseActive();
});
window.addEventListener("blur", releaseActive);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") releaseActive();
});

document.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  pressHome();
});

window.HandsetKeys.attach({
  post: (payload) => postJson("/key", payload),
  enabled: () => {
    try {
      return window.parent.handsetKeyboardOn !== false;
    } catch (_) {
      return true;
    }
  },
});

window.addEventListener("message", (e) => {
  if (e.origin !== window.location.origin) return;
  const d = e.data;
  if (!d || d.source !== "handset") return;
  if (d.cmd === "rotate") {
    visualRotation = (visualRotation + (d.deg || 0)) % 360;
    if (lastFrame) drawFrame(lastFrame);
    fitCanvas();
  } else if (d.cmd === "zoom-in") {
    setZoom(zoom * ZOOM_STEP);
  } else if (d.cmd === "zoom-out") {
    setZoom(zoom / ZOOM_STEP);
  } else if (d.cmd === "zoom-reset") {
    setZoom(1);
  } else if (d.cmd === "reload") {
    beginRun();
  }
});

async function fetchCodecWithRetry() {
  const delays = [200, 500, 1000, 2000, 3000, 4000];
  let lastErr = "";
  for (let attempt = 0; attempt <= delays.length; attempt++) {
    if (attempt > 0) await new Promise((r) => setTimeout(r, delays[attempt - 1]));
    try {
      const resp = await fetch(`${MIRROR}/codec`, { cache: "no-store" });
      if (!resp.ok) {
        lastErr = `HTTP ${resp.status}`;
        continue;
      }
      const info = await resp.json();
      if (!info.codec || !info.description) {
        lastErr = "waiting for video parameters";
        continue;
      }
      const description = Uint8Array.from(atob(info.description), (c) => c.charCodeAt(0));
      return { codec: info.codec.trim(), description };
    } catch (err) {
      lastErr = err.message || String(err);
    }
  }
  throw new Error(lastErr || "codec unreachable");
}

function drawFrame(f) {
  const sideways = Math.abs(visualRotation % 180) === 90;
  const fw = f.displayWidth;
  const fh = f.displayHeight;
  const targetW = sideways ? fh : fw;
  const targetH = sideways ? fw : fh;
  if (targetW !== canvas.width || targetH !== canvas.height) {
    canvas.width = targetW;
    canvas.height = targetH;
    fitCanvas();
  }
  const dstW = canvas.width;
  const dstH = canvas.height;
  const fpW = sideways ? dstH : dstW;
  const fpH = sideways ? dstW : dstH;
  ctx.save();
  ctx.translate(dstW / 2, dstH / 2);
  if (visualRotation) ctx.rotate((visualRotation * Math.PI) / 180);
  ctx.drawImage(f, -fpW / 2, -fpH / 2, fpW, fpH);
  ctx.restore();
}

function drawPending() {
  rafScheduled = false;
  const f = pendingFrame;
  pendingFrame = null;
  if (!f) return;
  const landscape = f.displayWidth > f.displayHeight;
  if (lastFrameLandscape !== null && landscape !== lastFrameLandscape && visualRotation !== 0) {
    visualRotation = 0;
  }
  lastFrameLandscape = landscape;
  try {
    drawFrame(f);
    if (frameCount === 1) setStatus("Live", "ok");
  } catch (_) {}
  if (lastFrame && lastFrame !== f) {
    try {
      lastFrame.close();
    } catch (_) {}
  }
  lastFrame = f;
}

async function run(generation) {
  setStatus("Connecting to stream…");
  frameCount = 0;
  const startedAt = performance.now();
  const watchdog = window.setInterval(() => {
    if (generation !== runGeneration) {
      window.clearInterval(watchdog);
      return;
    }
    if (frameCount > 0) {
      window.clearInterval(watchdog);
      return;
    }
    if (performance.now() - startedAt > 12000) {
      window.clearInterval(watchdog);
      setStatus(
        KNOWN_IOS_MAJOR != null && KNOWN_IOS_MAJOR < 27 ? NO_PICTURE_IOS26 : NO_PICTURE_UNKNOWN,
        "warn",
      );
    }
  }, 1000);

  const { codec, description } = await fetchCodecWithRetry();
  if (generation !== runGeneration) return;

  const decoderConfig = { codec, description, optimizeForLatency: true };
  const support = await VideoDecoder.isConfigSupported({ codec, description });
  if (!support.supported) {
    setStatus("This browser cannot decode the iPhone video stream.", "warn");
    return;
  }

  let needsResync = false;
  let autoRestartUsed = false;

  const buildDecoder = () =>
    new VideoDecoder({
      output: (frame) => {
        if (pendingFrame) {
          try {
            pendingFrame.close();
          } catch (_) {}
        }
        pendingFrame = frame;
        if (!rafScheduled) {
          rafScheduled = true;
          requestAnimationFrame(drawPending);
        }
        frameCount += 1;
      },
      error: () => {
        needsResync = true;
        if (!autoRestartUsed && frameCount < 5) {
          autoRestartUsed = true;
          fetch(`${MIRROR}/restart`, { method: "POST", cache: "no-store" }).catch(() => {});
        } else {
          fetch(`${MIRROR}/pli`, { method: "POST", cache: "no-store" }).catch(() => {});
        }
      },
    });

  let decoder = buildDecoder();
  decoder.configure(decoderConfig);
  setStatus("Waiting for video…");

  let resp = null;
  const streamDelays = [300, 600, 1200, 2000, 3000, 5000, 8000];
  for (let a = 0; a <= streamDelays.length; a++) {
    if (generation !== runGeneration) return;
    if (a > 0) {
      setStatus(`Waiting for video stream (retry ${a})…`);
      await new Promise((r) => setTimeout(r, streamDelays[a - 1]));
      if (a === 2) {
        await fetch(`${MIRROR}/pli`, { method: "POST", cache: "no-store" }).catch(() => {});
      }
    }
    try {
      const r = await fetch(`${MIRROR}/stream.bin`, { cache: "no-store" });
      if (r.ok) {
        resp = r;
        break;
      }
      if (r.status === 503) {
        setStatus("Stream starting on the iPhone…");
        continue;
      }
      setStatus(`Stream error (HTTP ${r.status})`, "warn");
    } catch (err) {
      setStatus(err.message || "Stream unreachable", "warn");
    }
  }
  if (!resp || generation !== runGeneration) {
    setStatus("Cannot reach the video stream. Press Restart screen.", "warn");
    return;
  }

  const reader = resp.body.getReader();
  abortStream = () => reader.cancel().catch(() => {});
  let buf = new Uint8Array(0);
  let timestamp = 0;
  let gotKey = false;

  while (generation === runGeneration) {
    const { value, done } = await reader.read();
    if (done) break;
    const merged = new Uint8Array(buf.length + value.length);
    merged.set(buf);
    merged.set(value, buf.length);
    buf = merged;
    while (buf.length >= 4) {
      const len = (buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3];
      if (buf.length < 4 + len) break;
      const type = buf[4];
      const data = buf.slice(5, 4 + len);
      buf = buf.subarray(4 + len);

      if (type === 2) {
        try {
          decoder.close();
        } catch (_) {}
        decoder = buildDecoder();
        decoder.configure(decoderConfig);
        needsResync = false;
        gotKey = true;
      } else if (type === 0) {
        gotKey = true;
        if (needsResync) {
          try {
            decoder.close();
          } catch (_) {}
          decoder = buildDecoder();
          decoder.configure(decoderConfig);
          needsResync = false;
        }
      }
      if (!gotKey || needsResync) continue;
      if (decoder.state !== "configured") {
        try {
          decoder.close();
        } catch (_) {}
        decoder = buildDecoder();
        decoder.configure(decoderConfig);
        needsResync = true;
        continue;
      }
      try {
        decoder.decode(
          new EncodedVideoChunk({
            type: type === 0 || type === 2 ? "key" : "delta",
            timestamp,
            data,
          }),
        );
        timestamp += 16666;
      } catch (_) {
        needsResync = true;
      }
    }
  }
  if (generation === runGeneration) {
    setStatus("Stream ended — press Restart screen", "warn");
  }
}

function beginRun() {
  runGeneration += 1;
  const generation = runGeneration;
  if (abortStream) {
    abortStream();
    abortStream = null;
  }
  if (pendingFrame) {
    try {
      pendingFrame.close();
    } catch (_) {}
    pendingFrame = null;
  }
  if (lastFrame) {
    try {
      lastFrame.close();
    } catch (_) {}
    lastFrame = null;
  }
  frameCount = 0;
  run(generation).catch((err) => {
    setStatus(err.message || "Mirror failed", "warn");
  });
}

beginRun();
