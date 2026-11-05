"""Generated backgrounds: a nature scene drawn by a GLSL shader, in the Chromium we already use.

Each scene (`<name>.frag` next to this file) defines `vec3 scene(vec2 uv, float t)`: the colour
of a pixel (uv in 0..1, y up) at t seconds. It is drawn in headless Chromium (WebGL 2, software
rendering on GitHub's runners); the page posts each frame's raw pixels to a small local HTTP
server, which feeds ffmpeg.

The clip is a seamless loop: its first `fade` seconds blend the scene at t + loop into the
scene at t, so the last frame runs into the first one. The compositor loops it under the
video. Drawn once, cached in .cache/backgrounds/ under a hash of the shader.

No stock footage, no licence, no people or animals by construction.
"""

from __future__ import annotations

import hashlib
import http.server
import json
import subprocess
import threading
from pathlib import Path
from typing import IO

from quran_reels.config import Config

HERE = Path(__file__).parent
HEAD = HERE / "common.glsl"
TAIL = """
uniform float u_loop;     // seconds; 0: no loop
uniform float u_fade;     // seconds blended at the start of the loop
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec3 col = scene(uv, u_time);
  if (u_loop > 0. && u_time < u_fade)
    col = mix(scene(uv, u_time + u_loop), col, smoothstep(0., 1., u_time / u_fade));
  finish(col);
}
"""

_PAGE = """<!doctype html><html><body style="margin:0;background:#000">
<canvas id="c" width="{w}" height="{h}"></canvas>
<script>
const FRAG = {frag};
const c = document.getElementById('c');
const gl = c.getContext('webgl2', {{preserveDrawingBuffer: true, antialias: false}});
function shader(type, src) {{
  const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
  return s;
}}
const prog = gl.createProgram();
gl.attachShader(prog, shader(gl.VERTEX_SHADER,
  '#version 300 es\\nin vec2 p; void main() {{ gl_Position = vec4(p, 0., 1.); }}'));
gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FRAG));
gl.linkProgram(prog);
if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
gl.useProgram(prog);
gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
const loc = gl.getAttribLocation(prog, 'p');
gl.enableVertexAttribArray(loc);
gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
const u = n => gl.getUniformLocation(prog, n);
gl.uniform2f(u('u_res'), {w}, {h});
gl.uniform1f(u('u_loop'), {loop});
gl.uniform1f(u('u_fade'), {fade});
const buf = new Uint8Array({w} * {h} * 4);
window.run = async (times) => {{
  for (const t of times) {{
    gl.uniform1f(u('u_time'), t);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.readPixels(0, 0, {w}, {h}, gl.RGBA, gl.UNSIGNED_BYTE, buf);
    const r = await fetch('/frame', {{method: 'POST', body: buf}});
    if (!r.ok) throw new Error('frame refused: ' + r.status);
  }}
  return times.length;
}};
</script></body></html>"""


def names() -> list[str]:
    return sorted(p.stem for p in HERE.glob("*.frag"))


def source(name: str) -> str:
    frag = HERE / f"{name}.frag"
    if not frag.is_file():
        raise ValueError(f"unknown scene {name!r} (scenes: {', '.join(names())})")
    head, body = frag.read_text(encoding="utf-8").split("\n", 1)
    if not head.startswith("#version"):
        raise ValueError(f"{frag.name}: the first line must be #version")
    return f"{head}\n{HEAD.read_text(encoding='utf-8')}\n{body}\n{TAIL}"


class _Server(http.server.HTTPServer):
    page: bytes
    sink: IO[bytes]
    frame_bytes: int
    frames: int = 0


class _Handler(http.server.BaseHTTPRequestHandler):
    server: _Server

    def do_GET(self) -> None:
        self._reply(200, self.server.page, "text/html; charset=utf-8")

    def do_POST(self) -> None:
        n = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(n)
        if n != self.server.frame_bytes:
            self._reply(400, b"wrong frame size", "text/plain")
            return
        self.server.sink.write(data)
        self.server.frames += 1
        self._reply(204, b"", "text/plain")

    def _reply(self, code: int, body: bytes, kind: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def render(cfg: Config, name: str, loop: float = 30.0, fade: float = 5.0, width: int = 540,
           height: int = 960, dest: Path | None = None) -> Path:
    """The scene as a seamless MP4 loop of `loop` seconds, scaled up to the video size by the
    compositor (half resolution is enough for skies, clouds and water, and 4× faster).
    loop=0 with fade=N renders N seconds without looping (previews)."""
    fps = cfg.video["fps"]
    frag = source(name)
    seconds = loop or fade
    digest = hashlib.sha1(f"{frag}|{width}x{height}|{fps}|{loop}|{fade}".encode()).hexdigest()
    if dest is None:
        dest = cfg.cache / "backgrounds" / f"scene-{name}-{digest[:10]}.mp4"
    if dest.is_file():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}")

    from playwright.sync_api import sync_playwright

    encoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-vf", "vflip",
         "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p",
         "-g", str(fps * 2), "-movflags", "+faststart", "-f", "mp4", str(tmp)],
        stdin=subprocess.PIPE)
    assert encoder.stdin
    server = _Server(("127.0.0.1", 0), _Handler)
    server.page = _PAGE.format(w=width, h=height, frag=json.dumps(frag), loop=float(loop),
                               fade=float(fade)).encode()
    server.sink = encoder.stdin
    server.frame_bytes = width * height * 4
    threading.Thread(target=server.serve_forever, daemon=True).start()
    total = round(seconds * fps)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--enable-unsafe-swiftshader"])
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
            if errors:
                raise RuntimeError(f"scene {name}: {errors[0]}")
            page.evaluate("ts => run(ts)", [f / fps for f in range(total)])
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        encoder.stdin.close()
    if encoder.wait() != 0 or server.frames != total:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"scene {name}: {server.frames}/{total} frames encoded")
    tmp.replace(dest)
    return dest
