// Shared by every scene: inserted after the scene's #version line.
precision highp float;
uniform vec2 u_res;       // pixels
uniform float u_time;     // seconds
out vec4 fragColor;

// Hashes without sine (David Hoskins, "Hash without Sine", MIT).
float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * .1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
vec3 hash33(vec3 p3) {
  p3 = fract(p3 * vec3(.1031, .1030, .0973));
  p3 += dot(p3, p3.yxz + 33.33);
  return -1. + 2. * fract((p3.xxy + p3.yxx) * p3.zyx);
}

// Gradient noise, about -0.7..0.7, smooth (quintic).
float gnoise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  vec3 u = f * f * f * (f * (f * 6. - 15.) + 10.);
  #define G(o) dot(hash33(i + o), f - o)
  return mix(mix(mix(G(vec3(0, 0, 0)), G(vec3(1, 0, 0)), u.x),
                 mix(G(vec3(0, 1, 0)), G(vec3(1, 1, 0)), u.x), u.y),
             mix(mix(G(vec3(0, 0, 1)), G(vec3(1, 0, 1)), u.x),
                 mix(G(vec3(0, 1, 1)), G(vec3(1, 1, 1)), u.x), u.y), u.z);
  #undef G
}

// Fractal noise, about 0..1.
float fbm(vec3 p, int octaves) {
  float s = 0., a = .5;
  for (int k = 0; k < 8; k++) {
    if (k >= octaves) break;
    s += a * gnoise(p);
    p = p * 2.03 + vec3(11.7, 5.3, 2.9);
    a *= .5;
  }
  return .5 + s;
}

// Twinkling stars on a jittered grid: p in screen heights, density 0..1.
vec3 stars(vec2 p, float t, float scale, float density, float seed) {
  vec2 g = p * scale;
  vec2 id = floor(g), f = fract(g);
  float h = hash12(id + seed);
  if (h > density) return vec3(0.);
  vec2 at = .2 + .6 * vec2(hash12(id + seed + 7.1), hash12(id + seed + 3.3));
  float d = length((f - at) / scale) * u_res.y;            // distance in pixels
  float size = .6 + 1.4 * pow(hash12(id + seed + 1.9), 4.);
  float twinkle = .55 + .45 * sin(t * (1.2 + 2.8 * hash12(id + 5.)) + 40. * h);
  vec3 tint = mix(vec3(1., .93, .82), vec3(.85, .9, 1.), hash12(id + 2.2));
  return tint * twinkle * exp(-d * d / (size * size)) * (.4 + .6 * hash12(id + 8.4));
}

float luma(vec3 c) { return dot(c, vec3(.2126, .7152, .0722)); }

vec3 hex(float r, float g, float b) { return vec3(r, g, b) / 255.; }

// 8-bit output with a little dithering, against banding in the dark gradients.
void finish(vec3 col) {
  float d = hash12(gl_FragCoord.xy + fract(u_time * 7.13) * 91.) - .5;
  fragColor = vec4(clamp(col + d / 255., 0., 1.), 1.);
}
