#!/bin/bash
# ASTROLABE — live star chart HUD + click-to-fly navigation console.
# Renders the universe map ~1-2 fps from `driftwm msg state`; enables terminal
# mouse reporting (SGR) so a left click on the map flies the camera to that
# spot (and returns to working zoom if you were zoomed far out).

TSV="$HOME/.config/driftwm/regions.tsv"
W=44; H=11
X0=-5600; X1=5600; Y0=-3600; Y1=3600

printf '\033[?25l\033[2J\033[?1006h\033[?1000h'
trap 'printf "\033[?1000l\033[?1006l\033[?25h"' EXIT

render() {
  local S FRAME
  S=$(timeout 3 driftwm msg state 2>/dev/null) || return
  FRAME=$(awk -v tsv="$TSV" -v W="$W" -v H="$H" -v X0="$X0" -v X1="$X1" -v Y0="$Y0" -v Y1="$Y1" '
    function P(x, y,  rr, cc) {
      cc = int((x - X0) / (X1 - X0) * W)
      rr = int((Y1 - y) / (Y1 - Y0) * H)
      if (rr >= 0 && rr < H && cc >= 0 && cc < W) return rr SUBSEP cc
      return ""
    }
    /^camera / { cx = $2; cy = $3 }
    /^zoom /   { z = $2 }
    /#[0-9]+ / {
      app = ""; x = ""; y = ""
      for (i = 1; i <= NF; i++) if ($i ~ /^\[/) { app = $(i - 1); x = $i; y = $(i + 1) }
      if (app == "" || app ~ /region-label|astrolabe/) next
      gsub(/[\[,]/, "", x); gsub(/[\],]/, "", y)
      p = P(x + 0, y + 0); if (p != "") win[p] = 1
    }
    END {
      while ((getline line < tsv) > 0) {
        n = split(line, f, "\t"); if (n < 3) continue
        p = P(f[2] + 0, f[3] + 0)
        if (p != "") reg[p] = substr(f[1], 1, 1)
      }
      if (z + 0 == 0) z = 1
      hw = 960 / z; hh = 540 / z
      cl = int((cx - hw - X0) / (X1 - X0) * W); cr = int((cx + hw - X0) / (X1 - X0) * W)
      ct = int((Y1 - (cy + hh)) / (Y1 - Y0) * H); cb = int((Y1 - (cy - hh)) / (Y1 - Y0) * H)
      DIM = "\033[38;2;65;72;104m";   FG   = "\033[38;2;192;202;245m"
      CAM = "\033[38;2;125;207;255m"; BLUE = "\033[38;2;122;162;247m"
      GRN = "\033[38;2;158;206;106m"; PURP = "\033[38;2;187;154;247m"
      ORNG = "\033[38;2;255;158;100m"; RST = "\033[0m"
      out = ""
      for (r = 0; r < H; r++) {
        row = " "
        for (c = 0; c < W; c++) {
          ch = " "; cc = DIM
          if ((r * 7 + c * 3) % 29 == 0) { ch = "." }
          p = r SUBSEP c
          if (p in reg) {
            ch = reg[p]
            if (ch == "D") cc = BLUE
            else if (ch == "O") cc = GRN
            else if (ch == "I") cc = PURP
            else if (ch == "S") cc = ORNG
            else { ch = "@"; cc = CAM }
          }
          if (p in win) { ch = "*"; cc = FG }
          onH = (r == ct || r == cb) && c >= cl && c <= cr
          onV = (c == cl || c == cr) && r >= ct && r <= cb
          if (onH || onV) { ch = (onH && onV) ? "+" : (onH ? "-" : "|"); cc = CAM }
          row = row cc ch RST
        }
        out = out row "\n"
      }
      printf "%s", out
    }' <<< "$S")
  printf '\033[H%s' "$FRAME"
}

fly_to_cell() {
  # terminal cell (1-based col,row) -> world coords -> fly there
  local col=$1 row=$2 WX WY Z
  read -r WX WY < <(awk -v c="$col" -v r="$row" -v W="$W" -v H="$H" \
    -v X0="$X0" -v X1="$X1" -v Y0="$Y0" -v Y1="$Y1" 'BEGIN {
      printf "%.0f %.0f", X0 + (c - 2 + 0.5) * (X1 - X0) / W, Y1 - (r - 1 + 0.5) * (Y1 - Y0) / H
    }')
  Z=$(timeout 2 driftwm msg zoom 2>/dev/null | awk '{print $NF}')
  awk -v z="$Z" 'BEGIN { exit !(z < 0.45) }' && driftwm msg zoom 1 > /dev/null 2>&1
  driftwm msg camera "$WX" "$WY" > /dev/null 2>&1
}

i=0
render
while :; do
  if IFS= read -rsn1 -t 0.25 ch && [[ $ch == $'\033' ]]; then
    seq=""
    while IFS= read -rsn1 -t 0.02 c2; do
      seq+="$c2"
      [[ $c2 == M || $c2 == m ]] && break
    done
    if [[ $seq =~ \<([0-9]+)\;([0-9]+)\;([0-9]+)M ]] && [ "${BASH_REMATCH[1]}" = "0" ]; then
      fly_to_cell "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
    fi
  fi
  i=$((i + 1))
  if (( i % 2 == 0 )); then render; fi
done
