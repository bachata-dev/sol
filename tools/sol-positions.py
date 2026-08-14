#!/usr/bin/env python3
"""Regenerate sol's orbits and planet positions for a given date.

The canvas is a snapshot of the real sky: each planet is placed by solving
Kepler's equation for the date, so it sits on its own ellipse at the angle it
really occupies. Orbits keep their real eccentricity and perihelion direction
— the Sun sits at a focus, not at the centre — while the semi-major axes are
spaced uniformly rather than to scale, so every hop between neighbours is a
comparable distance.

    python3 tools/sol-positions.py 2026-07-30

Prints the PLANETS table for bin/sol, the orbit constants for config/sol.glsl,
and the name-plate window_rules for config/config.toml.
"""

import datetime
import math
import sys

# JPL approximate elements at J2000 and their rates per Julian century
# (valid 1800-2050). a is dropped: sol spaces the orbits uniformly instead.
#   name, e, L (mean longitude), peri (longitude of perihelion), then rates,
#   colour, role, and the body's real equatorial radius in km
BODIES = [
    ("Mercury", 0.20563593, 252.25032350,  77.45779628,
                0.00001906, 149472.67411175, 0.16047689, "#9aa5ce", "quick",    2440),
    ("Venus",   0.00677672, 181.97909950, 131.60246718,
               -0.00004107,  58517.81538729, 0.00268329, "#d08b3e", "comms",    6052),
    ("Earth",   0.01671123, 100.46457166, 102.93768193,
               -0.00004392,  35999.37244981, 0.32327364, "#7aa2f7", "home",     6371),
    ("Mars",    0.09339410,  -4.55343205, -23.94362959,
                0.00007882,  19140.30268499, 0.44441088, "#f7768e", "ops",      3390),
    ("Jupiter", 0.04838624,  34.39644051,  14.72847983,
               -0.00013253,   3034.74612775, 0.21252668, "#ff9e64", "builds",  69911),
    ("Saturn",  0.05386179,  49.95424423,  92.59887831,
               -0.00050991,   1222.49362201, -0.41897216, "#e6cfa1", "media",  58232),
    ("Uranus",  0.04725744, 313.23810451, 170.95427630,
               -0.00004397,    428.48202785, 0.40805281, "#7dcfff", "spare",   25362),
    ("Neptune", 0.00859048, -55.12002969,  44.96476227,
                0.00005105,    218.45945325, -0.32241464, "#7477e0", "archive", 24622),
]
SUN_KM = 696000

BASE, STEP = 1000, 820          # innermost semi-major axis, spacing between orbits
LABEL_OFFSET = 400              # name plate sits this far above the planet

# Discs are the cube root of the real radius, scaled so Earth is 105 across.
# One rule for every body: the ranking is exactly right and Jupiter still
# reads as a giant, without Mercury vanishing or the Sun swallowing its own
# inner orbit — which is what true scale would do (at this orbit spacing a
# true-to-scale Earth would be a hundredth of a pixel).
EARTH_KM, EARTH_PX = 6371, 105


def disc(km):
    return round(EARTH_PX * (km / float(EARTH_KM)) ** (1 / 3.0))


def kepler(mean_anom_deg, e):
    """True anomaly (rad) and radius factor r/a, from the mean anomaly."""
    m = math.radians((mean_anom_deg + 180) % 360 - 180)
    ecc = m + e * math.sin(m)
    for _ in range(24):                       # Newton; converges in a handful
        d = (ecc - e * math.sin(ecc) - m) / (1 - e * math.cos(ecc))
        ecc -= d
        if abs(d) < 1e-12:
            break
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(ecc / 2),
                        math.sqrt(1 - e) * math.cos(ecc / 2))
    return nu, 1 - e * math.cos(ecc)


def main():
    when = sys.argv[1] if len(sys.argv) > 1 else "2026-07-30"
    date = datetime.date.fromisoformat(when)
    # Julian centuries since J2000.0 (2000-01-01 12:00 TT)
    t = ((date - datetime.date(2000, 1, 1)).days - 0.5) / 36525.0

    rows = []
    for i, (name, e0, l0, w0, de, dl, dw, colour, role, km) in enumerate(BODIES):
        e = e0 + de * t
        lon = l0 + dl * t
        peri = w0 + dw * t
        nu, rho = kepler(lon - peri, e)
        a = BASE + STEP * i
        theta = math.radians(peri) + nu
        x = round(a * rho * math.cos(theta))
        y = round(a * rho * math.sin(theta))
        rows.append(dict(n=i + 1, name=name, x=x, y=y, a=a, e=e, peri=peri,
                         body=disc(km), colour=colour, role=role))

    print(f"# heliocentric positions for {when}\n")
    print("# ── bin/sol : PLANETS ──")
    for r in rows:
        print('    Planet({n}, "{name}", {x:>6}, {y:>6}, {a:>4}, {e:.5f}, '
              '{peri:>7.2f}, {body:>3}, "{colour}", "{role}"),'.format(**r))

    print("\n// ── config/sol.glsl : orbits (shader space = canvas with y negated) ──")
    for r in rows:
        w = math.radians(r["peri"])
        b = r["a"] * math.sqrt(1 - r["e"] ** 2)
        # Sun sits at a focus, so the ellipse centre is offset from the origin
        # away from perihelion. Y is negated for shader space, which also flips
        # the rotation.
        cx, cy = -r["a"] * r["e"] * math.cos(w), r["a"] * r["e"] * math.sin(w)
        print(f'const vec4 O{r["n"]} = vec4({cx:9.1f}, {cy:9.1f}, {r["a"]:6.1f}, {b:8.2f});'
              f'  // {r["name"]}')
    for r in rows:
        w = math.radians(r["peri"])
        print(f'const vec2 R{r["n"]} = vec2({math.cos(w):8.5f}, {-math.sin(w):8.5f});')
    print("\n// planets (y negated)")
    for r in rows:
        print(f'const vec2 P{r["n"]} = vec2({r["x"]:8}.0, {-r["y"]:8}.0);   // {r["name"]}')
    print(f"const float BELT_R = {BASE + 3 * STEP + STEP // 2}.0;")
    print("// discs: " + ", ".join(f'{r["name"]} {r["body"]}' for r in rows)
          + f", Sun {disc(SUN_KM)}")

    print("\n# ── config/config.toml : name-plate placement ──")
    for r in rows:
        print(f'[[window_rules]]\napp_id = "planet-label-{r["n"]}"\n'
              f'position = [{r["x"]}, {r["y"] + LABEL_OFFSET}]\n')


if __name__ == "__main__":
    main()
