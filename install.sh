#!/bin/bash
# sol installer — the driftwm canvas as our solar system.
# Copies config to ~/.config/driftwm (backing up anything already there),
# installs the `sol` command to /usr/local/bin, and optionally enables the
# circle-gesture daemon (a root systemd service that reads /dev/input).

set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[38;2;122;162;247m▸\033[0m %s\n' "$*"; }
warn() { printf '\033[38;2;224;175;104m!\033[0m %s\n' "$*"; }

# ── dependency check ──────────────────────────────────────────────────────
missing=()
for c in driftwm foot python3 awk; do
  command -v "$c" > /dev/null || missing+=("$c")
done
if [ "${#missing[@]}" -gt 0 ]; then
  warn "missing required commands: ${missing[*]}"
  warn "install them first (driftwm: https://github.com/malbiruk/driftwm)"
  exit 1
fi
for c in waybar fuzzel mako; do
  command -v "$c" > /dev/null || warn "optional: '$c' not found — its autostart entry will no-op"
done
# The context menu is a layer-shell surface, which is what keeps it the same
# menu at every zoom — so it needs GTK and gtk-layer-shell. Without them
# right-click has nothing to open; everything else works.
python3 - <<'PY' || warn "the ☉ context menu needs python3-gi (GTK 3) and libgtk-layer-shell — right-click will not open without them"
import ctypes, gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
ctypes.CDLL("libgtk-layer-shell.so.0")
PY

# ── config ────────────────────────────────────────────────────────────────
CFG="$HOME/.config/driftwm"
if [ -e "$CFG" ]; then
  BAK="$CFG.bak.$(date +%Y%m%d-%H%M%S)"
  say "backing up existing $CFG -> $BAK"
  mv "$CFG" "$BAK"
fi
mkdir -p "$CFG"
cp config/* "$CFG/"
chmod +x "$CFG/label.sh"
say "config installed to $CFG"

# ── the sol command ───────────────────────────────────────────────────────
say "installing sol to /usr/local/bin (sudo)"
sudo install -m755 bin/sol bin/sol-menu bin/sol-help bin/sol-map bin/sol-cmd bin/driftwm-up /usr/local/bin/
# opt-in extras: installed, but nothing starts them until you say so
sudo install -m755 bin/sol-planetarium bin/sol-spin /usr/local/bin/

# ── circle-gesture daemon (optional; root, reads /dev/input) ──────────────
if [ "${WITH_SPIN:-ask}" = ask ]; then
  read -rp "Enable the circle-gesture daemon (draw a circle to travel between planets; root systemd service reading raw input)? [y/N] " a
  [ "${a,,}" = y ] && WITH_SPIN=1 || WITH_SPIN=0
fi
if [ "$WITH_SPIN" = 1 ]; then
  sudo install -m644 systemd/sol-spin.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now sol-spin
  say "circle-gesture daemon enabled"
fi

say "done. Set your display in the MACHINE-SPECIFIC block of $CFG/config.toml,"
say "then start driftwm from your display manager, or on a spare VT:"
say "  sudo driftwm-up"
say "Once inside, press mod+/ for the keybinding card."
