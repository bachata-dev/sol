#!/bin/bash
# sol uninstaller — removes companion tools and the gesture daemon.
# Leaves ~/.config/driftwm in place (delete it yourself if you want it gone;
# any pre-install config was preserved as ~/.config/driftwm.bak.*).

set -e
sudo systemctl disable --now driftwm-spin 2>/dev/null || true
sudo rm -f /etc/systemd/system/driftwm-spin.service
sudo systemctl daemon-reload
sudo rm -f /usr/local/bin/driftwm-{warp,region,orbit,background-next,wormholed,planetarium,spin,up}
echo "removed. ~/.config/driftwm left in place."
