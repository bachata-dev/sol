#!/bin/bash
# sol installer — the driftwm canvas as our solar system.
# Copies config to ~/.config/driftwm (backing up anything already there),
# installs the `sol` command to /usr/local/bin, and optionally enables the
# circle-gesture daemon (a root systemd service that reads /dev/input).

set -euo pipefail
cd "$(dirname "$0")"

# The console sol boots on, if you ask it to below. tty1 is the one every
# distro leaves for a desktop; override for a machine that wants its console.
BOOT_VT="${BOOT_VT:-1}"

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
# Installed as a module with a stub in front of it, rather than as a script.
# Python caches compiled bytecode for things it imports and never for a script
# it was handed, so a 190KB `sol` run directly is 190KB re-parsed on every
# keypress: 55ms, of which 43ms is the parser and 11ms is the interpreter
# existing at all. Imported once and compiled, the same command answers in
# 24ms. Nothing about sol is on a timer, so this is not a load question — it
# is the difference between a keybinding that feels instant and one that
# nearly does, paid on every press, every menu item and every click in the bar.
say "installing sol to /usr/local/bin (sudo)"
sudo install -d /usr/local/lib/sol
sudo install -m644 bin/sol /usr/local/lib/sol/solmod.py
# Compiled as root at install time, because the directory is root-owned: a
# stale or missing .pyc is silently re-parsed and re-written by whoever runs
# it next, and that user cannot write here. Failure is only slowness, so it
# does not stop the install.
sudo python3 -m compileall -q /usr/local/lib/sol >/dev/null 2>&1 || true
printf '%s\n' '#!/usr/bin/env python3' \
  '# The sol command. The code is /usr/local/lib/sol/solmod.py, imported' \
  '# rather than run so its compiled form is cached — see install.sh.' \
  'import sys' \
  'sys.path.insert(0, "/usr/local/lib/sol")' \
  'import solmod' \
  'solmod.main()' | sudo tee /usr/local/bin/sol >/dev/null
sudo chmod 755 /usr/local/bin/sol
sudo install -m755 bin/sol-menu bin/sol-help bin/sol-map bin/sol-cmd \
                   bin/sol-session bin/driftwm-up /usr/local/bin/
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

# ── booting into sol (optional; autologin on the console VT) ──────────────
# For a machine whose job is to be this desktop. It is deliberately not the
# default: it makes the console log itself in, which is the right trade only
# when the machine is yours and physical access already means everything.
if [ "${WITH_BOOT:-ask}" = ask ]; then
  read -rp "Boot into sol? (autologin on tty$BOOT_VT, then sol-session) [y/N] " a
  [ "${a,,}" = y ] && WITH_BOOT=1 || WITH_BOOT=0
fi
if [ "$WITH_BOOT" = 1 ]; then
  sudo mkdir -p "/etc/systemd/system/getty@tty$BOOT_VT.service.d"
  sudo tee "/etc/systemd/system/getty@tty$BOOT_VT.service.d/autologin.conf" > /dev/null <<EOF
# Written by sol's install.sh. Removing this file restores the login prompt.
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable "getty@tty$BOOT_VT"

  # The profile is the one place that knows you are on the console rather
  # than at the other end of an ssh connection, so it is the profile that
  # decides whether to start a desktop at all. Written between markers so
  # re-running this replaces the block instead of stacking another copy.
  PROFILE="$HOME/.bash_profile"
  [ -e "$PROFILE" ] || PROFILE="$HOME/.profile"
  if [ -e "$PROFILE" ] && grep -q '^# ── sol ──' "$PROFILE"; then
    say "replacing the existing sol block in $PROFILE"
    sed -i '/^# ── sol ──/,/^# ── end sol ──/d' "$PROFILE"
  fi
  cat >> "$PROFILE" <<EOF
# ── sol ──────────────────────────────────────────────────────────────────
# On the console, and not already inside a session: become the desktop.
# Not \`exec\` — sol-session explains why a boot loop is worse than a prompt.
if [ -z "\${WAYLAND_DISPLAY:-}" ] && [ "\$(tty)" = "/dev/tty$BOOT_VT" ]; then
  sol-session
fi
# ── end sol ──────────────────────────────────────────────────────────────
EOF
  say "booting into sol on tty$BOOT_VT (via $PROFILE)"
fi

say "done. Set your display in the MACHINE-SPECIFIC block of $CFG/config.toml."
if [ "${WITH_BOOT:-0}" = 1 ]; then
  say "Reboot, and the machine comes up in sol."
else
  say "Start driftwm from your display manager, or on a spare VT:"
  say "  sudo driftwm-up"
fi
say "Once inside, press mod+/ for the keybinding card."
