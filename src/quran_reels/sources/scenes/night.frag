#version 300 es
// Evening: dusk turning to night. Crescent moon, twinkling stars, two layers of clouds
// drifting across the sky (the near one faster, passing over the moon), mist moving over
// the hills. Sky palette of the validated mockup (#0b1026 → #1a2350 → #3b3a6b → #8a5a5a).
// Motion at the pace of filmed clouds: Facebook called the first version «a static image».

const float HORIZON = .14;

vec3 scene(vec2 uv, float t) {
  float aspect = u_res.x / u_res.y;
  vec2 p = vec2(uv.x * aspect, uv.y);
  float aa = 1.2 / u_res.y;
  float dusk = .78 + .22 * cos(6.2832 * t / 30.);  // the afterglow breathes, over the loop
  float s = 1. - uv.y;                           // 0 at the top

  vec3 col = mix(hex(11., 16., 38.), hex(26., 35., 80.), smoothstep(0., .45, s));
  col = mix(col, hex(59., 58., 107.), smoothstep(.45, .74, s));
  col = mix(col, mix(hex(62., 56., 104.), hex(150., 92., 88.), dusk), smoothstep(.72, 1., s));
  float glow = exp(-max(uv.y - HORIZON, 0.) / .13) * exp(-pow((uv.x - .72) / .55, 2.));
  col += hex(210., 120., 85.) * .28 * glow * dusk;

  // Stars: fewer and fainter towards the horizon.
  float starMask = smoothstep(.3, .75, uv.y) * (1.2 - .6 * dusk);
  if (starMask > 0.)
    col += (stars(p, t, 42., .33, 0.) + .7 * stars(p, t, 85., .22, 17.)) * starMask;

  // Waxing crescent, its lit side towards the set sun (lower right).
  vec2 mc = vec2(.73 * aspect, .835);
  float r = .03;
  float dm = length(p - mc);
  float disc = smoothstep(r + aa, r - aa, dm);
  float shade = smoothstep(r + aa, r - aa, length(p - mc - vec2(-.36, .2) * r));
  col += hex(255., 236., 200.) * (.12 * exp(-dm / .05) + .05 * exp(-dm / .2));
  if (disc > 0.)
    col = mix(col, hex(255., 241., 214.) * (.93 + .07 * gnoise(vec3((p - mc) * 90., 1.))),
              disc * (1. - shade));

  // Clouds in two layers, drifting right and changing shape as they go: high thin streaks,
  // slower, then nearer, thicker banks, faster (parallax), passing over the moon. Lit by the
  // moon (upper right) and, low down, by the afterglow.
  float band = smoothstep(.1, .2, uv.y) * (1. - smoothstep(.62, .8, uv.y))
             + .75 * smoothstep(.66, .86, uv.y);
  if (band > .01) {
    // Far layer.
    vec3 q = vec3(p * vec2(1.5, 4.5) + vec2(t * .026, 0.), t * .026) * 1.6;
    float n = fbm(q, 5);
    float cover = smoothstep(.55, .8, n) * band;
    if (cover > 0.) {
      vec3 cloud = mix(hex(30., 33., 66.), hex(84., 86., 128.), smoothstep(.55, .85, n));
      cloud += hex(255., 236., 200.) * .22 * exp(-dm / .22);
      cloud += hex(190., 110., 90.) * .5 * glow * dusk;
      col = mix(col, cloud, cover * .7);
    }
    // Near layer: the warp makes the banks roll and stretch instead of sliding as one piece.
    vec2 w = p * vec2(1.1, 3.) + vec2(t * .047, .1 * sin(t * .21));
    float warp = fbm(vec3(w * .8, t * .04 + 3.), 3);
    vec3 k = vec3(w + vec2(warp * .9, warp * .25), t * .037 + 7.) * 1.7;
    float m = fbm(k, 5);
    float thr = mix(.66, .5, band);
    float body = smoothstep(thr, thr + .2, m) * band;
    if (body > 0.) {
      float lit = clamp((m - fbm(k + vec3(.09, .12, 0.), 3)) * 9. + .35, 0., 1.);
      vec3 cloud = mix(hex(22., 25., 52.), hex(92., 94., 136.), lit);
      cloud += hex(255., 236., 200.) * .45 * lit * exp(-dm / .25);
      cloud += hex(190., 110., 90.) * .6 * glow * dusk;
      col = mix(col, cloud, body * .92);
    }
  }

  // Hills: a far hazy ridge and a near dark one, mist drifting in the valley between them.
  if (uv.y < .32) {
    float far = HORIZON + .012 + .1 * (fbm(vec3(p.x * 3.2, 1.3, 0.), 5) - .5);
    float near = .075 + .14 * (fbm(vec3(p.x * 2.1 + 5.2, 3.1, 0.), 5) - .5);
    col = mix(col, mix(col, hex(34., 32., 64.), .78), smoothstep(far + aa, far - aa, uv.y));
    float mist = fbm(vec3(p.x * 2.6 - t * .07, uv.y * 9., t * .06), 4);
    mist = smoothstep(.42, .75, mist) * smoothstep(far + .04, far - .02, uv.y)
         * smoothstep(near - .02, near + .05, uv.y);
    col = mix(col, hex(96., 92., 138.) + hex(190., 110., 90.) * .3 * glow, mist * .55);
    // The near slope: never one flat colour from edge to edge. It was #0e0e1f, still, under
    // the scrim: a black band along the bottom that Facebook's quality checklist read as a
    // border («vidéo avec bordures», 2026-11-13, the night reels). Rocks and scrub catch the
    // moonlight, the ridge has a lit rim, and a low mist drifts across the bottom edge.
    float depth = clamp((near - uv.y) / max(near, .02), 0., 1.);     // 0 at the ridge
    float rock = .6 * fbm(vec3(p.x * 6., uv.y * 9., 2.7), 4)
               + .4 * fbm(vec3(p.x * 22., uv.y * 30., 8.1), 3);
    vec3 ground = mix(hex(33., 30., 62.), hex(19., 18., 40.), depth) * (.45 + 1.1 * rock);
    ground += hex(170., 140., 160.) * .14 * smoothstep(near - .012, near, uv.y)
            * smoothstep(.15, .9, uv.x);                              // moon on the right
    col = mix(col, ground, smoothstep(near + aa, near - aa, uv.y));
    float low = fbm(vec3(p.x * 1.7 - t * .06, uv.y * 7., t * .05 + 7.), 4);
    low = smoothstep(.42, .8, low) * (1. - smoothstep(0., .09, uv.y));
    col = mix(col, hex(88., 84., 128.), low * .4);
  }
  return col;
}
