#version 300 es
// Evening: dusk turning to night. Crescent moon, twinkling stars, slow clouds, hills.
// Sky palette of the validated mockup (#0b1026 → #1a2350 → #3b3a6b → #8a5a5a).

const float HORIZON = .14;

vec3 scene(vec2 uv, float t) {
  float aspect = u_res.x / u_res.y;
  vec2 p = vec2(uv.x * aspect, uv.y);
  float aa = 1.2 / u_res.y;
  float dusk = .8 + .2 * cos(6.2832 * t / 30.);   // the afterglow breathes, over the loop
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

  // Clouds, stretched and drifting right, slowly changing shape. Lit by the moon (upper
  // right) and, low down, by the afterglow.
  float band = smoothstep(.12, .22, uv.y) * (1. - smoothstep(.5, .7, uv.y))
             + .6 * smoothstep(.72, .9, uv.y);
  if (band > .01) {
    vec3 q = vec3(p * vec2(1.5, 4.) + vec2(t * .011, 0.), t * .012) * 1.6;
    float n = fbm(q, 6);
    float thr = mix(.8, .5, band);
    float cover = smoothstep(thr, thr + .2, n);
    if (cover > 0.) {
      float lit = clamp((n - fbm(q + vec3(.08, .11, 0.), 4)) * 9. + .3, 0., 1.);
      vec3 cloud = mix(hex(24., 27., 55.), hex(72., 74., 112.), lit);
      cloud += hex(255., 236., 200.) * .25 * lit * exp(-dm / .25);
      cloud += hex(190., 110., 90.) * .55 * glow * dusk;
      col = mix(col, cloud, cover * .9);
    }
  }

  // Hills: a far hazy ridge and a near dark one.
  if (uv.y < .3) {
    float far = HORIZON + .012 + .1 * (fbm(vec3(p.x * 3.2, 1.3, 0.), 5) - .5);
    float near = .075 + .14 * (fbm(vec3(p.x * 2.1 + 5.2, 3.1, 0.), 5) - .5);
    col = mix(col, mix(col, hex(34., 32., 64.), .78), smoothstep(far + aa, far - aa, uv.y));
    col = mix(col, hex(14., 14., 31.), smoothstep(near + aa, near - aa, uv.y));
  }
  return col;
}
