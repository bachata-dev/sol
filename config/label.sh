#!/bin/sh
# Planet name plate: "3  E A R T H  home · 10". Rendered in a transparent,
# immovable terminal parked just above the planet.
#
# The tally follows what the planet is holding, but the plate never asks: it
# reads the line `sol here` leaves in $XDG_RUNTIME_DIR/sol-plates once a
# second, so eight plates cost eight `sed`s and nothing else. Without that
# file — driftwm not running, or no bar — it just shows the name.
num=$1
name=$(printf %s "$2" | sed 's/./& /g; s/ $//')
role=$3
plain=$(printf '  %s   %s   \033[2m%s\033[0m' "$num" "$name" "$role")
file="${XDG_RUNTIME_DIR:-/tmp}/sol-plates"

printf '\033[?25l'
last=''
while :; do
  live=$(sed -n "${num}p" "$file" 2>/dev/null)
  [ -n "$live" ] || live=$plain
  if [ "$live" != "$last" ]; then
    printf '\033[H\033[2J\n%s' "$live"
    last=$live
  fi
  sleep 2
done
