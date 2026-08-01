// sol — our solar system, as the driftwm canvas background.
//
// The Sun sits at the canvas origin, at a focus of eight real ellipses. The
// planets sit where they really were on 2026-07-30 — placed by solving
// Kepler's equation, so each one rides its own orbit line — ordered outward:
// Mercury, Venus, Earth, Mars, [asteroid belt], Jupiter, Saturn, Uranus,
// Neptune. Eccentricity and perihelion direction are real; only the spacing
// of the semi-major axes is uniform rather than true-to-scale, so that every
// hop between neighbours is a comparable distance.
//
// Zoom strata keep the workspace clean: at working zoom the astronomy fades
// to a whisper behind your windows, and it blooms as you pull back.
//
// GLSL ES 1.0. Shader coordinates are (x, -y) of driftwm canvas coordinates.
precision highp float;

varying vec2 v_coords;
uniform vec2 size;
uniform vec2 u_camera;
uniform float u_time;
uniform float u_zoom;

// Palette (Tokyo Night)
const vec3 SPACE_TOP = vec3(0.055, 0.055, 0.078);
const vec3 SPACE_BOT = vec3(0.078, 0.082, 0.118);
const vec3 STARLIGHT = vec3(0.753, 0.792, 0.961);
const vec3 ORBIT_COL = vec3(0.337, 0.373, 0.537);
const vec3 SUN_CORE  = vec3(1.000, 0.965, 0.878);
const vec3 SUN_GLOW  = vec3(0.941, 0.737, 0.408);

// Planet positions in shader space = driftwm canvas (x, y) with y negated.
const vec2 P1 = vec2(  934.0,   141.0);   // Mercury
const vec2 P2 = vec2( -512.0,  1753.0);   // Venus
const vec2 P3 = vec2( 1595.0,  2154.0);   // Earth
const vec2 P4 = vec2( 2057.0, -2649.0);   // Mars
const vec2 P5 = vec2(-2561.0, -3512.0);   // Jupiter
const vec2 P6 = vec2( 4997.0,  -768.0);   // Saturn
const vec2 P7 = vec2( 2823.0, -5294.0);   // Uranus
const vec2 P8 = vec2( 6692.0,  -265.0);   // Neptune

// Orbits, as ellipses: centre.xy (offset from the Sun, which is at a focus),
// semi-major, semi-minor. R is the perihelion direction, which is the
// ellipse's own axis — this is why Mercury's ring is visibly off-centre and
// Venus's is not. Regenerate with tools/sol-positions.py.
const vec4 O1 = vec4(  -44.5,   200.8, 1000.0,  978.63);   // Mercury
const vec4 O2 = vec4(    8.2,     9.2, 1820.0, 1819.96);   // Venus
const vec4 O3 = vec4(    9.9,    43.0, 2640.0, 2639.63);   // Earth
const vec4 O4 = vec4( -295.7,  -130.6, 3460.0, 3444.87);   // Mars
const vec4 O5 = vec4( -200.1,    52.8, 4280.0, 4274.99);   // Jupiter
const vec4 O6 = vec4(   11.9,   273.7, 5100.0, 5092.63);   // Saturn
const vec4 O7 = vec4(  276.3,    43.5, 5920.0, 5913.39);   // Uranus
const vec4 O8 = vec4(  -41.1,    40.9, 6740.0, 6739.75);   // Neptune
const vec2 R1 = vec2( 0.21643, -0.97630);
const vec2 R2 = vec2(-0.66397, -0.74776);
const vec2 R3 = vec2(-0.22535, -0.97428);
const vec2 R4 = vec2( 0.91478,  0.40395);
const vec2 R5 = vec2( 0.96689, -0.25519);
const vec2 R6 = vec2(-0.04340, -0.99906);
const vec2 R7 = vec2(-0.98786, -0.15535);
const vec2 R8 = vec2( 0.70860, -0.70561);

const vec3 C0 = vec3(0.941, 0.851, 0.604);   // the Sun, for its own district
const vec3 C1 = vec3(0.604, 0.647, 0.808);
const vec3 C2 = vec3(0.878, 0.686, 0.408);
const vec3 C3 = vec3(0.478, 0.635, 0.969);
const vec3 C4 = vec3(0.969, 0.463, 0.557);
const vec3 C5 = vec3(1.000, 0.620, 0.392);
const vec3 C6 = vec3(0.902, 0.812, 0.631);
const vec3 C7 = vec3(0.490, 0.812, 1.000);
const vec3 C8 = vec3(0.353, 0.498, 0.816);

const float BELT_R = 3870.0;
const float SUN_R  = 502.0;   // 109 Earth radii, on the same cube-root rule
const float POOL_R = 1500.0;  // how far a planet's colour pools around it

// The rectangles below are written by `sol arrange`: the card each district
// sits on. vec4 is (centre.xy, half-width, half-height) in shader space, and
// a zero half-width means that place is holding nothing. Only the lines
// between the two markers are generated; the rest of this file is yours.
// ── districts ──
const vec4 D0 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D1 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D2 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D3 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D4 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D5 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D6 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D7 = vec4(0.0, 0.0, 0.0, 0.0);
const vec4 D8 = vec4(0.0, 0.0, 0.0, 0.0);
// ── end districts ──

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// Distance from a point to an orbit ellipse. The gradient of the ellipse
// equation turns "inside / outside" into a length, which is exact enough
// within a few pixels of the curve — all a hairline needs.
float orbit_dist(vec2 c, vec4 o, vec2 rot) {
    vec2 d = c - o.xy;
    vec2 p = vec2(d.x * rot.x + d.y * rot.y, d.y * rot.x - d.x * rot.y);
    vec2 q = p / o.zw;
    return (dot(q, q) - 1.0) / max(length(2.0 * q / o.zw), 1e-6);
}

// One orbit line: a soft core with a wider, fainter bloom around it and no
// hard edge anywhere. Both widths are held in screen pixels, so the line
// keeps its weight at every zoom instead of thickening as you pull back.
float orbit_line(float dist, float px) {
    float a = abs(dist);
    return exp(-a / px) * 0.72 + exp(-a / (px * 5.0)) * 0.28;
}

// A planet: lit disc with a terminator facing the Sun, plus a thin atmosphere.
vec3 planet(vec2 c, vec2 p, float rad, vec3 tint, float bloom) {
    vec2 d = c - p;
    float r = length(d);
    if (r > rad * 4.0) return vec3(0.0);
    float disc = 1.0 - smoothstep(rad - 2.0, rad + 2.0, r);
    vec2 sunward = normalize(-p);                       // the Sun is at the origin
    float lit = 0.18 + 0.82 * clamp(dot(d / max(rad, 1.0), sunward) * 0.5 + 0.62, 0.0, 1.0);
    float atmo = exp(-abs(r - rad) * 0.05) * 0.30;
    return tint * (disc * lit + atmo) * bloom;
}

// Neighbourhood halo, so a window parked at a planet sits in a pool of that
// planet's colour when you pull back.
vec3 halo(vec2 c, vec2 p, vec3 tint, float uf, float amt) {
    return tint * exp(-dot(c - p, c - p) / (2.0 * POOL_R * POOL_R)) * uf * amt;
}

// Signed distance to a rounded rectangle. (`ext` is the half-extent; `half`
// itself is a reserved word in GLSL ES 1.0 and will not compile.)
float rrect(vec2 p, vec2 ext, float rad) {
    vec2 q = abs(p) - ext + rad;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - rad;
}

// The card a district sits on: a rounded panel in the planet's own colour,
// painted behind its windows so a workspace reads as a place rather than a
// heap of rectangles. `sol arrange` writes the rectangles; a zero-width one
// means that planet is holding nothing and nothing is drawn.
vec3 card(vec2 c, vec4 d, vec3 tint, float uf) {
    if (d.z < 1.0) return vec3(0.0);
    float s = rrect(c - d.xy, d.zw, 110.0);
    float fill = 1.0 - smoothstep(-3.0, 3.0, s);
    float rim  = exp(-abs(s) / 34.0);
    return tint * (fill * 0.05 + rim * 0.14) * (0.40 + 0.60 * uf);
}

void main() {
    vec2 screen = v_coords * size;
    vec2 c = screen + u_camera;

    // Zoom strata: 0 at working zoom, 1 when pulled well back.
    float uf = clamp((0.85 - u_zoom) * 2.2, 0.0, 1.0);
    float bloom = 0.35 + 0.65 * uf;

    vec3 col = mix(SPACE_TOP, SPACE_BOT, v_coords.y);

    // Starfield, parallaxed so panning feels like moving through depth
    vec2 sp = (screen + u_camera * 0.12) / 90.0;
    vec2 cell = floor(sp);
    float h = hash(cell);
    if (h > 0.93) {
        vec2 fp = fract(sp) - 0.5;
        vec2 off = vec2(hash(cell + 1.3), hash(cell + 2.7)) - 0.5;
        float tw = 0.6 + 0.4 * sin(u_time * (0.4 + h) + h * 40.0);
        col += STARLIGHT * (1.0 - smoothstep(0.02, 0.07, length(fp - off * 0.6))) * tw * 0.32;
    }

    float r = length(c);

    // Orbits
    float px = 1.5 / max(u_zoom, 0.04);
    float rings = orbit_line(orbit_dist(c, O1, R1), px)
                + orbit_line(orbit_dist(c, O2, R2), px)
                + orbit_line(orbit_dist(c, O3, R3), px)
                + orbit_line(orbit_dist(c, O4, R4), px)
                + orbit_line(orbit_dist(c, O5, R5), px)
                + orbit_line(orbit_dist(c, O6, R6), px)
                + orbit_line(orbit_dist(c, O7, R7), px)
                + orbit_line(orbit_dist(c, O8, R8), px);
    col += ORBIT_COL * rings * (0.035 + uf * 0.10);

    // District cards, over the orbit lines and under everything else
    col += card(c, D0, C0, uf) + card(c, D1, C1, uf) + card(c, D2, C2, uf)
         + card(c, D3, C3, uf) + card(c, D4, C4, uf) + card(c, D5, C5, uf)
         + card(c, D6, C6, uf) + card(c, D7, C7, uf) + card(c, D8, C8, uf);

    // Asteroid belt — a sparse annulus dividing the inner and outer system
    float band = 1.0 - smoothstep(90.0, 210.0, abs(r - BELT_R));
    if (band > 0.0) {
        vec2 ap = c / 62.0;
        vec2 ac = floor(ap);
        if (hash(ac + 5.7) > 0.90) {
            vec2 af = fract(ap) - 0.5;
            vec2 ao = vec2(hash(ac + 9.1), hash(ac + 3.3)) - 0.5;
            col += vec3(0.62, 0.60, 0.55)
                 * (1.0 - smoothstep(0.04, 0.10, length(af - ao * 0.7)))
                 * band * (0.10 + uf * 0.35);
        }
    }

    // The Sun: a disc with a limb, and a corona beyond it. Drawn to the same
    // rule as the planets, which at 109 Earth radii makes it far and away the
    // largest thing here — so, like the rest of the astronomy, it is held
    // down at working zoom and blooms only as you pull back.
    if (r < 2000.0) {
        float ang = atan(c.y, c.x);
        float flick = 0.88 + 0.12 * noise(vec2(ang * 3.0, u_time * 0.35));
        col += SUN_GLOW * exp(-r * 0.0026) * flick * (0.12 + uf * 0.20);
        col += SUN_CORE * (1.0 - smoothstep(SUN_R * 0.80, SUN_R, r))
             * (0.12 + uf * 0.66);
    }

    // Planets
    col += planet(c, P1,  76.0, C1, bloom);
    col += planet(c, P2, 103.0, C2, bloom);
    col += planet(c, P3, 105.0, C3, bloom);
    col += planet(c, P4,  85.0, C4, bloom);
    col += planet(c, P5, 233.0, C5, bloom);
    col += planet(c, P6, 220.0, C6, bloom);
    col += planet(c, P7, 166.0, C7, bloom);
    col += planet(c, P8, 165.0, C8, bloom);

    // Saturn's ring, at the real 2.35 planet radii of the A ring's outer edge
    vec2 sd = c - P6;
    float er = length(vec2(sd.x, sd.y * 3.0));
    col += C6 * (1.0 - smoothstep(0.0, 30.0, abs(er - 517.0))) * (0.10 + uf * 0.22);

    // Neighbourhood pools — each planet's colour spread wide and thin, so a
    // district sits in its own light rather than on flat black.
    col += halo(c, P1, C1, uf, 0.12);
    col += halo(c, P2, C2, uf, 0.12);
    col += halo(c, P3, C3, uf, 0.14);
    col += halo(c, P4, C4, uf, 0.12);
    col += halo(c, P5, C5, uf, 0.12);
    col += halo(c, P6, C6, uf, 0.12);
    col += halo(c, P7, C7, uf, 0.12);
    col += halo(c, P8, C8, uf, 0.12);

    // Vignette
    vec2 vc = v_coords - 0.5;
    col *= 1.0 - dot(vc, vc) * 0.40;

    gl_FragColor = vec4(col, 1.0);
}
