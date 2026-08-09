#!/bin/bash
# sol uninstaller — removes the sol commands and the gesture daemon.
# Leaves ~/.config/driftwm in place (delete it yourself if you want it gone;
# any pre-install config was preserved as ~/.config/driftwm.bak.*).

set -e
sudo systemctl disable --now sol-spin 2>/dev/null || true
sudo rm -f /etc/systemd/system/sol-spin.service
sudo systemctl daemon-reload
sudo rm -f /usr/local/bin/sol /usr/local/bin/sol-help /usr/local/bin/sol-map /usr/local/bin/sol-cmd \
           /usr/local/bin/sol-menu /usr/local/bin/sol-session \
           /usr/local/bin/sol-spin /usr/local/bin/sol-planetarium \
           /usr/local/bin/driftwm-up
# `sol` itself is a stub in front of a module — the module goes too.
sudo rm -rf /usr/local/lib/sol

# The boot hook, if install.sh was asked for one. The autologin drop-in goes
# with it: left behind, it would log the console in for a desktop that is no
# longer installed. The block is bounded by its own markers, so this takes
# back exactly what was added and nothing a person wrote around it.
for p in "$HOME/.bash_profile" "$HOME/.profile"; do
  if [ -e "$p" ] && grep -q '^# ── sol ──' "$p"; then
    sed -i '/^# ── sol ──/,/^# ── end sol ──/d' "$p"
    echo "removed the sol block from $p"
  fi
done
for d in /etc/systemd/system/getty@tty*.service.d/autologin.conf; do
  [ -e "$d" ] && grep -q "Written by sol's install.sh" "$d" && sudo rm -f "$d" \
    && echo "removed $d"
done
sudo systemctl daemon-reload

echo "removed. ~/.config/driftwm left in place."
