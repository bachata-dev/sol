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

**The Sun sits at the origin. The eight planets sit at their real heliocentric longitudes**, one per
orbit, ordered outward: Mercury, Venus, Earth, Mars, the asteroid belt, Jupiter, Saturn, Uranus,
Neptune. `mod+1` … `mod+8` fly you to them in that same order. `mod+0` returns to the Sun.

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
| `mod+0` | fly to the Sun | | |
| `mod+left` / `mod+right` | sunward / outward | **Do** | |
| `mod+u` | whole system view | `mod+return` | terminal |
| `mod+tab` | fly-to menu | `mod+space` | launcher |
| click the map | fly there | `mod+q` `mod+f` `mod+m` | close · fullscreen · maximise |

Drag to pan, scroll to pan, pinch to zoom — and when you're zoomed out past 45%, clicking any window
flies you to it.

## What you see

**The canvas** is a single GLSL fragment shader: the Sun with its corona, eight orbit rings, planets
lit with a real day/night terminator facing the Sun, Saturn's ring, a sparse asteroid belt, and a
parallaxed starfield. It costs no windows and no meaningful CPU.

It also **gets out of your way**: at working zoom the astronomy fades to a whisper behind your
windows, and blooms as you pull back — so the same canvas is a clean workspace up close and a map
from far away.

![the whole system](screenshots/system.png)

**The map** (bottom right) is live: the planets, your windows, and a box showing exactly what you're
looking at. Click anywhere on it to fly there.

**The bar** always names where you are — "3 Earth", "6 Saturn", "deep space" — tinted that planet's
colour, so you can read your location without looking for it.

**Name plates** float beside each planet. They're ordinary windows on purpose: driftwm limits how far
you can zoom out to half the fit of the real windows on the canvas, so the plates are what hold the
canvas open wide enough for the whole-system view to exist — and they double as click-to-fly targets.

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
sol goto 4        # or: sol goto mars, sol goto sun
sol hop out       # next planet outward; `sol hop in` goes sunward
sol system        # frame the whole solar system
sol send 8        # send the focused window to Neptune
sol here          # where am I?
sol menu          # fuzzel fly-to menu
sol map           # the live map (runs inside a terminal)
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

- **Different sky** — `python3 tools/sol-positions.py 2027-03-01` prints the planet table for
  `bin/sol`, the constants for `config/sol.glsl`, and the name-plate placements for the config.
  The layout is a snapshot of the real sky, so you can set it to a date that means something.
- **Roles** — the labels ("home", "ops", "builds") are just strings in the autostart lines.
- **Shader** — every colour and coefficient is a named `const` at the top of `sol.glsl`; edits
  hot-reload on save.

Orbit spacing is uniform rather than true-to-scale: real spacing would put Neptune eighty times
further out than Mercury and make half the system unusable. The order and the angles are real; the
radial scale is legible, which also means every hop between neighbours takes about the same time.

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
