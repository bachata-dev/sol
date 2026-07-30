#!/usr/bin/env python3
"""Regenerate sol's planet positions for a given date.

The canvas places each planet at its real heliocentric longitude, so the
layout is a snapshot of the actual sky. Orbit spacing is uniform rather than
true-to-scale, which keeps every hop between neighbours a comparable distance
while preserving the real order and the real angles.

    python3 tools/sol-positions.py 2026-07-30

Prints the PLANETS table for bin/sol, the position constants for
config/sol.glsl, and the label window_rules for config/config.toml.
"""

import datetime
import math
import sys

# name, mean longitude at J2000 (deg), deg/day, colour, role
BODIES = [
    ("Mercury", 252.25084, 4.09233445, "#9aa5ce", "quick",   68),
    ("Venus",   181.97973, 1.60213034, "#e0af68", "comms",  103),
    ("Earth",   100.46435, 0.98560912, "#7aa2f7", "home",   105),
    ("Mars",    355.45332, 0.52403304, "#f7768e", "ops",     81),
    ("Jupiter",  34.40438, 0.08308676, "#ff9e64", "builds", 199),
    ("Saturn",   49.94432, 0.03344414, "#e6cfa1", "media",  192),
    ("Uranus",  313.23218, 0.01172581, "#7dcfff", "spare",  159),
    ("Neptune", 304.88003, 0.00599515, "#5a7fd0", "archive", 158),
]

BASE, STEP = 1000, 820          # innermost orbit radius, spacing between orbits
LABEL_OFFSET = 400              # name plate sits this far above the planet


def main():
    when = sys.argv[1] if len(sys.argv) > 1 else "2026-07-30"
    date = datetime.date.fromisoformat(when)
    d = (date - datetime.date(2000, 1, 1)).days + 0.5

    rows = []
    for i, (name, l0, rate, colour, role, body) in enumerate(BODIES):
        lon = (l0 + rate * d) % 360
        r = BASE + STEP * i
        x = round(r * math.cos(math.radians(lon)))
        y = round(r * math.sin(math.radians(lon)))
        rows.append((i + 1, name, x, y, r, body, colour, role, lon))

    print(f"# heliocentric longitudes for {when}\n")
    print("# ── bin/sol : PLANETS ──")
    for n, name, x, y, r, body, colour, role, lon in rows:
        print(f'    ({n}, "{name}", {x:>6}, {y:>6}, {r:>4}, {body:>3}, "{colour}", "{role}"),')

    print("\n// ── config/sol.glsl : positions (y negated for shader space) ──")
    for n, name, x, y, r, body, colour, role, lon in rows:
        print(f"const vec2 P{n} = vec2({x:>8}.0, {-y:>8}.0);   // {name}  lon {lon:.1f}")
    print("float rings = " + " + ".join(f"ring(r, {r}.0, px)" for *_, in []) or "", end="")
    print("// orbit radii: " + ", ".join(str(r[4]) for r in rows))
    print(f"const float BELT_R = {BASE + 3 * STEP + STEP // 2}.0;")

    print("\n# ── config/config.toml : label placement ──")
    for n, name, x, y, r, body, colour, role, lon in rows:
        print(f'[[window_rules]]\napp_id = "planet-label-{n}"\nposition = [{x}, {y + LABEL_OFFSET}]\n')


if __name__ == "__main__":
    main()
