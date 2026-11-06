// Catalogue: plays the recitation samples from their source, the clip previews while they are
// on screen, and draws the generated scenes live (their own shaders). Nothing is sent anywhere.
(() => {
  "use strict";

  // ---- samples: one player, files one after the other, a missing file is skipped ------------
  const audio = document.getElementById("player");
  let current = null;           // {button, urls, i}

  function setButton(button, on, text) {
    button.classList.toggle("on", on);
    button.querySelector(".ico").textContent = on ? "■" : "▶";
    button.lastChild.textContent = " " + text;
  }

  function stop() {
    if (!current) return;
    audio.pause();
    setButton(current.button, false, current.label);
    current = null;
  }

  function next() {
    if (!current) return;
    current.i += 1;
    if (current.i >= current.urls.length) { stop(); return; }
    const n = current.urls.length;
    setButton(current.button, true, n > 1 ? `${current.i + 1}/${n}` : "Arrêter");
    audio.src = current.urls[current.i];
    // A file that does not load fires "error" (handled below); only a refused play stops.
    audio.play().catch((e) => { if (e.name === "NotAllowedError") stop(); });
  }

  audio.addEventListener("ended", next);
  audio.addEventListener("error", () => { if (current) next(); });

  document.querySelectorAll("button.play").forEach((button) => {
    button.addEventListener("click", () => {
      const mine = current && current.button === button;
      stop();
      if (mine) return;
      current = { button, urls: JSON.parse(button.dataset.urls), i: -1,
                  label: button.lastChild.textContent.trim() };
      setButton(button, true, "…");
      next();
    });
  });

  // ---- clip previews: play while visible ------------------------------------------------------
  const seen = new IntersectionObserver((entries) => {
    for (const e of entries) {
      const v = e.target;
      if (e.isIntersecting) v.play().catch(() => {});
      else v.pause();
    }
  }, { rootMargin: "100px" });
  document.querySelectorAll("video.clip").forEach((v) => seen.observe(v));

  // ---- generated scenes: the renderer's own shader, drawn small ------------------------------
  let shaders = {};
  try { shaders = JSON.parse(document.getElementById("shaders").textContent); } catch (e) {}
  const VERT = "#version 300 es\nin vec2 p; void main() { gl_Position = vec4(p, 0., 1.); }";
  const scenes = [];

  function setup(canvas) {
    const gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: true });
    const src = shaders[canvas.dataset.scene];
    if (!gl || !src) return fail(canvas, "WebGL 2 indisponible");
    const sh = (type, text) => {
      const s = gl.createShader(type); gl.shaderSource(s, text); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    try {
      const prog = gl.createProgram();
      gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
      gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, src));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);
      gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(prog, "p");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      const u = (n) => gl.getUniformLocation(prog, n);
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(u("u_res"), canvas.width, canvas.height);
      gl.uniform1f(u("u_loop"), 30);
      gl.uniform1f(u("u_fade"), 5);
      const scene = { canvas, gl, time: u("u_time"), t0: performance.now(), on: false };
      draw(scene, 6);           // a first frame, even before it is on screen
      scenes.push(scene);
      return scene;
    } catch (e) {
      return fail(canvas, "scène non affichable");
    }
  }

  function fail(canvas, text) {
    const div = document.createElement("div");
    div.className = "noprev";
    div.textContent = text;
    canvas.replaceWith(div);
    return null;
  }

  function draw(scene, t) {
    scene.gl.uniform1f(scene.time, t % 30);
    scene.gl.drawArrays(scene.gl.TRIANGLES, 0, 3);
  }

  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function frame(now) {
    for (const s of scenes) if (s.on) draw(s, 6 + (now - s.t0) / 1000);
    if (!reduce) requestAnimationFrame(frame);
  }
  const watch = new IntersectionObserver((entries) => {
    for (const e of entries) {
      const s = scenes.find((x) => x.canvas === e.target);
      if (s) s.on = e.isIntersecting;
    }
  });
  document.querySelectorAll("canvas.scene").forEach((c) => {
    const s = setup(c);
    if (s) watch.observe(c);
  });
  if (scenes.length && !reduce) requestAnimationFrame(frame);

  // ---- on demand: the form builds a pre-filled issue (docs/on-demand.md), nothing else ------
  // Before the issue exists it shows the chosen ayahs (Arabic and translation read from
  // Quran.com, as the reels are) and the Muyassar's meanings to tick (surahs/SSS.json, written
  // by the catalogue build with the preview's own code and numbering). The workflow checks
  // everything again: this page only helps choosing.
  const form = document.getElementById("od-form");
  if (form) {
    const q = new URLSearchParams(location.search);
    for (const name of ["reciter", "background"]) {
      const v = q.get(name);
      if (v && form.elements[name].querySelector(`option[value="${CSS.escape(v)}"]`)) form.elements[name].value = v;
    }
    const warn = form.querySelector(".od-warn");
    const panel = document.getElementById("od-passage");
    const maxPer = Number(form.dataset.maxPerAyah) || 2;
    const SHOWN_MAX = 30;                 // ayahs drawn; a longer range is over 90 s anyway
    const AR = "٠١٢٣٤٥٦٧٨٩";
    const arabic = (n) => String(n).replace(/\d/g, (d) => AR[d]);
    const cache = {};
    let words = { touched: false, picked: new Set(), key: "" };

    const ayahs = () => Number(form.elements.surah.selectedOptions[0].dataset.ayahs);
    function range() {
      const n = ayahs();
      if (form.elements.range.value !== "part") return [1, n];
      const a = Math.max(1, Math.min(n, Number(form.elements.from.value) || 1));
      return [a, Math.max(a, Math.min(n, Number(form.elements.to.value) || a))];
    }
    function el(tag, attrs = {}, text = "") {
      const x = document.createElement(tag);
      for (const [k, v] of Object.entries(attrs)) x.setAttribute(k, v);
      if (text) x.textContent = text;
      return x;
    }
    const clean = (t) => t.replace(/<sup\b[^>]*>[\s\S]*?<\/sup>/gi, "").replace(/<[^>]+>/g, "")
      .replace(/\s+/g, " ").trim();

    async function surah(s) {
      if (cache[s]) return cache[s];
      const api = form.dataset.api, tid = form.dataset.tid;
      const pad = String(s).padStart(3, "0");
      const json = (u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);
      const [v, t, d] = await Promise.all([
        json(`${api}/quran/verses/uthmani?chapter_number=${s}`),
        tid ? json(`${api}/quran/translations/${tid}?chapter_number=${s}&fields=verse_key`) : null,
        json(`surahs/${pad}.json`)]);
      const text = {}, tr = {};
      for (const x of (v && v.verses) || []) text[Number(x.verse_key.split(":")[1])] = x.text_uthmani;
      ((t && t.translations) || []).forEach((x, i) => {
        tr[x.verse_key ? Number(x.verse_key.split(":")[1]) : i + 1] = clean(x.text || "");
      });
      return (cache[s] = { text, tr, data: d });
    }

    function wordsValue() {
      if (!words.touched) return "auto";
      const n = [...words.picked].sort((a, b) => a - b);
      return n.length ? n.join(", ") : "aucun";
    }

    let drawing = 0;
    async function draw() {
      const ticket = ++drawing;
      const s = Number(form.elements.surah.value), n = ayahs();
      const [a, b] = range();
      const key = `${s}:${a}-${b}`;
      if (key !== words.key) words = { touched: false, picked: new Set(), key };
      panel.replaceChildren(el("p", { class: "small muted" }, "Chargement des ayahs…"));
      const { text, tr, data } = await surah(s);
      if (ticket !== drawing) return;          // the choice changed meanwhile
      panel.replaceChildren();

      if (data) {                               // whole sentences only (rule 4)
        const ends = new Set(data.ends);
        const okStart = a === 1 || ends.has(a - 1), okEnd = b === n || ends.has(b);
        if (!okStart || !okEnd) {
          let a2 = a, b2 = b;
          while (a2 > 1 && !ends.has(a2 - 1)) a2--;
          while (b2 < n && !ends.has(b2)) b2++;
          const p = el("p", { class: "notice small" });
          p.append(`${key} coupe une phrase (${!okStart ? `${s}:${a - 1} ne la finit pas` : `${s}:${b} ne la finit pas`}) : il sera refusé. `);
          const fix = el("button", { type: "button", class: "link" }, `Prendre ${s}:${a2}-${b2}`);
          fix.addEventListener("click", () => {
            form.elements.range.value = "part"; form.elements.from.value = a2; form.elements.to.value = b2; draw();
          });
          p.append(fix);
          panel.append(p);
        }
      }
      const meanings = data && data.meanings;
      const tooLong = b - a + 1 > SHOWN_MAX;
      const head = el("p", { class: "small muted" });
      head.textContent = !meanings
        ? "Sens du Muyassar pas encore chargés pour cette sourate : tu les choisiras après l'aperçu (/mots)."
        : tooLong ? `${b - a + 1} ayahs : bien plus de 90 s, choisis une plage plus courte.`
          : `Coche les mots à surligner et expliquer (sens du Muyassar, ${maxPer} au plus par ayah). Cochés : les règles habituelles.`;
      panel.append(head);

      let num = 0;
      for (let i = a; i <= Math.min(b, a + SHOWN_MAX - 1); i++) {
        const box = el("div", { class: "od-ayah" });
        box.append(el("p", { class: "ar", lang: "ar" }, `${text[i] || ""} ﴿${arabic(i)}﴾`));
        if (tr[i]) box.append(el("p", { class: "tr" }, `${i}. ${tr[i]}`));
        for (const m of (meanings && !tooLong && meanings[String(i)]) || []) {
          num += 1;
          const row = el("label", { class: "mean" + (m.usable ? "" : " off") });
          const c = el("input", { type: "checkbox", value: String(num), "data-ayah": String(i) });
          c.checked = words.touched ? words.picked.has(num) : m.usable && m.auto;
          c.disabled = !m.usable;
          const t = el("span");
          t.append(el("span", { class: "small muted" }, `n° ${num} · `), el("span", { class: "w", lang: "ar" }, m.word));
          if (m.usable) t.append(el("span", { class: "g", lang: "ar" }, m.gloss));
          else t.append(el("span", { class: "small muted" }, ` — ${m.why}`));
          row.append(c, t);
          box.append(row);
        }
        panel.append(box);
      }
      if (tooLong) panel.append(el("p", { class: "small muted" }, `… ${b - a + 1 - SHOWN_MAX} ayahs de plus.`));
    }

    panel.addEventListener("change", (e) => {
      const c = e.target;
      if (!(c instanceof HTMLInputElement) || c.type !== "checkbox") return;
      const same = panel.querySelectorAll(`input[data-ayah="${c.dataset.ayah}"]:checked`);
      if (c.checked && same.length > maxPer) {
        c.checked = false;
        warn.textContent = `${maxPer} mots expliqués au plus par ayah (la place à l'écran).`; warn.hidden = false;
        return;
      }
      words.touched = true;
      words.picked = new Set([...panel.querySelectorAll("input[type=checkbox]:checked")].map((x) => Number(x.value)));
      update();
    });

    function update() {
      const n = ayahs();
      for (const k of ["from", "to"]) { form.elements[k].max = n; }
      if (Number(form.elements.to.value) > n) form.elements.to.value = n;
      const rec = form.elements.reciter.selectedOptions[0];
      const yt = form.querySelector('input[value="youtube"]');
      const msg = [];
      if (yt.checked && rec.dataset.youtube === "0") {
        msg.push(`YouTube sera retiré : ${rec.textContent} y est revendiqué par Content ID (les autres plateformes continuent).`);
      }
      warn.textContent = msg.join(" "); warn.hidden = !msg.length;
    }
    let timer = 0;
    form.addEventListener("change", (e) => {
      if (e.target.closest && e.target.closest("#od-passage")) return;   // its own handler
      update();
      if (["surah", "range", "from", "to"].includes(e.target.name)) draw();
    });
    form.addEventListener("input", (e) => {
      if (["from", "to"].includes(e.target.name)) { clearTimeout(timer); timer = setTimeout(draw, 500); }
    });
    form.elements.from.addEventListener("focus", () => { form.elements.range.value = "part"; });
    form.elements.to.addEventListener("focus", () => { form.elements.range.value = "part"; });
    update();
    draw();
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const f = form.elements, s = f.surah.value, n = ayahs();
      const [a, b] = range();
      const passage = f.range.value === "part" ? `${s}:${a}-${b}` : s;
      const platforms = [...form.querySelectorAll('input[name="platform"]:checked')].map((x) => x.value);
      if (!platforms.length) { warn.textContent = "Choisis au moins une plateforme."; warn.hidden = false; return; }
      const h = JSON.parse(form.dataset.headings);
      const rec = f.reciter.selectedOptions[0];
      const body = [`### ${h.reciter}\n\n${f.reciter.value}`, `### ${h.passage}\n\n${passage}`,
                    `### ${h.background}\n\n${f.background.value}`,
                    `### ${h.platforms}\n\n${platforms.join(", ")}`,
                    `### ${h.words}\n\n${wordsValue()}`].join("\n\n")
                   + `\n\n---\n${form.dataset.footer}\n`;
      const who = f.reciter.value === "auto" ? "auto" : rec.textContent;
      const title = `${form.dataset.prefix} : ${passage} · ${who}`;
      location.href = `${form.dataset.newIssue}?` + new URLSearchParams({ title, body, labels: "on-demand" });
    });
    if (location.hash === "#on-demand" && (q.get("reciter") || q.get("background"))) {
      document.getElementById("on-demand").scrollIntoView();
    }
  }
})();

