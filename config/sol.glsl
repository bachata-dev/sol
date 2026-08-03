// sol — our solar system, as the driftwm canvas background.
//
// The Sun sits at the canvas origin, at a focus of eight real ellipses. The
// planets sit where they really were on 2029-01-01 — placed by solving
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

// Palette. Cool and dark so the astronomy can sit behind your work without
// competing with it; several hues started life in Tokyo Night and drifted.
const vec3 SPACE_TOP = vec3(0.055, 0.055, 0.078);
const vec3 SPACE_BOT = vec3(0.078, 0.082, 0.118);
const vec3 STARLIGHT = vec3(0.753, 0.792, 0.961);
const vec3 ORBIT_COL = vec3(0.337, 0.373, 0.537);
const vec3 SUN_CORE  = vec3(1.000, 0.976, 0.898);   // the hot centre
const vec3 SUN_LIMB  = vec3(1.000, 0.678, 0.255);   // amber, where it cools
const vec3 SUN_GLOW  = vec3(0.976, 0.667, 0.333);   // the corona beyond it

// Planet positions in shader space = driftwm canvas (x, y) with y negated.
const vec2 P1 = vec2(     789.0,     -331.0);   // Mercury
const vec2 P2 = vec2(   -1089.0,     1461.0);   // Venus
const vec2 P3 = vec2(    -471.0,    -2553.0);   // Earth
const vec2 P4 = vec2(   -3202.0,    -2007.0);   // Mars
const vec2 P5 = vec2(   -4344.0,     1125.0);   // Jupiter
const vec2 P6 = vec2(    3789.0,    -3146.0);   // Saturn
const vec2 P7 = vec2(    1826.0,    -5663.0);   // Uranus
const vec2 P8 = vec2(    6634.0,     -890.0);   // Neptune

// Orbits, as ellipses: centre.xy (offset from the Sun, which is at a focus),
// semi-major, semi-minor. R is the perihelion direction, which is the
// ellipse's own axis — this is why Mercury's ring is visibly off-centre and
// Venus's is not. Regenerate with tools/sol-positions.py.
const vec4 O1 = vec4(    -44.5,     200.8, 1000.0,   978.63);  // Mercury
const vec4 O2 = vec4(      8.2,       9.2, 1820.0,  1819.96);  // Venus
const vec4 O3 = vec4(      9.9,      42.9, 2640.0,  2639.63);  // Earth
const vec4 O4 = vec4(   -295.7,    -130.5, 3460.0,  3444.87);  // Mars
const vec4 O5 = vec4(   -200.1,      52.8, 4280.0,  4274.99);  // Jupiter
const vec4 O6 = vec4(     11.8,     273.7, 5100.0,  5092.64);  // Saturn
const vec4 O7 = vec4(    276.3,      43.4, 5920.0,  5913.39);  // Uranus
const vec4 O8 = vec4(    -41.1,      40.9, 6740.0,  6739.75);  // Neptune
const vec2 R1 = vec2( 0.21637, -0.97631);
const vec2 R2 = vec2(-0.66397, -0.74776);
const vec2 R3 = vec2(-0.22549, -0.97425);
const vec2 R4 = vec2( 0.91486,  0.40378);
const vec2 R5 = vec2( 0.96687, -0.25528);
const vec2 R6 = vec2(-0.04322, -0.99907);
const vec2 R7 = vec2(-0.98789, -0.15518);
const vec2 R8 = vec2( 0.70869, -0.70552);

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

// A star is not white. Most are near-white, the hot few run blue, and the
// old ones run orange — the same three families a dark-sky photograph shows.
vec3 star_tint(float h) {
    if (h > 0.86) return vec3(0.64, 0.72, 1.00);       // the hot blue few
    if (h < 0.16) return vec3(1.00, 0.82, 0.62);       // the old orange few
    return vec3(0.78, 0.82, 0.97);                     // everyone else
}

// One layer of stars: a sparse grid, each cell holding at most one, offset
// inside its cell so no row ever reads. `par` is how much of the camera the
// layer follows — smaller is deeper, which is all parallax is.
vec3 stars(vec2 screen, float par, float cellpx, float amt, float t) {
    vec2 sp = (screen + u_camera * par) / cellpx;
    vec2 cell = floor(sp);
    float h = hash(cell);
    if (h <= 0.93) return vec3(0.0);
    vec2 fp = fract(sp) - 0.5;
    vec2 off = vec2(hash(cell + 1.3), hash(cell + 2.7)) - 0.5;
    float tw = 0.72 + 0.28 * sin(t * (0.3 + h) + h * 40.0);
    float pt = 1.0 - smoothstep(0.02, 0.07, length(fp - off * 0.6));
    return star_tint(hash(cell + 7.7)) * pt * tw * amt;
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

// What a planet's face is made of. Two numbers, because two are enough to
// tell the kinds of world apart: gas giants are banded along their latitudes
// and the rocky ones are blotched where their surfaces differ.
//
// The disc is a projected sphere, so latitude comes from asin() rather than
// straight from y — which is what makes the bands crowd together towards the
// poles the way they really do, instead of marching evenly down the face. A
// little noise warps them so they are not drawn with a ruler, and everything
// fades out at the limb where the surface is turning away from you.
float face(vec2 d, float rad, float band, float mottle) {
    vec2 n = d / max(rad, 1.0);
    float z2 = 1.0 - dot(n, n);
    if (z2 <= 0.0) return 0.0;
    float lat = asin(clamp(n.y, -1.0, 1.0));
    float warp = noise(vec2(n.x * 2.2, lat * 3.4)) - 0.5;
    float bands = sin(lat * 9.0 + warp * 1.7) * band;
    float blots = (noise(n * 5.0 + 3.7) - 0.5) * 2.0 * mottle;
    return (bands + blots) * sqrt(z2);
}

// A planet: lit disc with a terminator facing the Sun, plus a thin atmosphere.
vec3 planet(vec2 c, vec2 p, float rad, vec3 tint, float bloom,
            float band, float mottle) {
    vec2 d = c - p;
    float r = length(d);
    if (r > rad * 4.0) return vec3(0.0);
    float disc = 1.0 - smoothstep(rad - 2.0, rad + 2.0, r);
    vec2 sunward = normalize(-p);                       // the Sun is at the origin
    float lit = 0.18 + 0.82 * clamp(dot(d / max(rad, 1.0), sunward) * 0.5 + 0.62, 0.0, 1.0);
    float atmo = exp(-abs(r - rad) * 0.05) * 0.30;
    return tint * (disc * lit * (1.0 + face(d, rad, band, mottle)) + atmo) * bloom;
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
//
// `here` lifts the card the camera is standing in. It is not decoration —
// the camera position is stateful truth the shader already receives, and
// "the lights are on where you are" is how a district reads as the room
// you are in rather than one more rectangle in the dark.
vec3 card(vec2 c, vec4 d, vec3 tint, float uf, float here) {
    if (d.z < 1.0) return vec3(0.0);
    float s = rrect(c - d.xy, d.zw, 110.0);
    float fill = 1.0 - smoothstep(-3.0, 3.0, s);
    float rim  = exp(-abs(s) / 34.0);
    return tint * (fill * 0.05 + rim * 0.14) * (0.40 + 0.60 * uf) * (1.0 + here * 0.9);
}

// Is a point inside a district's rectangle? 1.0 or 0.0.
float inside(vec2 p, vec4 d) {
    if (d.z < 1.0) return 0.0;
    vec2 q = abs(p - d.xy) - d.zw;
    return step(max(q.x, q.y), 0.0);
}

void main() {
    vec2 screen = v_coords * size;
    vec2 c = screen + u_camera;

    // Zoom strata: 0 at working zoom, 1 when pulled well back.
    float uf = clamp((0.85 - u_zoom) * 2.2, 0.0, 1.0);
    float bloom = 0.35 + 0.65 * uf;

    vec3 col = mix(SPACE_TOP, SPACE_BOT, v_coords.y);

    // The Milky Way, on the deepest layer there is. The galactic plane
    // really does cross the ecliptic at about 60°, and the Sun really does
    // sit in it — so the band runs through the origin at that angle, made
    // of cloud rather than a line, and barely follows the camera at all,
    // because the galaxy is the one thing here that is genuinely far away.
    vec2 mw = screen + u_camera * 0.03;
    float d_mw = dot(mw, vec2(-0.868, 0.496));
    float band_mw = exp(-d_mw * d_mw / (2.0 * 900.0 * 900.0));
    float wisp = noise(mw * 0.0016) * 0.65 + noise(mw * 0.004) * 0.35;
    col += vec3(0.72, 0.76, 0.92) * band_mw * (0.20 + 0.55 * wisp) * 0.045;

    // Starfield in three depths, so panning moves through the sky rather
    // than past a painted one. The near layer keeps the brightness the old
    // single layer had; the two behind it only deepen the field.
    col += stars(screen, 0.26, 62.0, 0.30, u_time);
    col += stars(screen, 0.12, 90.0, 0.26, u_time);
    col += stars(screen, 0.05, 130.0, 0.18, u_time);

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

    // District cards, over the orbit lines and under everything else. The
    // card the camera is inside of is lifted: you can see which room you
    // are in from the light being on.
    vec2 cam = u_camera + size * 0.5;
    col += card(c, D0, C0, uf, inside(cam, D0)) + card(c, D1, C1, uf, inside(cam, D1))
         + card(c, D2, C2, uf, inside(cam, D2)) + card(c, D3, C3, uf, inside(cam, D3))
         + card(c, D4, C4, uf, inside(cam, D4)) + card(c, D5, C5, uf, inside(cam, D5))
         + card(c, D6, C6, uf, inside(cam, D6)) + card(c, D7, C7, uf, inside(cam, D7))
         + card(c, D8, C8, uf, inside(cam, D8));

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
    //
    // The disc is not one flat colour, because a flat disc is exactly what
    // made it look pale. A star reads as a sphere for the same reason a
    // planet does: the edge is cooler and dimmer than the middle. So the
    // colour walks from a near-white core out to amber at the limb and
    // darkens as it goes, over a slow granulation that keeps it from
    // looking painted.
    if (r < 2600.0) {
        float ang = atan(c.y, c.x);
        float flick = 0.88 + 0.12 * noise(vec2(ang * 3.0, u_time * 0.35));

        // Corona in two falloffs: a tight one that hugs the limb, and a wide
        // faint one that reaches out towards Mercury. Between them they come
        // to about what the single falloff they replaced did — the point of
        // the second is the shape of the fade, not more light.
        col += SUN_GLOW * exp(-r * 0.0040) * flick * (0.09 + uf * 0.17);
        col += SUN_GLOW * exp(-r * 0.0011) * flick * (0.03 + uf * 0.06);

        // The disc keeps exactly the brightness it always had. What changed
        // is where that brightness goes: concentrated in the core and falling
        // away to a cooler limb, rather than spread flat across the whole
        // face. Pale was never a shortage of light, it was a shortage of
        // contrast.
        float d = clamp(r / SUN_R, 0.0, 1.0);
        float mu = sqrt(max(0.0, 1.0 - d * d));       // cosine of the view angle
        float limb = 0.34 + 0.66 * pow(mu, 0.55);     // the classic darkening law
        float gran = 0.94 + 0.06 * noise(c * 0.014 + u_time * 0.02);
        col += mix(SUN_LIMB, SUN_CORE, limb) * limb * gran
             * (1.0 - smoothstep(SUN_R * 0.98, SUN_R * 1.015, r))
             * (0.12 + uf * 0.66);
    }

    // Planets, each with the face its own kind of world has: banding for the
    // gas giants, mottling for the rocky ones. Venus is nearly blank because
    // Venus is nearly blank — an unbroken deck of cloud — and Uranus is the
    // smoothest thing in the system.
    //                                     band  mottle
    col += planet(c, P1,  76.0, C1, bloom, 0.00, 0.18);   // Mercury, cratered
    col += planet(c, P2, 103.0, C2, bloom, 0.03, 0.05);   // Venus, featureless
    col += planet(c, P3, 105.0, C3, bloom, 0.00, 0.16);   // Earth, land and sea
    col += planet(c, P4,  85.0, C4, bloom, 0.00, 0.20);   // Mars, albedo marks
    col += planet(c, P5, 233.0, C5, bloom, 0.16, 0.03);   // Jupiter, belts
    col += planet(c, P6, 220.0, C6, bloom, 0.10, 0.02);   // Saturn, fainter
    col += planet(c, P7, 166.0, C7, bloom, 0.03, 0.00);   // Uranus, smooth
    col += planet(c, P8, 165.0, C8, bloom, 0.05, 0.03);   // Neptune, faint bands

    // Saturn's rings as they are: the broad bright B ring, the Cassini
    // division, then the A ring — at their real extents in planet radii
    // (B spans 1.53–1.95, A spans 2.03–2.27), squashed to the tilt the
    // system is viewed at. Never over the disc: seen from above the plane,
    // the planet stands in front of its own rings, so the ring fades out
    // where the disc begins instead of drawing across it.
    vec2 sd = c - P6;
    float er = length(vec2(sd.x, sd.y * 3.0)) / 220.0;      // in Saturn radii
    float ringB = smoothstep(1.50, 1.56, er) * (1.0 - smoothstep(1.90, 1.97, er));
    float ringA = smoothstep(2.01, 2.07, er) * (1.0 - smoothstep(2.24, 2.30, er));
    float infront = smoothstep(216.0, 232.0, length(sd));
    col += C6 * (ringB * 0.95 + ringA * 0.70) * infront * (0.07 + uf * 0.18);

    // Earth's night side shows its cities: warm pinpricks past the
    // terminator only, and only on land — the same noise field that mottles
    // the daylit face decides where the continents are, so the lights and
    // the landmasses agree about which planet this is.
    vec2 ed = c - P3;
    if (length(ed) < 105.0) {
        vec2 en = ed / 105.0;
        float night = smoothstep(0.02, 0.42, -dot(en, normalize(-P3)));
        vec2 cp = ed / 9.0;
        vec2 cc = floor(cp);
        if (hash(cc + 4.2) > 0.80) {
            vec2 cf = fract(cp) - 0.5;
            float spark = 1.0 - smoothstep(0.05, 0.15, length(cf));
            float onland = step(0.5, noise(en * 5.0 + 3.7));
            col += vec3(1.0, 0.82, 0.55) * spark * night * onland
                 * sqrt(max(0.0, 1.0 - dot(en, en))) * (0.30 + uf * 0.55);
        }
    }

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
