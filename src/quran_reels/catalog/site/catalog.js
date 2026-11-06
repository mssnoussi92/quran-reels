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
  const form = document.getElementById("od-form");
  if (form) {
    const q = new URLSearchParams(location.search);
    for (const name of ["reciter", "background"]) {
      const v = q.get(name);
      if (v && form.elements[name].querySelector(`option[value="${CSS.escape(v)}"]`)) form.elements[name].value = v;
    }
    const warn = form.querySelector(".od-warn");
    const ayahs = () => Number(form.elements.surah.selectedOptions[0].dataset.ayahs);
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
    form.addEventListener("change", update);
    form.elements.from.addEventListener("focus", () => { form.elements.range.value = "part"; });
    form.elements.to.addEventListener("focus", () => { form.elements.range.value = "part"; });
    update();
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const f = form.elements, n = ayahs(), s = f.surah.value;
      let passage = s;
      if (f.range.value === "part") {
        const a = Math.max(1, Math.min(n, Number(f.from.value) || 1));
        const b = Math.max(a, Math.min(n, Number(f.to.value) || a));
        passage = `${s}:${a}-${b}`;
      }
      const platforms = [...form.querySelectorAll('input[name="platform"]:checked')].map((x) => x.value);
      if (!platforms.length) { warn.textContent = "Choisis au moins une plateforme."; warn.hidden = false; return; }
      const h = JSON.parse(form.dataset.headings);
      const rec = f.reciter.selectedOptions[0];
      const body = [`### ${h.reciter}\n\n${f.reciter.value}`, `### ${h.passage}\n\n${passage}`,
                    `### ${h.background}\n\n${f.background.value}`,
                    `### ${h.platforms}\n\n${platforms.join(", ")}`].join("\n\n")
                   + `\n\n---\n${form.dataset.footer}\n`;
      const who = f.reciter.value === "auto" ? "auto" : rec.textContent;
      const title = `${form.dataset.prefix} : ${passage} · ${who}`;
      const url = `${form.dataset.newIssue}?` + new URLSearchParams({ title, body, labels: "on-demand" });
      location.href = url;
    });
    if (location.hash === "#on-demand" && (q.get("reciter") || q.get("background"))) {
      document.getElementById("on-demand").scrollIntoView();
    }
  }
})();

