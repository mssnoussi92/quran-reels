#version 300 es
// Morning: dawn over desert dunes. The sun at the horizon, its glow breathing, light rays
// shimmering, two layers of thin pink clouds drifting (the near one faster), sand blown off
// the crests, the last stars fading at the top. Motion at the pace of filmed clouds: Facebook
// called the first version «a static image».

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
  float breath = 1. + .1 * sin(6.2832 * t / 7.5);     // 4 times over the loop
  col += hex(255., 186., 120.) * (.5 * exp(-ds / .05) + .28 * breath * exp(-ds / .22));

  // Light rays fanning out from the sun, shimmering and slowly turning.
  float ang = atan(d.y, d.x) + .04 * sin(t * .21);
  float rays = .5 + gnoise(vec3(ang * 5., t * .16, 0.)) + .4 * gnoise(vec3(ang * 11., t * .26, 4.));
  rays = smoothstep(.45, 1.1, rays) * exp(-length(d) / .32) * smoothstep(0., .06, d.y);
  col += hex(255., 205., 160.) * rays * .2;

  // The last stars, high up.
  float starMask = smoothstep(.62, .95, uv.y);
  if (starMask > 0.) col += stars(p, t, 40., .25, 3.) * starMask * .7;

  // Thin clouds, stretched, drifting left and changing shape; pink and gold underneath, lit
  // by the sun. High wisps, slower, then a lower layer, faster (parallax).
  float band = smoothstep(.19, .3, uv.y) * (1. - smoothstep(.62, .82, uv.y));
  if (uv.y > .5) {
    vec3 q = vec3(p * vec2(1.4, 7.) + vec2(-t * .034, 0.), t * .034 + 5.) * 1.3;
    float n = fbm(q, 4);
    float cover = smoothstep(.5, .74, n) * smoothstep(.5, .66, uv.y)
                * (1. - smoothstep(.88, 1., uv.y));
    col = mix(col, mix(hex(150., 98., 140.), hex(250., 170., 150.), smoothstep(.55, .85, n)),
              cover * .65);
  }
  if (band > .01) {
    vec2 w = p * vec2(1.1, 6.) + vec2(-t * .066, 0.);
    float warp = fbm(vec3(w * vec2(.7, .4), t * .045 + 2.), 3);
    vec3 q = vec3(w + vec2(warp * .8, 0.), t * .045) * 1.4;
    float n = fbm(q, 6);
    float cover = smoothstep(.44, .68, n) * band;
    if (cover > 0.) {
      float lit = clamp((fbm(q + vec3(0., -.12, 0.), 4) - n) * 8. + .45, 0., 1.);
      vec3 cloud = mix(hex(96., 62., 104.), hex(255., 180., 140.), lit);
      cloud = mix(cloud, hex(255., 205., 150.), .45 * exp(-length(d) / .3) * lit);
      col = mix(col, cloud, cover * .85);
    }
  }

  // Dunes: three ridges, hazy far away, darker and nearer below, rim-lit by the sun.
  if (uv.y < .3) {
    float glowX = exp(-pow((p.x - sun.x) / .35, 2.));
    // Shadows of the clouds passing over the sand.
    float shadow = .8 + .2 * smoothstep(.36, .62,
                                        fbm(vec3(p.x * 1.6 - t * .05, uv.y * 5., t * .03), 3));
    float h3 = dune(p.x, HORIZON - .006, .025, 30., 1.3);
    float h2 = dune(p.x, .1, .06, 15., 4.1);
    float h1 = dune(p.x, .03, .085, 9., 7.7);
    vec3 c3 = mix(col, hex(160., 98., 112.), .6);
    vec3 c2 = hex(104., 62., 88.) * (.82 + .18 * exp(-(h2 - uv.y) / .03)) * shadow;
    vec3 c1 = hex(56., 34., 58.) * (.8 + .2 * exp(-(h1 - uv.y) / .04)) * shadow;
    col = mix(col, c3, smoothstep(h3 + aa, h3 - aa, uv.y));
    // Morning haze drifting over the far dunes.
    float haze = fbm(vec3(p.x * 2.4 + t * .06, uv.y * 10., t * .05), 4);
    haze = smoothstep(.45, .78, haze) * smoothstep(h3 + .03, h3 - .02, uv.y)
         * smoothstep(h2 - .01, h2 + .04, uv.y);
    col = mix(col, hex(236., 160., 140.), haze * .4 * (.5 + .5 * glowX));
    col = mix(col, c2 + hex(255., 160., 110.) * .35 * glowX * exp(-(h2 - uv.y) / .006),
              smoothstep(h2 + aa, h2 - aa, uv.y));
    // Sand blown off the near crest by the wind, in gusts.
    float above = uv.y - h1;
    if (above > -.004 && above < .05) {
      float gust = fbm(vec3(p.x * 9. - t * .45, above * 60. - t * .2, t * .3), 4);
      float sand = smoothstep(.5, .8, gust) * exp(-max(above, 0.) / .014)
                 * (.4 + .6 * smoothstep(-.3, .6, sin(p.x * 3. - t * .7)));
      col = mix(col, hex(220., 150., 120.) + hex(255., 170., 110.) * .4 * glowX, sand * .5);
    }
    col = mix(col, c1 + hex(255., 150., 100.) * .25 * glowX * exp(-(h1 - uv.y) / .005),
              smoothstep(h1 + aa, h1 - aa, uv.y));
  }
  return col;
}
