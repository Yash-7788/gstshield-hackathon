import Lenis from "./vendor/lenis.mjs";
/* Pinned local Lenis build; the standalone export embeds the same version. */

const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)],
  cl = (v, a, b) => Math.min(b, Math.max(a, v)),
  ease = (t) => t * t * (3 - 2 * t),
  inr = (n) => "₹" + Math.round(n).toLocaleString("en-IN");
const GD = "#f2b01e",
  PAL = ["#b92d1b", "#f2b01e", "#0b5148", "#12255a", "#ff9f1c"];
const ARW =
  '<svg viewBox="0 0 16 16"><path d="M2 8h11M9 3l5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const arwI = () => {
  $$(".cb i").forEach((i) => (i.innerHTML = ARW));
  $$(".ul .arw").forEach(
    (i) => (i.innerHTML = ARW.replace("<svg", '<svg width="16" height="16"')),
  );
  $(".orb i").innerHTML = ARW.replace(
    'stroke-width="1.9"',
    'stroke-width="1.5"',
  );
};
function pt(n, r0, len, wid, rot, fill, str, sw) {
  let s = "";
  for (let j = 0; j < n; j++)
    s += `<g transform="rotate(${rot + (j * 360) / n})"><path d="M0 ${-r0}C${wid} ${-r0 - len * 0.3} ${wid} ${-r0 - len * 0.72} 0 ${-r0 - len}C${-wid} ${-r0 - len * 0.72} ${-wid} ${-r0 - len * 0.3} 0 ${-r0}Z" fill="${fill}" stroke="${str}" stroke-width="${sw}"/><path d="M0 ${-r0 - len * 0.2}V${-r0 - len * 0.7}" stroke="${str}" stroke-width="${sw * 0.7}" opacity=".6"/></g>`;
  return s;
}
function dots(n, r, rad, c) {
  let s = "";
  for (let i = 0; i < n; i++) {
    const a = (i * 2 * Math.PI) / n;
    s += `<circle cx="${(r * Math.cos(a)).toFixed(1)}" cy="${(r * Math.sin(a)).toFixed(1)}" r="${rad}" fill="${c}"/>`;
  }
  return s;
}
const outer = (s) =>
    pt(32, 78, 22, 6, 0, "none", s, 1) +
    `<circle r="74" fill="none" stroke="${s}" stroke-width=".8"/>` +
    dots(48, 104, 1.7, s),
  mid = (s, f) =>
    pt(16, 40, 40, 13, 0, f, s, 1.2) + pt(16, 40, 26, 8, 11.25, "none", s, 1),
  core = (s, f) =>
    pt(8, 8, 30, 10, 0, f, s, 1.2) + `<circle r="5" fill="${s}"/>`;
const lot = (s, f, g) => outer(s) + mid(s, f) + core(s, g),
  VB = "-110 -110 220 220",
  svg = (b) => `<svg viewBox="${VB}">${b}</svg>`;
function mand(n, sd) {
  let s = "";
  for (let k = 0; k < n; k++) {
    const r = 14 + k * 13,
      m = 6 + k * 3,
      w = 5 + k * 1.4,
      c = PAL[(k + sd) % 5];
    for (let j = 0; j < m; j++)
      s += `<path d="M0 ${-r}Q${w} ${-r - 8} 0 ${-r - 16}Q${-w} ${-r - 8} 0 ${-r}Z" fill="${c}" opacity="${k % 2 ? 0.92 : 0.78}" transform="rotate(${(j * 360) / m})"/>`;
    s += `<circle r="${r + 19}" fill="none" stroke="${PAL[(k + sd + 1) % 5]}" stroke-width="1.2" stroke-dasharray="1.5 4"/>`;
  }
  return s + '<circle r="9" fill="#f2b01e"/><circle r="4" fill="#b92d1b"/>';
}
["m1", "m2", "m3"].forEach((id, i) => {
  $("#" + id).setAttribute("viewBox", VB);
  const c = i == 1 ? "#f4ead2" : "#0b0a08";
  $("#" + id).innerHTML =
    mid(c, i == 1 ? "#0b0a08" : "#f2b01e") +
    core(c, i == 1 ? "#ff9f1c" : "#f4ead2");
});
$("#cm").setAttribute("viewBox", VB);
$("#cm").innerHTML = mand(6, 2);
// ---- morphing monogram: G -> S -> T, one stroke each, resampled to a common point count
const M = 72;
function rs(p) {
  const L = [0];
  for (let i = 1; i < p.length; i++)
    L.push(L[i - 1] + Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]));
  const T = L[L.length - 1],
    o = [];
  let j = 1;
  for (let k = 0; k < M; k++) {
    const d = (T * k) / (M - 1);
    while (j < p.length - 1 && L[j] < d) j++;
    const u = (d - L[j - 1]) / (L[j] - L[j - 1] || 1);
    o.push([
      p[j - 1][0] + (p[j][0] - p[j - 1][0]) * u,
      p[j - 1][1] + (p[j][1] - p[j - 1][1]) * u,
    ]);
  }
  return o;
}
const bz = (a, b, c, d, n) => {
  const o = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n,
      u = 1 - t;
    o.push(
      [0, 1].map(
        (k) =>
          u * u * u * a[k] +
          3 * u * u * t * b[k] +
          3 * u * t * t * c[k] +
          t * t * t * d[k],
      ),
    );
  }
  return o;
};
const G = [];
for (let i = 0; i <= 60; i++) {
  const a = -0.55 - (i / 60) * 5.25;
  G.push([0.78 * Math.cos(a), 0.78 * Math.sin(a)]);
}
G.push([0.12, 0.14]);
G.push([0.12, 0.14]);
const S = [
  ...bz([0.56, -0.66], [0.3, -0.98], [-0.62, -0.92], [-0.6, -0.36], 24),
  ...bz([-0.6, -0.36], [-0.58, 0.06], [0.6, -0.04], [0.6, 0.42], 24).slice(1),
  ...bz([0.6, 0.42], [0.6, 0.96], [-0.3, 1], [-0.58, 0.68], 24).slice(1),
];
const Tt = [
  [-0.72, -0.78],
  [0.72, -0.78],
  [0, -0.78],
  [0, 0.84],
];
const SH = [G, S, Tt].map(rs);
let cur = SH[0].map((p) => p.slice()),
  tgt = 0;
const lp = $("#lp");
function drawLogo() {
  lp.setAttribute(
    "d",
    cur
      .map((p, i) => (i ? "L" : "M") + p[0].toFixed(3) + " " + p[1].toFixed(3))
      .join(""),
  );
}
drawLogo();
$("#lgo").addEventListener("mouseenter", () => {
  tgt = (tgt + 1) % 3;
});
setInterval(() => {
  if (!document.hidden) tgt = (tgt + 1) % 3;
}, 3400);
// header menu
const mb = $("#mb"),
  mn = $("#mn");
let lenis = null;
function menu(on) {
  mb.classList.toggle("on", on);
  mn.classList.toggle("on", on);
  mb.setAttribute("aria-expanded", String(on));
  mn.setAttribute("aria-hidden", String(!on));
  mn.inert = !on;
  mb.setAttribute("aria-label", on ? "Close menu" : "Open menu");
  lenis && (on ? lenis.stop() : lenis.start());
  if (on) mn.querySelector("a")?.focus();
  else mb.focus();
}
mb.onclick = () => menu(!mb.classList.contains("on"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && mn.classList.contains("on")) menu(false);
});
// book
const P = [
  [
    "CGST Section 16(2)(aa)",
    "Missing GST record",
    "Your bill is absent or different in the GST statement. Track the tax under review and request a correction.",
    "Verify with CA",
  ],
  [
    "Income-tax Section 43B(h)",
    "Payment due soon",
    "A hold may conflict with micro or small supplier deadlines. Save the terms and ask your CA.",
    "Verify with CA",
  ],
  [
    "CGST Rule 37A",
    "Reclaim follow-up",
    "Keep the claim, reversal and later filing evidence together. A correction still needs review.",
    "Verify with CA",
  ],
  [
    "CGST Rule 48(4)",
    "Invoice reference",
    "Review IRN format and whether it applies. Format alone does not prove government verification.",
    "Verify with CA",
  ],
  [
    "CGST Rule 88D / DRC-01C",
    "Notice response",
    "Keep the notice, deadline and evidence together. Prepare a draft for your team to review.",
    "Verify with CA",
  ],
  [
    "CGST Section 16(4)",
    "Credit deadline",
    "Check unresolved bills before the applicable credit deadline. Similar invoice numbers need review.",
    "Verify with CA",
  ],
];
const face = (p, b) =>
  `<div class="fc pg ${b ? "b" : ""}"><div class="rf">${p[0]}</div><h3 class="rz">${p[1]}</h3><p>${p[2]}</p><span class="sm2">${p[3]}</span></div>`;
$("#bk").innerHTML =
  `<div class="fc pg base book-centered"><h3 class="rz book-end-title">Review it before you pay.</h3><p>The ledger closes here.</p></div>` +
  `<div class="lf"><div class="fc cov">${svg(lot(GD, "none", "none"))}<h3 class="rz">Invoice<br>ledger</h3><div>GST-Shield</div></div><div class="fc b pg book-centered"><h3 class="rz">Six checks, six pages</h3><p>Saved facts first. Review the rule with your CA.</p></div></div>` +
  [
    [0, 1],
    [2, 3],
    [4, 5],
  ]
    .map(([a, b]) => `<div class="lf">${face(P[a], 0)}${face(P[b], 1)}</div>`)
    .join("");
const lv = $$(".lf"),
  bk = $("#bk"),
  N = lv.length;
let bp = 0;
// ---- landing page: draw a live 8-fold rangoli with the cursor
const hero = $("#hero"),
  kc = $("#kc"),
  kx = kc.getContext("2d");
let W = 0,
  Hh = 0,
  cx = 0,
  cy = 0,
  pv = null,
  lastMove = 0,
  gt = 0,
  gp = null;
function rsz() {
  const d = Math.min(devicePixelRatio || 1, 2),
    stage = $("#rangoli-stage");
  W = stage.clientWidth;
  Hh = stage.clientHeight;
  kc.width = W * d;
  kc.height = Hh * d;
  kc.style.width = W + "px";
  kc.style.height = Hh + "px";
  kx.setTransform(d, 0, 0, d, 0, 0);
  cx = W * 0.5;
  cy = Hh * 0.5;
  pv = null;
  gp = null;
}
rsz();
addEventListener("resize", rsz);
const INK = ["#0b0a08", "#8a1c0f", "#f4ead2"];
function seg(a, b, w) {
  kx.lineWidth = w;
  kx.lineCap = "round";
  kx.strokeStyle = INK[Math.floor(performance.now() / 2600) % 3];
  for (let m = 0; m < 2; m++)
    for (let k = 0; k < 8; k++) {
      kx.save();
      kx.translate(cx, cy);
      kx.rotate((k * Math.PI) / 4);
      if (m) kx.scale(1, -1);
      kx.beginPath();
      kx.moveTo(a[0], a[1]);
      kx.lineTo(b[0], b[1]);
      kx.stroke();
      kx.restore();
    }
}
addEventListener("pointermove", (e) => {
  if (scrollY > innerHeight * 0.8) return;
  const r = kc.getBoundingClientRect();
  if (
    e.clientX < r.left ||
    e.clientX > r.right ||
    e.clientY < r.top ||
    e.clientY > r.bottom
  ) {
    pv = null;
    return;
  }
  const v = [(e.clientX - r.left - cx) * 0.5, (e.clientY - r.top - cy) * 0.5];
  if (pv) {
    const sp = Math.hypot(v[0] - pv[0], v[1] - pv[1]);
    seg(pv, v, cl(5 - sp * 0.08, 1.1, 4));
  }
  pv = v;
  lastMove = performance.now();
});
function ghost() {
  if (performance.now() - lastMove < 2200 || scrollY > innerHeight * 0.8) {
    gp = null;
    return;
  }
  gt += 0.016;
  const R = Math.min(W, Hh) * 0.4,
    v = [
      R * (0.62 * Math.cos(1.7 * gt) + 0.38 * Math.cos(2.9 * gt + 1)),
      R * (0.62 * Math.sin(1.3 * gt) + 0.38 * Math.sin(2.3 * gt + 2)),
    ];
  if (gp) seg(gp, v, 2.2);
  gp = v;
}
function kfade() {
  kx.globalCompositeOperation = "destination-out";
  kx.fillStyle = "rgba(0,0,0,.05)";
  kx.fillRect(0, 0, W, Hh);
  kx.globalCompositeOperation = "source-over";
}
// hero intro: black first, then the saffron circle spreads
function intro() {
  if (reduced) {
    hero.style.setProperty("--r", "150");
    document.body.classList.add("go");
    return;
  }
  const t0 = performance.now() + 700;
  (function f(t) {
    const x = cl((t - t0) / 2600, 0, 1);
    hero.style.setProperty("--r", (150 * ease(x)).toFixed(1));
    if (x > 0.5) document.body.classList.add("go");
    if (x < 1) requestAnimationFrame(f);
  })(performance.now());
}
document.readyState === "complete" ? intro() : addEventListener("load", intro);
const PIN = ["#lab", "#how", "#price", "#cta"].map($),
  ST = ["#hero", "#book", "#lab", "#how", "#price", "#cta"].map($),
  ring = $("#ring");
let cs = -1;
function tick() {
  const vh = innerHeight,
    y = scrollY;
  PIN.forEach((el) => {
    const f = cl(-el.getBoundingClientRect().top / vh, 0, 1);
    el.style.setProperty("--f", f.toFixed(3));
    el.style.setProperty("--r", (150 * ease(f)).toFixed(1));
  });
  const br = $("#book").getBoundingClientRect(),
    bf = cl(-br.top / (vh * 0.9), 0, 1),
    bs = $("#book");
  bs.style.setProperty("--r", (150 * ease(bf)).toFixed(1));
  bs.style.setProperty("--v", cl((bf - 0.42) * 2.4, 0, 1).toFixed(3));
  const p = cl((-br.top - vh * 0.9) / (br.height - vh * 1.9), 0, 1);
  bp = reduced ? p : bp + (p - bp) * 0.12;
  const q = Math.min(1, bp / 0.92) * N,
    w = bk.offsetWidth;
  lv.forEach((l, i) => {
    const t = cl(q - i, 0, 1),
      e = t < 0.5 ? 2 * t * t : 1 - 2 * (1 - t) * (1 - t);
    l.style.transform = `rotateY(${-180 * e}deg)`;
    l.style.zIndex = t > 0.5 ? 10 + i : 10 + N - i;
  });
  bk.style.transform = `translateX(${(Math.min(1, q) * w) / 2}px) rotateX(5deg)`;
  const hw = $("#how").getBoundingClientRect(),
    g = cl((-hw.top - vh * 0.9) / (hw.height - vh * 1.9), 0, 1);
  $("#rl").style.transform = `scaleY(${g})`;
  $$(".st").forEach((s, i) => {
    const k = cl(g * 3.4 - i * 1.05, 0, 1);
    s.style.opacity = 0.18 + 0.82 * k;
    s.style.transform = `translateX(${(1 - k) * 26}px)`;
    s.classList.toggle("on", k > 0.35);
  });
  $("#cm").style.setProperty(
    "--m",
    (
      0.28 * cl((-$("#cta").getBoundingClientRect().top / vh - 0.35) * 2, 0, 1)
    ).toFixed(3),
  );
  $("#cm").style.transform = `rotate(${y * 0.03}deg)`;
  ring.style.strokeDashoffset =
    1 - cl(y / (document.documentElement.scrollHeight - vh), 0, 1);
  let c = 0;
  ST.forEach((s, i) => {
    if (s.getBoundingClientRect().top < vh * 0.5) c = i;
  });
  if (c !== cs) {
    cs = c;
    tgt = c % 3;
  }
  let mv = 0;
  for (let k = 0; k < M; k++)
    for (let a = 0; a < 2; a++) {
      const d = SH[tgt][k][a] - cur[k][a];
      cur[k][a] += d * 0.075;
      mv += Math.abs(d);
    }
  if (mv > 0.003) drawLogo();
  if (y < vh && !reduced && !document.hidden) {
    kfade();
    ghost();
  }
  requestAnimationFrame(tick);
}
tick();
if (!reduced) {
  lenis = new Lenis({
    allowNestedScroll: true,
    duration: 1.25,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
  });
  (function raf(t) {
    lenis.raf(t);
    requestAnimationFrame(raf);
  })(0);
}
$$('a[href^="#"]').forEach((a) =>
  a.addEventListener("click", (e) => {
    const h = a.getAttribute("href"),
      el = $(h);
    if (!el) return;
    e.preventDefault();
    const offset = el.id === "how" ? 1.88 : el.id === "book" ? 1 : 1.02,
      y = h === "#hero" ? 0 : el.offsetTop + innerHeight * offset;
    menu(false);
    lenis
      ? lenis.scrollTo(y, { duration: 2.2 })
      : scrollTo({ top: y, behavior: reduced ? "instant" : "smooth" });
  }),
);
$$(".arch").forEach((a) => {
  a.addEventListener("pointermove", (e) => {
    const r = a.getBoundingClientRect(),
      x = (e.clientX - r.left) / r.width - 0.5,
      y = (e.clientY - r.top) / r.height - 0.5;
    a.style.transform = `rotateY(${x * 14}deg) rotateX(${-y * 10}deg)`;
  });
  a.addEventListener("pointerleave", () => (a.style.transform = ""));
});
// ---- reconciler driven by what you type
const key = (s) =>
  String(s)
    .trim()
    .toUpperCase()
    .replace(/[ /._-]/g, "");
let DATA = [
  ["INV-0942", "INV/0942"],
  ["A-0101", "A-0101"],
  ["SK/0033", ""],
  ["7781", "7781"],
  ["PUR-0450", "PUR/0450"],
  ["KT/22/118", "KT/22/811"],
];
const rowsEl = $("#rows");
rowsEl.innerHTML = DATA.map(
  (r, i) =>
    `<div class="rt" data-i="${i}"><input value="${r[0]}"><input value="${r[1]}" placeholder="not filed"><div class="sd"><i></i><span></span></div></div>`,
).join("");
const rg = $("#rg"),
  X = [],
  Y = [];
let h = "";
for (let i = 0; i < 100; i++) {
  const a = i * 2.39996,
    r = Math.sqrt(i + 0.5) * 10.6;
  X.push(r * Math.cos(a));
  Y.push(r * Math.sin(a));
  h += `<circle class="d" cx="${X[i].toFixed(1)}" cy="${Y[i].toFixed(1)}" r="4.4"/>`;
}
rg.innerHTML = h;
const D = [...rg.children],
  PM = [...Array(100).keys()].sort(
    (a, b) => Math.sin(a * 91.7) - Math.sin(b * 91.7),
  ),
  RANK = [];
PM.forEach((d, r) => (RANK[d] = r));
let CT = [0, 0, 0],
  TOT = 0,
  hasCompared = false,
  revealGeneration = 0;
const revealTimers = new Set();
const compareButton = $("#compare");
function clearReveal() {
  revealGeneration++;
  revealTimers.forEach(clearTimeout);
  revealTimers.clear();
  compareButton.disabled = false;
  compareButton.removeAttribute("aria-busy");
}
function recon(animate = true) {
  clearReveal();
  hasCompared = true;
  const generation = revealGeneration;
  const st = [];
  $$("#rows .rt").forEach((row) => {
    const [a, b] = row.querySelectorAll("input"),
      A = a.value.trim().toUpperCase(),
      B = b.value.trim().toUpperCase(),
      sd = row.querySelector(".sd"),
      t = sd.querySelector("span");
    let s = "";
    if (!A) {
      sd.className = "sd";
      t.textContent = "empty";
    } else if (!B) {
      s = "x";
      t.textContent = "missing on 2B";
    } else if (A === B) {
      s = "e";
      t.textContent = "exact match";
    } else if (key(A) && key(A) === key(B)) {
      s = "f";
      t.textContent = "similar format — review";
    } else {
      s = "x";
      t.textContent = "different invoice";
    }
    if (A) sd.className = "sd " + s;
    row.dataset.s = s;
    st.push(s);
  });
  const e = st.filter((s) => s === "e").length,
    f = st.filter((s) => s === "f").length,
    x = st.filter((s) => s === "x").length;
  CT = [e, f, x];
  TOT = e + f + x;
  [e, f, x].forEach((v, i) => ($("#n" + i).textContent = v));
  const n0 = Math.round((100 * e) / (TOT || 1)),
    n1 = Math.round((100 * f) / (TOT || 1));
  D.forEach((d) => d.setAttribute("class", "d"));
  const color = (i) => {
    const rank = RANK[i];
    return (
      "d" + (TOT ? (rank < n0 ? " c0" : rank < n0 + n1 ? " c1" : " c2") : "")
    );
  };
  const finished = () => {
    compareButton.disabled = false;
    compareButton.removeAttribute("aria-busy");
    $("#dl").textContent = TOT
      ? "Compared " +
        TOT +
        " sample invoices. Hover a dot, or click it to highlight its result."
      : "Add sample invoice numbers to compare.";
  };
  if (!animate || reduced || !TOT) {
    D.forEach((d, i) => d.setAttribute("class", color(i)));
    finished();
    return;
  }
  compareButton.disabled = true;
  compareButton.setAttribute("aria-busy", "true");
  $("#dl").textContent = "Comparing the sample records…";
  PM.forEach((index, position) => {
    const id = setTimeout(
      () => {
        revealTimers.delete(id);
        if (generation !== revealGeneration) return;
        D[index].setAttribute("class", color(index));
        if (position === PM.length - 1) finished();
      },
      position * 24 + (position >= 84 ? 450 : 0),
    );
    revealTimers.add(id);
  });
}
compareButton.textContent = "Compare these records";
const icon = document.createElement("i");
compareButton.append(icon);
rowsEl.addEventListener("input", () => {
  if (hasCompared) recon();
});
compareButton.onclick = () => recon();
$("#shuf").onclick = () => {
  const kinds = [
    0,
    1,
    2,
    ...Array.from({ length: 3 }, () => Math.floor(Math.random() * 3)),
  ];
  for (let i = kinds.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [kinds[i], kinds[j]] = [kinds[j], kinds[i]];
  }
  $$("#rows .rt").forEach((row, i) => {
    const n = String(1000 + Math.floor(Math.random() * 8000)),
      inputs = row.querySelectorAll("input");
    inputs[0].value = "INV-" + n;
    inputs[1].value =
      kinds[i] === 0
        ? "INV-" + n
        : kinds[i] === 1
          ? "INV/" + n
          : i % 2
            ? ""
            : "OTHER-" + n;
  });
  recon();
};
$$("#rows .sd span").forEach((span) => (span.textContent = "Not compared yet"));
$("#dl").textContent = "Start the comparison to reveal the result mix.";
addEventListener("pagehide", clearReveal);
const CN = ["exact match", "review suggestion", "needs checking"];
let bi = -1,
  bd = 99;
const tip = $("#tip");
const cat = (i) => {
  const c = D[i].classList;
  return c.contains("c0")
    ? 0
    : c.contains("c1")
      ? 1
      : c.contains("c2")
        ? 2
        : -1;
};
rg.addEventListener("pointermove", (e) => {
  const r = rg.getBoundingClientRect(),
    px = ((e.clientX - r.left) / r.width) * 224 - 112,
    py = ((e.clientY - r.top) / r.height) * 224 - 112;
  bd = 99;
  D.forEach((d, i) => {
    const dd = Math.hypot(X[i] - px, Y[i] - py);
    d.style.transform = `scale(${(1 + 1.5 * Math.pow(Math.max(0, 1 - dd / 32), 2)).toFixed(2)})`;
    if (dd < bd) {
      bd = dd;
      bi = i;
    }
  });
  if (bd < 8) {
    const c = cat(bi);
    tip.textContent =
      c < 0
        ? "Not compared yet"
        : `${CN[c]} · ${CT[c]} of ${TOT} invoices in your register`;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - 330) + "px";
    tip.style.top = e.clientY + 16 + "px";
    tip.style.opacity = 1;
  } else tip.style.opacity = 0;
});
rg.addEventListener("pointerleave", () => {
  D.forEach((d) => (d.style.transform = ""));
  tip.style.opacity = 0;
});
rg.addEventListener("click", () => {
  if (bd > 8 || bi < 0) return;
  const c = cat(bi),
    m = ["e", "f", "x"][c];
  if (c < 0) return;
  $$("#rows .rt").forEach((r) => {
    if (r.dataset.s === m) {
      r.classList.add("hl");
      setTimeout(() => r.classList.remove("hl"), 1400);
    }
  });
  $("#dl").textContent = `${CT[c]} of your ${TOT} invoices are ${CN[c]}.`;
});
// ---- split calculator: every number follows the inputs
const S2 = { r: 0.18, v: "no" };
function calc() {
  const raw = Number($("#amt").value),
    B = Number.isFinite(raw) ? Math.min(1e12, Math.max(0, raw)) : 0,
    g = B * S2.r,
    d = +$("#days").value;
  $("#dv").textContent = d;
  const O = [
    [
      "Hold the payment",
      "Review timing",
      `Before keeping ${inr(B + g)} unpaid, check supplier deadlines and terms with your CA.`,
    ],
    [
      "Pay the full invoice",
      inr(B + g),
      S2.v === "yes"
        ? "Compare the received GST evidence and review the payment facts before approving."
        : `${inr(g)} tax needs GST evidence review. It is not a confirmed loss.`,
    ],
    [
      "Review a part payment",
      inr(B),
      `${inr(B)} goods; ${inr(g)} tax remains for review. Agree terms and approve before acting. No escrow is created.`,
    ],
  ];
  $("#opts").innerHTML = O.map(
    (o, i) =>
      `<div class="opt ${i == 2 ? "best" : ""}"><span class="opt-title">${o[0]}</span><b>${o[1]}</b><span>${o[2]}</span></div>`,
  ).join("");
  const tot = B + g || 1;
  $("#b1").style.flex = (B / tot) * 100;
  $("#b2").style.flex = (g / tot) * 100;
  $("#b1").textContent = "";
  $("#b2").textContent = "";
  $("#b1").style.background = "var(--pea)";
  $("#b2").style.background = "var(--ver)";
  $("#base-label").textContent = "Goods " + inr(B);
  $("#tax-label").textContent = "Tax " + inr(g);
  $("#payment-bar").setAttribute(
    "aria-label",
    `Goods ${inr(B)}; tax ${inr(g)}`,
  );
}

$("#amt").oninput = $("#days").oninput = calc;
$$("#rate .chip").forEach(
  (b) =>
    (b.onclick = () => {
      $$("#rate .chip").forEach((x) => x.classList.toggle("on", x === b));
      S2.r = +b.dataset.r;
      calc();
    }),
);
$$("#vf .chip").forEach(
  (b) =>
    (b.onclick = () => {
      $$("#vf .chip").forEach((x) => x.classList.toggle("on", x === b));
      S2.v = b.dataset.v;
      calc();
    }),
);
calc();
function ir() {
  const v = $("#irn").value.trim(),
    ok = /^[a-f0-9]{64}$/i.test(v),
    o = $("#io"),
    bad = v.replace(/[a-f0-9]/gi, "").length;
  $("#ib").style.flex = (Math.min(v.length, 64) / 64) * 100;
  $("#ib").style.background = ok
    ? "var(--pea)"
    : bad
      ? "var(--ver)"
      : "var(--mg)";
  o.className = "out " + (v ? (ok ? "ok" : "no") : "");
  o.textContent = !v
    ? "Waiting for an IRN."
    : ok
      ? "Expected reference format. Authenticity and applicability still need review."
      : bad
        ? `${bad} character${bad > 1 ? "s are" : " is"} not hexadecimal. Reference format needs review; this example cannot approve payment.`
        : `${v.length} of 64 characters so far.`;
}
$("#irn").oninput = ir;
ir();
$("#irs").onclick = () => {
  $("#irn").value = [...Array(64)]
    .map(() => "0123456789abcdef"[(Math.random() * 16) | 0])
    .join("");
  ir();
};
$$("#tabs button").forEach(
  (b) =>
    (b.onclick = () => {
      $$("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
      $$(".card>.p").forEach((p, i) =>
        p.classList.toggle("on", i == b.dataset.t),
      );
    }),
);
arwI();

// Indicate overflow only while more content remains below in a viewport panel.
const panelContents = PIN.map((section) => section.querySelector(".inner"));
function updatePanelHints() {
  panelContents.forEach((p) =>
    p
      .closest(".stick")
      .classList.toggle(
        "has-overflow",
        p.scrollHeight > p.clientHeight + 2 &&
          p.scrollTop + p.clientHeight < p.scrollHeight - 3,
      ),
  );
}
panelContents.forEach((p) => {
  p.tabIndex = 0;
  p.setAttribute("role", "region");
  p.setAttribute(
    "aria-label",
    p.closest("section").querySelector("h2").textContent.trim(),
  );
  p.addEventListener("scroll", updatePanelHints, { passive: true });
});
if ("ResizeObserver" in window) {
  const observer = new ResizeObserver(updatePanelHints);
  panelContents.forEach((p) => {
    observer.observe(p);
    p.querySelectorAll(".card,.tiers").forEach((e) => observer.observe(e));
  });
}
updatePanelHints();

const portalDialog = document.querySelector("#portal-dialog");
document.querySelector("#portal-open")?.addEventListener("click", () => {
  portalDialog.showModal();
  lenis?.stop();
});
document
  .querySelector("#portal-close")
  ?.addEventListener("click", () => portalDialog.close());
portalDialog?.addEventListener("close", () => lenis?.start());
