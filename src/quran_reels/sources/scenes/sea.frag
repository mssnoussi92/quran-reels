#version 300 es
// Calm sea at golden hour: the sun low on the right, a glittering path towards the viewer,
// a slow swell, soft clouds. A small ray tracer: each pixel below the horizon hits the
// water plane, whose waves reflect the sky.

const float HORIZON = .27;
const float FOCAL = 1.1;
const vec2 SUN = vec2(.87, HORIZON + .04);      // on screen, right of the credits line

vec3 sky(vec3 r, vec3 sunDir) {
  float h = clamp(r.y / length(r.xz) / .8, 0., 1.);   // 0 at the horizon
  vec3 c = mix(hex(236., 164., 112.), hex(150., 112., 128.), smoothstep(0., .1, h));
  c = mix(c, hex(62., 78., 124.), smoothstep(.08, .42, h));
  c = mix(c, hex(20., 32., 70.), smoothstep(.4, 1., h));
  float sd = max(dot(normalize(r), sunDir), 0.);
  return c + hex(255., 180., 110.) * (.45 * pow(sd, 400.) + .16 * pow(sd, 18.));
}

float swell(vec2 q, float t, int octaves) {
  // Crests parallel to the shore, rolling towards the viewer, slowly changing.
  // A second, crossing wave train breaks up the lines.
  vec2 c = mat2(.8, -.6, .6, .8) * q;
  return fbm(vec3(q * vec2(.17, .42) + vec2(t * .015, t * .14), t * .06), octaves)
       + .35 * fbm(vec3(c * vec2(.5, .9) + vec2(-t * .05, t * .2), 7.3), max(octaves - 2, 1));
}

vec3 scene(vec2 uv, float t) {
  float aspect = u_res.x / u_res.y;
  vec3 sunDir = normalize(vec3((SUN.x - .5) * aspect, SUN.y - HORIZON, FOCAL));
  vec3 v = normalize(vec3((uv.x - .5) * aspect, uv.y - HORIZON, FOCAL));
  vec2 p = vec2(uv.x * aspect, uv.y);

  if (v.y >= 0.) {
    vec3 col = sky(v, sunDir);
    float ds = length((uv - SUN) * vec2(aspect, 1.));
    col += hex(255., 232., 190.) * smoothstep(.019, .015, ds);
    // Soft clouds, long and thin, warm near the sun.
    float band = smoothstep(HORIZON + .02, HORIZON + .1, uv.y) * (1. - smoothstep(.62, .85, uv.y));
    if (band > .01) {
      vec3 q = vec3(p * vec2(1.2, 6.5) + vec2(t * .008, 0.), t * .01) * 1.3;
      float n = fbm(q, 6);
      float cover = smoothstep(.55, .78, n) * band;
      if (cover > 0.) {
        float lit = clamp((fbm(q + vec3(-.06, -.1, 0.), 4) - n) * 7. + .4, 0., 1.);
        vec3 cloud = mix(hex(112., 104., 136.), hex(255., 196., 150.), lit);
        cloud += hex(255., 190., 130.) * .45 * exp(-ds / .12);
        col = mix(col, cloud, cover * .7);
      }
    }
    return col;
  }

  // Below the horizon: the water plane, one unit under the eye.
  float vy = min(v.y, -.0015);
  float dist = 1. / -vy;
  vec2 q = vec2(v.x, v.z) * dist;
  int oct = dist < 6. ? 5 : (dist < 20. ? 4 : 3);
  float e = .04 * (1. + dist * .2);
  float h0 = swell(q, t, oct);
  float hx = (swell(q + vec2(e, 0.), t, oct) - h0) / e;
  float hz = (swell(q + vec2(0., e), t, oct) - h0) / e;
  float steep = .55 / (1. + dist * .05);
  vec3 n = normalize(vec3(-hx * steep, 1., -hz * steep));
  vec3 r = reflect(v, n);
  r.y = abs(r.y) + .001;
  float fres = .02 + .98 * pow(1. - max(dot(n, -v), 0.), 5.);
  vec3 col = mix(hex(8., 24., 44.), sky(r, sunDir), clamp(fres, 0., 1.));
  float sd = max(dot(r, sunDir), 0.);
  col += hex(255., 214., 160.) * (5. * pow(sd, 1400.) + .35 * pow(sd, 60.));
  // Haze towards the horizon line.
  vec3 horizon = sky(vec3(v.x, .001, v.z), sunDir);
  return mix(horizon, col, exp(-dist * .012));
}
