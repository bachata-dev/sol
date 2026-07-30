#!/bin/sh
# Planet name plate: "3  E A R T H  home". Rendered in a transparent,
# immovable terminal parked just above the planet.
num=$1
name=$(printf %s "$2" | sed 's/./& /g; s/ $//')
role=$3
printf '\033[?25l\n  %s   %s   \033[2m%s\033[0m' "$num" "$name" "$role"
exec sleep infinity
