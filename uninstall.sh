#!/bin/bash
# sol uninstaller — removes the sol commands and the gesture daemon.
# Leaves ~/.config/driftwm in place (delete it yourself if you want it gone;
# any pre-install config was preserved as ~/.config/driftwm.bak.*).

set -e
sudo systemctl disable --now sol-spin 2>/dev/null || true
sudo rm -f /etc/systemd/system/sol-spin.service
sudo systemctl daemon-reload
sudo rm -f /usr/local/bin/sol /usr/local/bin/sol-help /usr/local/bin/sol-map \
           /usr/local/bin/sol-spin /usr/local/bin/sol-planetarium \
           /usr/local/bin/driftwm-up
echo "removed. ~/.config/driftwm left in place."
