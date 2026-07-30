#!/bin/sh
# Floating region label on the driftwm canvas (spawned from autostart).
txt=$(printf %s "$1" | tr '[:lower:]' '[:upper:]' | sed 's/./& /g; s/ $//')
printf '\033[?25l\n\n   %s' "$txt"
exec sleep infinity
