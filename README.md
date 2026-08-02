<h1 align="center">sol</h1>

<p align="center">
  <b>Your desktop is the solar system.</b><br>
  A workspace model for <a href="https://github.com/malbiruk/driftwm">driftwm</a> —
  the Sun at the origin, eight planets in the order you learned as a child,
  and everything you already know about them doing the navigating for you.
</p>

![sol](screenshots/sol-tour.gif)

---

## The idea

[driftwm](https://github.com/malbiruk/driftwm) gives you an infinite canvas: windows live anywhere on
an endless plane and the screen is a camera looking at it. It's a lovely idea with one honest
problem — **an infinite plane is featureless**. Pan away from your windows and nothing tells you
where you are, which way is home, or where you left that terminal.

`sol` answers that by making the canvas a place you already know. Not a metaphor you have to learn —
*the* solar system, the one you can already recite.

**The Sun sits at a focus of eight real ellipses, and the planets sit where they really were**, one
per orbit, ordered outward: Mercury, Venus, Earth, Mars, the asteroid belt, Jupiter, Saturn, Uranus,
Neptune. Each one is placed by solving Kepler's equation for the date, so it rides its own orbit
line at the angle it actually occupied. `mod+1` … `mod+8` fly you to them in that same order.
`mod+0` returns to the Sun.

And the layout means something:

> **Distance from the Sun is distance from your attention.**
> Inner planets are immediate and ephemeral, the asteroid belt divides, outer planets are heavy and
> background.

| | | |
|---|---|---|
| **1 Mercury** — quick | **2 Venus** — comms | **3 Earth** — home |
| **4 Mars** — ops | · · · *asteroid belt* · · · | **5 Jupiter** — builds |
| **6 Saturn** — media | **7 Uranus** — spare | **8 Neptune** — archive |

Those roles are only defaults; what matters is that "further out" always means "further from what
I'm doing right now".

## The one rule

**The camera moves only when you ask it to.** Every automatic camera move driftwm offers is switched
off: new windows don't drag the view, opening a window doesn't reset your zoom, closing one doesn't
pan somewhere, and nothing wanders while you're reading.

When the view does move, it **travels**. Every flight is an eased path streamed at 90 Hz, so you
always see where you went — which is what makes a large canvas navigable instead of disorienting.

## Controls

Press **`mod+/`** at any time for this card on screen.

| Go | | Carry | |
|---|---|---|---|
| `mod+1` … `mod+8` | fly to a planet | `mod+ctrl+1` … `8` | send the focused window to a planet |
| `mod+0` | fly to the Sun | **A crowded planet** | |
| `mod+left` / `mod+right` | sunward / outward | `mod+a` | tidy this planet into a grid |
| `mod+u` | whole system view | `mod+n` / `mod+p` | step through its windows |
| `mod+e` | the overview | **Do** | |
| `mod+tab` | fly-to menu | `mod+return` `mod+space` | terminal · launcher |
| | | `mod+q` `mod+f` `mod+m` | close · fullscreen · maximise |

Drag to pan, scroll to pan, pinch to zoom — and when you're zoomed out past 45%, clicking any window
flies you to it.

## When a planet fills up

Ten terminals on Earth used to be ten terminals in a heap, each one 28 pixels down and to the right
of the last. Now a planet holds a **district**, and sol knows what is in it:

- **`mod+a` tidies it** into justified rows around the planet, shaped to your screen, with the name
  plate lifted clear above. The planet's own disc is reserved as a cell, so windows flow *around* it
  and it is never buried — from across the system a district reads as a lit world nested in its
  work. Rows rather than a ring of moons because rows are compact — orbits here are 820 apart while
  a terminal is 700 wide — and because a block shaped like your screen frames at a zoom where the
  windows are still *usable*, not merely visible.
- **The district gets a card**: a rounded panel in the planet's colour, painted behind the windows
  by the shader. `sol arrange` writes the rectangles into `sol.glsl` between two markers and reloads
  the config, which keeps your camera, windows and focus exactly as they were.
- **The focused window comes forward** and the rest sit a touch back, at 90% opacity.
- **`mod+3` frames the whole district** when it no longer fits at working zoom, so you arrive seeing
  everything Earth is holding. Press `mod+3` again from that overview and you drop into your window
  to get to work; press it again and you are back to the overview.
- **`mod+n` / `mod+p` step through** them one at a time, flying to each.
- **The bar and the overview count them**, so a busy planet reads as busy from across the system.

A window belongs where you put it. `mod+ctrl+3` and `mod+a` write that down, which matters because a
tidy district is wider than the gap between planets — without it the far corner of Earth's grid
would defect to Mercury. Drag a window off somewhere else and it belongs to whatever it is nearest
again.

![a planet with a full district](screenshots/district.png)

## What you see

**The canvas** is a single GLSL fragment shader: the Sun with its corona, eight orbit ellipses drawn
with the Sun at a focus — so Mercury's is visibly off-centre and Venus's is not — planets lit with a
real day/night terminator facing the Sun, Saturn's ring, a sparse asteroid belt, and a parallaxed
starfield. Every orbit is a soft hairline with a faint bloom and no hard edge, held at a constant
weight in screen pixels so it never thickens as you pull back. Each planet pools its colour into the
space around it, and each district gets a rounded card in that colour behind its windows. It costs
no windows and no meaningful CPU.

It also **gets out of your way**: at working zoom the astronomy fades to a whisper behind your
windows, and blooms as you pull back — so the same canvas is a clean workspace up close and a map
from far away.

![the whole system](screenshots/system.png)

**The overview** (`mod+e`) is the whole system at a size that can actually answer something: every
orbit drawn as a fine dotted ellipse, every district as a card, every window as a mark inside it,
and a pane naming what the planet you picked is holding. `1`…`8` fly, `↑``↓` pick a window, `⏎`
drops you into it, `a` tidies the planet, and clicking anywhere flies there. Press `mod+e` again, or
`esc`, and it is gone.

It replaced a small live map that sat in the bottom-right corner of every screen. That map was forty
cells by twenty for the entire solar system — four hundred canvas units to the cell, which put
neighbouring orbits two cells apart, squashed a whole district into two rows, and left nowhere to
say what any window was. It drew the shape of a system you already knew by heart and none of what
you would open a map for, and it did it on top of your windows, all day. **Asking for it is what
makes it worth having**: nothing is parked, so it can take the room it needs to be legible.

![the overview](screenshots/overview.png)

**The bar** borrows the grammar of the macOS menu bar, because the mapping turns out to be exact:
the planet you are standing on is the frontmost application. So `☉` opens sol's menu where the Apple
menu would be, the place is named in **bold** where the app name goes — "Earth", "Saturn", "the
system", "deep space", in that planet's colour — and what it holds ("home · 10") reads as that app's
menus. Status sits on the right, monochrome and quiet, then Control Centre, then the clock last.

In the middle is **the strip**: all eight planets at once, `①②③④ ┊ ⑤⑥⑦⑧`, each in its own colour with
a small tally, dim when empty, underlined where you are. It is ordinal rather than spatial on
purpose — nobody flies by angle, they fly by number — and the belt keeps its place in the middle as
the divide it is. Scroll it to travel sunward and outward, the way you scroll a volume icon.

Only one module in the bar ever asks driftwm anything. `sol here` runs once a second, and leaves the
other modules' answers in a file for them to read, so eight planets' worth of tally costs one query.

**Name plates** float beside each planet, naming it and counting what it holds — "3  E A R T H
home · 10". They're ordinary windows on purpose: driftwm limits how far you can zoom out to half the
fit of the real windows on the canvas, so the plates are what hold the canvas open wide enough for
the whole-system view to exist — and they double as click-to-fly targets. Keeping the tally live
costs nothing: `sol here`, which the bar already runs once a second, leaves the lines in a file and
each plate just reads its own.

![a planet](screenshots/planet.png)

Press `mod+/` for the card, any time:

![keybindings](screenshots/help.png)

## Install

```sh
git clone https://github.com/bachata-dev/sol
cd sol
./install.sh
```

Then set your display in the `MACHINE-SPECIFIC` block of `~/.config/driftwm/config.toml` (connector
name and HiDPI scale — find yours in `driftwm msg state`) and start driftwm from your display
manager's session list, or on a spare VT:

```sh
sudo driftwm-up          # defaults to VT 3
```

**Requirements:** [driftwm](https://github.com/malbiruk/driftwm), `foot`, `python3`, `awk`;
optionally `waybar`, `fuzzel`, `mako`; JetBrains Mono plus a Nerd Font for the bar glyphs.
[Omarchy](https://omarchy.org) keybindings light up automatically if omarchy is installed, and are
harmless if not.

## The `sol` command

Everything the keybindings do is available directly, and the whole toolkit is one command:

```sh
sol goto 4        # or: sol goto mars, sol goto ops, sol goto sun
sol hop out       # next planet outward; `sol hop in` goes sunward
sol system        # frame the whole solar system
sol arrange       # tidy this planet's windows; `sol arrange all` does every one
sol next          # step to the next window here; `sol prev` goes back
sol send 8        # send the focused window to Neptune; `--stay` to not follow
sol list          # what is where
sol plate 3       # the line Earth's name plate is showing
sol here          # where am I?
sol menu          # the ☉ menu: everywhere to go, and what to do
sol map           # the overview (runs inside a terminal; sol-map toggles it)
sol bar strip     # one line of the bar — where, holding, or strip
sol help          # the keybinding card
```

## Opt-in extras

Nothing below runs unless you turn it on, because each one moves the camera without being asked.

- **`sol-planetarium`** — after four idle minutes, glides the camera in a slow orbit of the system
  (~8 minutes per revolution) and hands it straight back on any key or mouse movement. Add
  `"sol-planetarium"` to `autostart` in the config.
- **`sol-spin`** — draw a circle with the mouse to travel outward (clockwise) or sunward
  (counter-clockwise). Root systemd service, since it reads `/dev/input`:
  `sudo systemctl enable --now sol-spin`. It also stamps input activity, which is how the
  planetarium tells real idleness from you simply not panning.

## Make it yours

- **Different sky** — `python3 tools/sol-positions.py 2027-03-01` solves the orbits for that date and
  prints the planet table for `bin/sol`, the orbit constants for `config/sol.glsl`, and the
  name-plate placements for the config. The layout is a snapshot of the real sky, so you can set it
  to a date that means something.
- **Roles** — the labels ("home", "ops", "builds") are just strings in the autostart lines.
- **Sizes** — every disc comes from one rule in `tools/sol-positions.py`: the cube root of the body's
  real radius, with Earth at 105. Change `EARTH_PX` to scale them all, or the exponent for a
  different compression.
- **Shader** — every colour and coefficient is a named `const` at the top of `sol.glsl`. Saving the
  file is not enough on its own: press `mod+shift+c` to reload the config and the shader comes with
  it. The only lines `sol` ever writes are the district rectangles between the two `── districts ──`
  markers; delete the markers and you simply get no cards.

## What's real, and what isn't

Real: the order, the angles, the eccentricities and the perihelion directions. Each planet is placed
by solving Kepler's equation for the date, so it sits on its own ellipse where it actually was, and
the Sun sits at a focus of all eight.

Two things are deliberately not to scale, because true scale is unusable:

- **Orbit spacing is uniform** — 1000, 1820, 2640 … 6740. In reality Neptune orbits 78× further out
  than Mercury; here it is 6.7×. Even spacing keeps the whole system reachable and makes every hop
  between neighbours take about the same time.
- **Discs are the cube root of the real radii**, scaled so Earth is 105 across. One rule for every
  body, so the ranking is exactly right — Jupiter is the giant, Mercury the pebble, and the Sun
  dwarfs all of it — without the giants swallowing their own orbits. At true scale, with Neptune's
  orbit where it is, Earth would be a hundredth of a pixel.

The two scales are also independent of each other: relative to its own orbit, every planet is drawn
hundreds of times too large. Distance means "how far from what I'm doing", not kilometres.

## Uninstall

```sh
./uninstall.sh    # removes the commands and the daemon; your config stays put
```

## Status

Developed and daily-driven on Debian 13 with AMD graphics and a 4K display. It should work anywhere
driftwm runs; display scale, fonts, and the `/dev/input` bits are where another machine is most
likely to need a nudge. Issues and PRs welcome.

## Credits

- [driftwm](https://github.com/malbiruk/driftwm) by Klim Kostiuk — the infinite-canvas compositor
  that makes any of this possible
- [Tokyo Night](https://github.com/enkia/tokyo-night-vscode-theme) palette by enkia

## License

GPL-3.0, matching driftwm. See [LICENSE](LICENSE).
