#version 300 es
// Morning: dawn over desert dunes. The sun at the horizon, soft light rays, thin pink
// clouds, the last stars fading at the top.

const float HORIZON = .17;

float dune(float x, float base, float amp, float freq, float seed) {
  // Rounded crests, a gentle windward side and a steeper lee side, uneven heights.
  float w = x * freq + seed;
  float s = .5 + .5 * sin(w + .65 * cos(w));
  float a = amp * (.6 + .4 * sin(.37 * w + 2. * seed));
  return base + a * pow(s, 1.4) + .12 * amp * (fbm(vec3(x * freq * .5, seed, 0.), 3) - .5);
}

vec3 scene(vec2 uv, float t) {
  float aspect = u_res.x / u_res.y;
  vec2 p = vec2(uv.x * aspect, uv.y);
  float aa = 1.2 / u_res.y;
  float s = 1. - uv.y;
  vec2 sun = vec2(.5 * aspect, HORIZON + .012);
  vec2 d = p - sun;

  // Sky: indigo at the top, violet, rose, peach at the horizon.
  vec3 col = mix(hex(22., 27., 64.), hex(58., 55., 110.), smoothstep(0., .42, s));
  col = mix(col, hex(150., 94., 126.), smoothstep(.42, .72, s));
  col = mix(col, hex(240., 160., 118.), smoothstep(.72, 1. - HORIZON + .02, s));
  float ds = length(d * vec2(.75, 1.5));
  col += hex(255., 186., 120.) * (.5 * exp(-ds / .05) + .28 * exp(-ds / .22));

  // Light rays fanning out from the sun, slowly shimmering.
  float ang = atan(d.y, d.x);
  float rays = .5 + gnoise(vec3(ang * 5., t * .05, 0.)) + .4 * gnoise(vec3(ang * 11., t * .08, 4.));
  rays = smoothstep(.5, 1.15, rays) * exp(-length(d) / .28) * smoothstep(0., .06, d.y);
  col += hex(255., 205., 160.) * rays * .16;

  // The last stars, high up.
  float starMask = smoothstep(.62, .95, uv.y);
  if (starMask > 0.) col += stars(p, t, 40., .25, 3.) * starMask * .7;

  // Thin clouds, stretched, drifting left; pink and gold underneath, lit by the sun.
  float band = smoothstep(.24, .36, uv.y) * (1. - smoothstep(.62, .82, uv.y));
  if (band > .01) {
    vec3 q = vec3(p * vec2(1.1, 6.) + vec2(-t * .01, 0.), t * .01) * 1.4;
    float n = fbm(q, 6);
    float cover = smoothstep(.53, .77, n) * band;
    if (cover > 0.) {
      float lit = clamp((fbm(q + vec3(0., -.12, 0.), 4) - n) * 7. + .45, 0., 1.);
      vec3 cloud = mix(hex(110., 74., 112.), hex(255., 176., 140.), lit);
      cloud = mix(cloud, hex(255., 200., 150.), .35 * exp(-length(d) / .3));
      col = mix(col, cloud, cover * .75);
    }
  }

  // Dunes: three ridges, hazy far away, darker and nearer below, rim-lit by the sun.
  if (uv.y < .3) {
    float glowX = exp(-pow((p.x - sun.x) / .35, 2.));
    float h3 = dune(p.x, HORIZON - .006, .025, 30., 1.3);
    float h2 = dune(p.x, .1, .06, 15., 4.1);
    float h1 = dune(p.x, .03, .085, 9., 7.7);
    vec3 c3 = mix(col, hex(160., 98., 112.), .6);
    vec3 c2 = hex(104., 62., 88.) * (.82 + .18 * exp(-(h2 - uv.y) / .03));
    vec3 c1 = hex(56., 34., 58.) * (.8 + .2 * exp(-(h1 - uv.y) / .04));
    col = mix(col, c3, smoothstep(h3 + aa, h3 - aa, uv.y));
    col = mix(col, c2 + hex(255., 160., 110.) * .35 * glowX * exp(-(h2 - uv.y) / .006),
              smoothstep(h2 + aa, h2 - aa, uv.y));
    col = mix(col, c1 + hex(255., 150., 100.) * .25 * glowX * exp(-(h1 - uv.y) / .005),
              smoothstep(h1 + aa, h1 - aa, uv.y));
  }
  return col;
}
