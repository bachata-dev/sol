// sol — our solar system, as the driftwm canvas background.
//
// The Sun sits at the canvas origin. The eight planets sit at their real
// heliocentric longitudes for 2026-07-30, one per orbit, ordered outward:
// Mercury, Venus, Earth, Mars, [asteroid belt], Jupiter, Saturn, Uranus,
// Neptune. Orbit spacing is uniform rather than true-to-scale so that every
// hop between neighbours is a comparable distance — the order and the angles
// are real, the radial scale is legible.
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
const vec2 P1 = vec2(  948.0,  -319.0);   // Mercury
const vec2 P2 = vec2( -481.0,  1755.0);   // Venus
const vec2 P3 = vec2( 1635.0,  2073.0);   // Earth
const vec2 P4 = vec2( 2551.0, -2338.0);   // Mars
const vec2 P5 = vec2(-2202.0, -3670.0);   // Jupiter
const vec2 P6 = vec2( 4935.0, -1286.0);   // Saturn
const vec2 P7 = vec2( 2307.0, -5452.0);   // Uranus
const vec2 P8 = vec2( 6730.0,  -362.0);   // Neptune

const vec3 C1 = vec3(0.604, 0.647, 0.808);
const vec3 C2 = vec3(0.878, 0.686, 0.408);
const vec3 C3 = vec3(0.478, 0.635, 0.969);
const vec3 C4 = vec3(0.969, 0.463, 0.557);
const vec3 C5 = vec3(1.000, 0.620, 0.392);
const vec3 C6 = vec3(0.902, 0.812, 0.631);
const vec3 C7 = vec3(0.490, 0.812, 1.000);
const vec3 C8 = vec3(0.353, 0.498, 0.816);

const float BELT_R = 3870.0;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

// One orbit ring. Width is held constant in screen pixels so the map reads
// the same at every zoom level.
float ring(float r, float radius, float px) {
    return 1.0 - smoothstep(0.0, px, abs(r - radius));
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
    return tint * exp(-dot(c - p, c - p) / (2.0 * 620.0 * 620.0)) * uf * amt;
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
    float px = 2.6 / max(u_zoom, 0.04);
    float rings = ring(r, 1000.0, px) + ring(r, 1820.0, px) + ring(r, 2640.0, px)
                + ring(r, 3460.0, px) + ring(r, 4280.0, px) + ring(r, 5100.0, px)
                + ring(r, 5920.0, px) + ring(r, 6740.0, px);
    col += ORBIT_COL * rings * (0.05 + uf * 0.16);

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

    // The Sun
    if (r < 2000.0) {
        float ang = atan(c.y, c.x);
        float flick = 0.88 + 0.12 * noise(vec2(ang * 3.0, u_time * 0.35));
        col += SUN_GLOW * exp(-r * 0.0026) * flick * (0.12 + uf * 0.20);
        col += SUN_CORE * exp(-(r * r) / (2.0 * 150.0 * 150.0)) * 0.75;
    }

    // Planets
    col += planet(c, P1,  68.0, C1, bloom);
    col += planet(c, P2, 103.0, C2, bloom);
    col += planet(c, P3, 105.0, C3, bloom);
    col += planet(c, P4,  81.0, C4, bloom);
    col += planet(c, P5, 199.0, C5, bloom);
    col += planet(c, P6, 192.0, C6, bloom);
    col += planet(c, P7, 159.0, C7, bloom);
    col += planet(c, P8, 158.0, C8, bloom);

    // Saturn's ring
    vec2 sd = c - P6;
    float er = length(vec2(sd.x, sd.y * 3.0));
    col += C6 * (1.0 - smoothstep(0.0, 26.0, abs(er - 330.0))) * (0.10 + uf * 0.22);

    // Neighbourhood halos
    col += halo(c, P1, C1, uf, 0.13);
    col += halo(c, P2, C2, uf, 0.13);
    col += halo(c, P3, C3, uf, 0.16);
    col += halo(c, P4, C4, uf, 0.13);
    col += halo(c, P5, C5, uf, 0.13);
    col += halo(c, P6, C6, uf, 0.13);
    col += halo(c, P7, C7, uf, 0.13);
    col += halo(c, P8, C8, uf, 0.13);

    // Vignette
    vec2 vc = v_coords - 0.5;
    col *= 1.0 - dot(vc, vc) * 0.40;

    gl_FragColor = vec4(col, 1.0);
}
