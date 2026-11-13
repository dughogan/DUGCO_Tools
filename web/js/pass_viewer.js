// DUGco Pass Viewer: the in-node viewer. One <video> per pass, stacked; the dropdown picks which one
// shows, and every switch carries the current frame across so passes can be compared on the same frame.
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const STYLE = `
.dugco-pv { --orange:#ff4219; --ink:#0a0a0a; --cream:#f2f1ed; --line:#2b2b2b; --mute:#9a978f;
  display:flex; flex-direction:column; width:100%; height:100%; min-height:0; box-sizing:border-box;
  background:var(--ink); color:var(--cream); border:1px solid var(--line); border-radius:10px; overflow:hidden;
  font-family:"Chakra Petch", "Segoe UI", system-ui, sans-serif; font-size:13px; outline:none; }
.dugco-pv:focus-visible { border-color:var(--orange); }
.dugco-pv * { box-sizing:border-box; }
.dugco-pv-bar { display:flex; align-items:center; gap:6px; padding:7px 8px; background:#141414; flex:0 0 auto; }
.dugco-pv-brand { font-family:"IBM Plex Mono", ui-monospace, Consolas, monospace; font-size:10px; letter-spacing:.18em;
  text-transform:uppercase; color:var(--mute); display:flex; align-items:center; gap:6px; white-space:nowrap; }
.dugco-pv-brand::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--orange); }
.dugco-pv select { flex:1 1 auto; min-width:0; height:30px; padding:0 8px; border-radius:6px; border:1px solid #3a3a3a;
  background:var(--cream); color:var(--ink); font:700 13px "Chakra Petch", "Segoe UI", system-ui, sans-serif;
  text-transform:uppercase; letter-spacing:.04em; cursor:pointer; }
.dugco-pv button { height:30px; min-width:30px; padding:0 8px; border-radius:6px; border:1px solid #3a3a3a; background:#1f1f1f;
  color:var(--cream); font:700 12px "Chakra Petch", "Segoe UI", system-ui, sans-serif; cursor:pointer;
  display:inline-flex; align-items:center; justify-content:center; }
.dugco-pv button:hover:not(:disabled) { background:var(--orange); border-color:var(--orange); color:var(--ink); }
.dugco-pv button:disabled, .dugco-pv select:disabled { opacity:.35; cursor:default; }
.dugco-pv button svg { width:14px; height:14px; fill:none; stroke:currentColor; stroke-width:2.2; stroke-linecap:round; stroke-linejoin:round; }
.dugco-pv-count { font-family:"IBM Plex Mono", ui-monospace, Consolas, monospace; font-size:11px; color:var(--mute); white-space:nowrap; }
.dugco-pv-stage { position:relative; flex:1 1 auto; min-height:0; background:#000; }
.dugco-pv-stage video { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; visibility:hidden; }
.dugco-pv-stage video.on { visibility:visible; }
.dugco-pv-tag { position:absolute; left:8px; top:8px; padding:3px 8px; border-radius:6px; background:var(--orange); color:var(--ink);
  font-weight:700; font-size:11px; letter-spacing:.08em; text-transform:uppercase; pointer-events:none; }
.dugco-pv-empty { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; text-align:center;
  padding:16px; color:var(--mute); font-size:13px; line-height:1.5; }
.dugco-pv-note { padding:5px 10px; font-size:11.5px; color:#c9c6be; background:#101010; flex:0 0 auto; min-height:24px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dugco-pv-transport { display:flex; align-items:center; gap:6px; padding:7px 8px; background:#141414; flex:0 0 auto; }
.dugco-pv input[type=range] { flex:1 1 auto; min-width:0; accent-color:var(--orange); height:18px; cursor:pointer; }
.dugco-pv-frame { font-family:"IBM Plex Mono", ui-monospace, Consolas, monospace; font-size:11px; min-width:86px; text-align:right; white-space:nowrap; }
`;

const ICON = {
  up: '<svg viewBox="0 0 24 24"><path d="m6 15 6-6 6 6"/></svg>',
  down: '<svg viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>',
  play: '<svg viewBox="0 0 24 24"><path d="M7 4v16l13-8z"/></svg>',
  pause: '<svg viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></svg>',
  back: '<svg viewBox="0 0 24 24"><path d="m14 6-6 6 6 6"/></svg>',
  fwd: '<svg viewBox="0 0 24 24"><path d="m10 6 6 6-6 6"/></svg>',
};

function ensureStyle() {
  if (document.getElementById("dugco-pv-style")) return;
  const font = document.createElement("link");
  font.rel = "stylesheet";
  font.href = "https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;700&family=IBM+Plex+Mono&display=swap";
  document.head.appendChild(font);
  const style = document.createElement("style");
  style.id = "dugco-pv-style";
  style.textContent = STYLE;
  document.head.appendChild(style);
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

class Viewer {
  constructor(node) {
    this.node = node;
    this.passes = [];
    this.videos = {};
    this.current = null;
    this.playing = true;

    const root = (this.root = el("div", "dugco-pv"));
    root.tabIndex = 0;

    const bar = el("div", "dugco-pv-bar");
    bar.append(el("span", "dugco-pv-brand", "Pass"));
    this.select = el("select");
    this.select.title = "Pick the pass to look at";
    this.prevBtn = el("button", null, ICON.up);
    this.prevBtn.title = "Previous pass (Up arrow)";
    this.nextBtn = el("button", null, ICON.down);
    this.nextBtn.title = "Next pass (Down arrow)";
    this.count = el("span", "dugco-pv-count", "");
    bar.append(this.select, this.prevBtn, this.nextBtn, this.count);

    this.stage = el("div", "dugco-pv-stage");
    this.empty = el("div", "dugco-pv-empty", "Run the workflow to load the passes.");
    this.tag = el("div", "dugco-pv-tag");
    this.tag.style.display = "none";
    this.stage.append(this.empty, this.tag);

    this.note = el("div", "dugco-pv-note", "");

    const tr = el("div", "dugco-pv-transport");
    this.backBtn = el("button", null, ICON.back);
    this.backBtn.title = "Back one frame (Left arrow)";
    this.playBtn = el("button", null, ICON.pause);
    this.playBtn.title = "Play / pause (Space)";
    this.fwdBtn = el("button", null, ICON.fwd);
    this.fwdBtn.title = "Forward one frame (Right arrow)";
    this.scrub = el("input");
    this.scrub.type = "range";
    this.scrub.min = 0;
    this.scrub.max = 0;
    this.scrub.step = 1;
    this.scrub.value = 0;
    this.frameLabel = el("span", "dugco-pv-frame", "");
    tr.append(this.backBtn, this.playBtn, this.fwdBtn, this.scrub, this.frameLabel);

    root.append(bar, this.stage, this.note, tr);

    this.select.addEventListener("change", () => this.show(this.select.value));
    this.prevBtn.addEventListener("click", () => this.cycle(-1));
    this.nextBtn.addEventListener("click", () => this.cycle(1));
    this.playBtn.addEventListener("click", () => this.setPlaying(!this.playing));
    this.backBtn.addEventListener("click", () => this.step(-1));
    this.fwdBtn.addEventListener("click", () => this.step(1));
    this.scrub.addEventListener("input", () => {
      this.setPlaying(false);
      this.seekFrame(Number(this.scrub.value));
    });
    root.addEventListener("keydown", (e) => {
      if (e.target === this.select) return;
      const map = { ArrowUp: () => this.cycle(-1), ArrowDown: () => this.cycle(1), ArrowLeft: () => this.step(-1),
        ArrowRight: () => this.step(1), " ": () => this.setPlaying(!this.playing) };
      if (map[e.key]) {
        map[e.key]();
        e.preventDefault();
        e.stopPropagation();
      }
    });
    // Keep clicks and wheel inside the viewer from dragging or zooming the graph.
    for (const type of ["pointerdown", "mousedown", "wheel", "dblclick"]) {
      root.addEventListener(type, (e) => e.stopPropagation());
    }
    this.enable(false);
  }

  enable(on) {
    for (const c of [this.select, this.prevBtn, this.nextBtn, this.backBtn, this.playBtn, this.fwdBtn, this.scrub]) c.disabled = !on;
  }

  active() {
    return this.current ? this.videos[this.current] : null;
  }

  info() {
    return this.passes.find((p) => p.name === this.current);
  }

  load(passes, wanted) {
    const old = this.active();
    const time = old ? old.currentTime : 0;
    for (const v of Object.values(this.videos)) {
      v.pause();
      v.removeAttribute("src");
      v.load();
      v.remove();
    }
    this.videos = {};
    this.passes = passes || [];
    this.select.innerHTML = "";
    this.current = null;
    if (!this.passes.length) {
      this.empty.style.display = "";
      this.tag.style.display = "none";
      this.note.textContent = "";
      this.count.textContent = "";
      this.frameLabel.textContent = "";
      this.enable(false);
      return;
    }
    this.empty.style.display = "none";
    for (const p of this.passes) {
      const opt = el("option");
      opt.value = p.name;
      opt.textContent = p.label;
      this.select.append(opt);
      const v = el("video");
      v.muted = true;
      v.loop = true;
      v.playsInline = true;
      v.preload = "auto";
      const q = new URLSearchParams({ filename: p.filename, subfolder: p.subfolder, type: p.type, rand: p.rev });
      v.src = api.apiURL(`/view?${q}`);
      v.addEventListener("timeupdate", () => this.tick(v));
      v.addEventListener("seeked", () => this.tick(v));
      if (v.requestVideoFrameCallback) {
        // Frame-accurate counter while playing (timeupdate only fires a few times a second).
        const onFrame = () => {
          if (!v.isConnected) return;
          this.tick(v);
          v.requestVideoFrameCallback(onFrame);
        };
        v.requestVideoFrameCallback(onFrame);
      }
      v.addEventListener("error", () => {
        if (this.current === p.name) this.note.textContent = "This preview is gone (ComfyUI was restarted). Run the workflow again.";
      });
      this.stage.insertBefore(v, this.tag);
      this.videos[p.name] = v;
    }
    this.enable(true);
    const first = this.passes.some((p) => p.name === wanted) ? wanted : this.passes[0].name;
    this.show(first, time);
  }

  show(name, time) {
    const next = this.videos[name];
    if (!next) return;
    const prev = this.active();
    const t = time != null ? time : prev ? prev.currentTime : 0;
    if (prev && prev !== next) prev.pause();
    this.current = name;
    const apply = () => {
      try {
        next.currentTime = Math.min(t, Math.max(0, (next.duration || t) - 0.001));
      } catch (e) {}
      if (this.playing) next.play().catch(() => {});
    };
    if (next.readyState >= 1) apply();
    else next.addEventListener("loadedmetadata", apply, { once: true });
    for (const [n, v] of Object.entries(this.videos)) v.classList.toggle("on", n === name);
    const p = this.info();
    const i = this.passes.indexOf(p);
    this.select.value = name;
    this.tag.textContent = p.label;
    this.tag.style.display = "";
    this.note.textContent = p.note || "";
    this.note.title = p.note || "";
    this.count.textContent = `${i + 1} / ${this.passes.length}`;
    this.scrub.max = Math.max(0, p.frames - 1);
    this.node.properties = this.node.properties || {};
    this.node.properties.dugco_pass = name;
    this.tick(next);
  }

  cycle(dir) {
    if (!this.passes.length) return;
    const i = this.passes.findIndex((p) => p.name === this.current);
    this.show(this.passes[(i + dir + this.passes.length) % this.passes.length].name);
  }

  frameOf(v) {
    const p = this.info();
    if (!p) return 0;
    return Math.min(p.frames - 1, Math.max(0, Math.floor(v.currentTime * p.fps + 0.001)));
  }

  seekFrame(f) {
    const v = this.active();
    const p = this.info();
    if (!v || !p) return;
    f = Math.min(p.frames - 1, Math.max(0, f));
    v.currentTime = (f + 0.5) / p.fps;
    this.paint(f);
  }

  step(dir) {
    const v = this.active();
    const p = this.info();
    if (!v || !p) return;
    this.setPlaying(false);
    this.seekFrame((this.frameOf(v) + dir + p.frames) % p.frames);
  }

  setPlaying(on) {
    this.playing = on;
    this.playBtn.innerHTML = on ? ICON.pause : ICON.play;
    const v = this.active();
    if (!v) return;
    if (on) v.play().catch(() => {});
    else v.pause();
  }

  tick(v) {
    if (v !== this.active()) return;
    this.paint(this.frameOf(v));
  }

  paint(f) {
    const p = this.info();
    if (!p) return;
    if (document.activeElement !== this.scrub) this.scrub.value = f;
    this.frameLabel.textContent = `${p.first_frame + f} / ${p.first_frame + p.frames - 1}`;
  }
}

app.registerExtension({
  name: "DUGco.PassViewer",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "DUGcoPassViewer") return;
    ensureStyle();

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated?.apply(this, arguments);
      const viewer = (this.dugcoViewer = new Viewer(this));
      this.addDOMWidget("viewer", "dugco_pass_viewer", viewer.root, {
        serialize: false,
        hideOnZoom: false,
        getMinHeight: () => 300,
      });
      if (this.size[0] < 560 || this.size[1] < 620) this.setSize([Math.max(this.size[0], 560), Math.max(this.size[1], 620)]);
      return r;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (message) {
      onExecuted?.apply(this, arguments);
      const passes = message?.dugco_passes;
      if (!passes) return;
      this.properties = this.properties || {};
      this.properties.dugco_passes = passes;
      this.dugcoViewer?.load(passes, this.properties.dugco_pass);
    };

    // Reopening the workflow brings the last previews back, as long as ComfyUI has not been restarted.
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure?.apply(this, arguments);
      const passes = this.properties?.dugco_passes;
      if (passes?.length) this.dugcoViewer?.load(passes, this.properties.dugco_pass);
      return r;
    };

    const onRemoved = nodeType.prototype.onRemoved;
    nodeType.prototype.onRemoved = function () {
      this.dugcoViewer?.load([]);
      return onRemoved?.apply(this, arguments);
    };
  },
});
