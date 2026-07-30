// sol — a Tokyo Night solar system for driftwm
//
// Sol (the sun) burns at Desk — everything revolves around your desk.
// Ops and Info are shaded planets on the r=2400 orbit (terminator lit by the
// sun; Ops wears a Saturn ring). Scratch is an asteroid belt along r=1600.
// Moons crawl the orbits in real time; a comet rides an ellipse with a tail.
// Scale strata: work zoom stays clean; regions/orbits bloom below 0.8 zoom,
// cosmic web below 0.34. Wormhole gates at x=±4800 (daemon teleports a
// lingering camera). Internal shader coords = (x, -bookmark_y).
precision highp float;

varying vec2 v_coords;
uniform vec2 size;
uniform vec2 u_camera;
uniform float u_time;
uniform float u_zoom;

// Tokyo Night palette
const vec3 BG_TOP    = vec3(0.086, 0.086, 0.118);
const vec3 BG_BOT    = vec3(0.102, 0.106, 0.149);
const vec3 AUR_BLUE  = vec3(0.478, 0.635, 0.969);
const vec3 AUR_PURP  = vec3(0.733, 0.604, 0.969);
const vec3 AUR_CYAN  = vec3(0.490, 0.812, 1.000);
const vec3 STAR_COL  = vec3(0.753, 0.792, 0.961);
const vec3 GRID_COL  = vec3(0.337, 0.373, 0.537);
const vec3 OPS_GREEN = vec3(0.620, 0.808, 0.416);
const vec3 SCR_ORNG  = vec3(1.000, 0.620, 0.392);
const vec3 GOLD      = vec3(0.878, 0.686, 0.408);
const vec3 SUN_CORE  = vec3(1.000, 0.950, 0.850);

// Layout (internal coords). Region glows anchor at the window clusters;
// planet bodies ride the same orbit offset ~14 deg along the arc so the
// windows don't occlude them.
const vec2 SOL       = vec2(0.0, 0.0);        // Desk
const vec2 R_OPS     = vec2(2400.0, 0.0);
const vec2 R_INFO    = vec2(-2400.0, 0.0);
const vec2 P_OPS     = vec2(2329.0, -582.0);
const vec2 P_INFO    = vec2(-2329.0, -582.0);
const vec2 BELT_C    = vec2(0.0, 1600.0);     // Scratch cluster on the belt
const vec2 GATE_W    = vec2(-4800.0, 0.0);
const vec2 GATE_E    = vec2(4800.0, 0.0);

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
               mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x),
               u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * noise(p);
        p = p * 2.03 + vec2(17.0, 9.2);
        a *= 0.55;
    }
    return v;
}

// Soft territorial glow (no ring — orbits carry the structure now)
vec3 glow(vec2 cpos, vec2 rpos, vec3 tint, float uf) {
    float d = length(cpos - rpos);
    return tint * exp(-(d * d) / (2.0 * 700.0 * 700.0)) * (0.05 + uf * 0.20);
}

// Shaded planet: disc with a day/night terminator lit from the sun
vec3 planet(vec2 cpos, vec2 ppos, float rad, vec3 tint) {
    vec2 d = cpos - ppos;
    float r = length(d);
    if (r > rad * 3.5) return vec3(0.0);
    float disc = 1.0 - smoothstep(rad - 3.0, rad + 3.0, r);
    vec2 sdir = normalize(SOL - ppos);
    float lit = 0.25 + 0.75 * clamp(dot(d / rad, sdir) * 0.5 + 0.62, 0.0, 1.0);
    float atmo = exp(-abs(r - rad) * 0.045) * 0.22;
    return tint * (disc * lit * 0.85 + atmo);
}

// Orbiting moon: a small bright body moving along an orbit in real time
vec3 moon(vec2 cpos, float orbR, float speed, float phase, vec3 tint, float t) {
    vec2 mp = vec2(cos(t * speed + phase), sin(t * speed + phase)) * orbR;
    float d2 = dot(cpos - mp, cpos - mp);
    return tint * exp(-d2 / (2.0 * 22.0 * 22.0)) * 0.8;
}

// Animated wormhole portal
vec3 gatePortal(vec2 d, float t) {
    float r = length(d);
    if (r > 520.0) return vec3(0.0);
    float ang = atan(d.y, d.x);
    float swirl = 0.5 + 0.5 * sin(ang * 3.0 - t * 1.6 + r * 0.03);
    float ring = exp(-abs(r - 170.0) * 0.025) * (0.4 + 0.6 * swirl);
    float core = exp(-(r * r) / (2.0 * 55.0 * 55.0));
    return AUR_CYAN * ring * 0.30 + AUR_PURP * core * 0.45;
}

// Distant landmark galaxy
vec3 farGalaxy(vec2 d, float tilt, vec3 tint) {
    float cs = cos(tilt);
    float sn = sin(tilt);
    vec2 e = vec2(cs * d.x - sn * d.y, (sn * d.x + cs * d.y) * 2.6);
    float r = length(e);
    if (r > 700.0) return vec3(0.0);
    float body = exp(-(r * r) / (2.0 * 130.0 * 130.0));
    float arm = 0.75 + 0.25 * cos(atan(e.y, e.x) * 2.0 - r * 0.05);
    return tint * body * arm * 0.16;
}

void main() {
    vec2 screen = v_coords * size;
    vec2 cpos = screen + u_camera;

    float uf  = clamp((0.80 - u_zoom) * 2.5, 0.0, 1.0);
    float uf3 = clamp((0.34 - u_zoom) * 6.0, 0.0, 1.0);

    vec3 col = mix(BG_TOP, BG_BOT, v_coords.y);

    // Aurora — mid-depth parallax
    vec2 pa = (screen + u_camera * 0.35) * 0.00055;
    float t = u_time * 0.03;
    float n1 = fbm(pa + vec2(t, -t * 0.6));
    float n2 = fbm(pa * 1.7 - vec2(t * 0.8, t * 0.4) + 3.7);
    float band = smoothstep(0.42, 0.72, n1) * 0.55 + smoothstep(0.52, 0.82, n2) * 0.4;
    vec3 aurora = mix(AUR_BLUE, AUR_PURP, noise(pa * 2.2 + t));
    aurora = mix(aurora, AUR_CYAN, smoothstep(0.6, 0.9, n2) * 0.6);
    col += aurora * band * 0.30;

    // Starfield — deepest parallax, twinkle
    vec2 sp = (screen + u_camera * 0.12) / 90.0;
    vec2 cell = floor(sp);
    float h = hash(cell);
    if (h > 0.92) {
        vec2 fp = fract(sp) - 0.5;
        vec2 off = vec2(hash(cell + 1.3), hash(cell + 2.7)) - 0.5;
        float d = length(fp - off * 0.6);
        float tw = 0.6 + 0.4 * sin(u_time * (0.5 + h) + h * 40.0);
        col += STAR_COL * (1.0 - smoothstep(0.02, 0.07, d)) * tw * 0.35;
    }

    // Cosmic web at the deepest zoom stratum
    if (uf3 > 0.0) {
        float w = fbm(cpos * 0.00013 + 7.3);
        float fil = pow(clamp(1.0 - abs(w - 0.5) * 2.0, 0.0, 1.0), 7.0);
        col += mix(AUR_BLUE, AUR_PURP, noise(cpos * 0.0004)) * fil * uf3 * 0.06;
    }

    // Distant landmark galaxies
    col += farGalaxy(cpos - vec2(3600.0, -2400.0), 0.6, AUR_PURP);
    col += farGalaxy(cpos - vec2(-4200.0, 2600.0), -0.9, AUR_CYAN);
    col += farGalaxy(cpos - vec2(1400.0, 3400.0), 0.2, GOLD);
    col += farGalaxy(cpos - vec2(-2000.0, -3400.0), 1.9, AUR_BLUE);

    // ── Orbits (screen-constant line width) ──
    float rSol = length(cpos - SOL);
    float ow = 3.0 / max(u_zoom, 0.05);
    float orb1 = 1.0 - smoothstep(0.0, ow, abs(rSol - 1600.0));
    float orb2 = 1.0 - smoothstep(0.0, ow, abs(rSol - 2400.0));
    col += GRID_COL * (orb1 + orb2) * (0.04 + uf * 0.14);

    // ── Sol: the sun at Desk (halo wide enough to flare around windows) ──
    if (rSol < 1500.0) {
        vec2 dd = cpos - SOL;
        float ang = atan(dd.y, dd.x);
        float corona = pow(0.5 + 0.5 * sin(ang * 9.0 + u_time * 0.25), 3.0);
        float flick = 0.85 + 0.15 * noise(vec2(ang * 3.0, u_time * 0.4));
        float halo = exp(-rSol * 0.0038);
        float core = exp(-(rSol * rSol) / (2.0 * 85.0 * 85.0));
        col += GOLD * halo * flick * (0.13 + uf * 0.20) * (0.65 + 0.35 * corona);
        col += SUN_CORE * core * 0.55;
    }
    col += glow(cpos, SOL, GOLD, uf * 0.6);

    // ── Ops: green planet with a Saturn ring ──
    col += glow(cpos, R_OPS, OPS_GREEN, uf);
    col += planet(cpos, P_OPS, 170.0, OPS_GREEN);
    vec2 eo = cpos - P_OPS;
    vec2 ell = vec2(eo.x, eo.y * 2.8);
    float er = length(ell);
    float sring = 1.0 - smoothstep(0.0, 30.0, abs(er - 330.0));
    col += OPS_GREEN * sring * (0.10 + uf * 0.18);

    // ── Info: purple planet inside its nebula ──
    col += glow(cpos, R_INFO, AUR_PURP, uf);
    col += planet(cpos, P_INFO, 155.0, AUR_PURP);
    vec2 di = cpos - R_INFO;
    float rI = length(di);
    if (rI < 1100.0) {
        float nI = fbm(di * 0.0022 + u_time * 0.02);
        col += AUR_PURP * nI * exp(-(rI * rI) / (2.0 * 520.0 * 520.0)) * (0.04 + uf * 0.14);
    }

    // ── Scratch: asteroid belt along the whole r=1600 orbit ──
    col += glow(cpos, BELT_C, SCR_ORNG, uf * 0.8);
    float beltBand = 1.0 - smoothstep(120.0, 220.0, abs(rSol - 1600.0));
    if (beltBand > 0.0) {
        vec2 apc = cpos / 70.0;
        vec2 acell = floor(apc);
        float ah = hash(acell + 5.7);
        // denser near the Scratch cluster, sparse along the rest of the belt
        float near = exp(-dot(cpos - BELT_C, cpos - BELT_C) / (2.0 * 800.0 * 800.0));
        float thresh = 0.93 - near * 0.20;
        if (ah > thresh) {
            vec2 af = fract(apc) - 0.5;
            vec2 aoff = vec2(hash(acell + 9.1), hash(acell + 3.3)) - 0.5;
            float ad = length(af - aoff * 0.7);
            col += SCR_ORNG * (1.0 - smoothstep(0.03, 0.09, ad)) * beltBand * (0.12 + uf * 0.30);
        }
    }

    // ── Moons on the orbits (live motion) ──
    col += moon(cpos, 1600.0, 0.050, 1.1, STAR_COL, u_time);
    col += moon(cpos, 2400.0, 0.031, 3.9, AUR_CYAN, u_time);
    col += moon(cpos, 2400.0, 0.026, 0.4, GOLD, u_time);

    // ── Comet on an ellipse, tail away from motion ──
    float ct = u_time * 0.035;
    vec2 cpo = vec2(3400.0 * cos(ct) - 800.0, 1750.0 * sin(ct));
    vec2 cd = cpos - cpo;
    if (dot(cd, cd) < 1000000.0) {
        vec2 vel = normalize(vec2(-3400.0 * sin(ct), 1750.0 * cos(ct)));
        float along = dot(cd, -vel);
        float perp = dot(cd, vec2(-vel.y, vel.x));
        float head = exp(-dot(cd, cd) / (2.0 * 18.0 * 18.0));
        float wdt = 14.0 + along * 0.06;
        float tail = along > 0.0 ? exp(-along / 260.0) * exp(-(perp * perp) / (2.0 * wdt * wdt)) : 0.0;
        col += AUR_CYAN * (head * 0.9 + tail * 0.22);
    }

    // Wormhole gates
    col += gatePortal(cpos - GATE_W, u_time);
    col += gatePortal(cpos - GATE_E, u_time);

    // Orientation dots
    const float SPACING = 140.0;
    vec2 g = mod(screen + mod(u_camera, SPACING), SPACING);
    vec2 gdd = min(g, SPACING - g);
    float dotA = 1.0 - smoothstep(1.2, 2.2, length(gdd));
    col = mix(col, GRID_COL, dotA * 0.35);

    // Vignette
    vec2 vc = v_coords - 0.5;
    col *= 1.0 - dot(vc, vc) * 0.45;

    gl_FragColor = vec4(col, 1.0);
}
