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

# Hide the cursor, and turn off line wrapping. A plate is one row tall, so a
# line even one column too long does not merely spill — it wraps, scrolls, and
# leaves the end of the name showing where the start should be. Clipping is the
# honest failure here; scrolling looks like a different bug entirely.
printf '\033[?25l\033[?7l'
last=''

# Woken, not polling. Eight plates checking a file twice a second was eight
# processes a second spent almost entirely on finding it unchanged, and on a
# four-core machine that churn is paid whether or not anyone is looking. So
# `sol watch` signals us when the file really moves, and the long sleep below
# is only a safety net: if a signal is ever missed, or sol is not running at
# all, the plate still catches up within the minute instead of freezing.
#
# The sleep runs in the background and is waited on, because a signal does not
# interrupt `sleep` itself — it interrupts `wait`. That is the whole trick.
trap ':' USR1
while :; do
  live=$(sed -n "${num}p" "$file" 2>/dev/null)
  [ -n "$live" ] || live=$plain
  if [ "$live" != "$last" ]; then
    printf '\033[H\033[2J\n%s' "$live"
    last=$live
  fi
  sleep 60 &
  wait $! 2>/dev/null
  kill $! 2>/dev/null
done
