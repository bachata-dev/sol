#!/bin/bash
# sol installer — a Tokyo Night solar system for driftwm.
# Copies config to ~/.config/driftwm (backing up anything already there),
# installs companion tools to /usr/local/bin (sudo), and optionally enables
# the circle-gesture daemon (root systemd service reading /dev/input).

set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\033[38;2;122;162;247m▸\033[0m %s\n' "$*"; }
warn() { printf '\033[38;2;224;175;104m!\033[0m %s\n' "$*"; }

# ── dependency check ──────────────────────────────────────────────────────
missing=()
for c in driftwm foot fuzzel waybar awk; do
  command -v "$c" > /dev/null || missing+=("$c")
done
if [ "${#missing[@]}" -gt 0 ]; then
  warn "missing required commands: ${missing[*]}"
  warn "install them first (driftwm: https://github.com/malbiruk/driftwm)"
  exit 1
fi
for c in btop fastfetch mako; do
  command -v "$c" > /dev/null || warn "optional: '$c' not found — the $c autostart entry will no-op"
done

# ── config ────────────────────────────────────────────────────────────────
CFG="$HOME/.config/driftwm"
if [ -e "$CFG" ]; then
  BAK="$CFG.bak.$(date +%Y%m%d-%H%M%S)"
  say "backing up existing $CFG -> $BAK"
  mv "$CFG" "$BAK"
fi
mkdir -p "$CFG"
cp config/* "$CFG/"
chmod +x "$CFG/astrolabe.sh" "$CFG/label.sh" "$CFG/info.sh"
ln -sf "$CFG/sol.glsl" "$CFG/background.glsl"
say "config installed to $CFG"

# ── companion tools ───────────────────────────────────────────────────────
say "installing companion tools to /usr/local/bin (sudo)"
sudo install -m755 bin/driftwm-warp bin/driftwm-region bin/driftwm-orbit \
  bin/driftwm-background-next bin/driftwm-wormholed bin/driftwm-planetarium \
  bin/driftwm-spin bin/driftwm-up /usr/local/bin/

# ── circle-gesture daemon (optional; root, reads /dev/input) ──────────────
if [ "${WITH_SPIN:-ask}" = ask ]; then
  read -rp "Enable the circle-gesture daemon (draw a circle to cycle windows; root systemd service reading raw mouse input)? [y/N] " a
  [ "${a,,}" = y ] && WITH_SPIN=1 || WITH_SPIN=0
fi
if [ "$WITH_SPIN" = 1 ]; then
  sudo install -m644 systemd/driftwm-spin.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now driftwm-spin
  say "circle-gesture daemon enabled"
fi

say "done. Review the MACHINE-SPECIFIC output section in $CFG/config.toml"
say "then start driftwm: from a display manager session entry, or on a spare VT:"
say "  sudo driftwm-up"
