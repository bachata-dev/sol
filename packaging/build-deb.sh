#!/bin/bash
# Build sol as a .deb. Run from the top of a checkout, on any Debian machine
# with dpkg-deb; produces sol_<version>_all.deb beside the tree.
#
#     ./packaging/build-deb.sh
#
# Architecture is `all` because there is nothing here to compile: sol is
# Python, its canvas is a shader the GPU compiles at load, and the only thing
# resembling a build step is byte-compiling the module, which the postinst
# does on the machine that will run it.
#
# ── what a package may and may not do ─────────────────────────────────────
# A .deb owns files under /usr and nothing under /home. That is not a
# limitation to work around, it is the correct division: a package is
# installed once for a machine and a config belongs to a person, and the
# config here has your monitor's connector name in it. So the package ships
# the commands and a config *template* under /usr/share/sol, and `sol setup`
# copies it into your home directory when you ask it to.
#
# driftwm is a Depends this package cannot declare, because driftwm is not in
# Debian — a dependency on a package that does not exist makes the .deb
# uninstallable rather than informative. It is documented, `sol doctor` says
# so in as many words, and every sol command exits cleanly when it is absent.
set -euo pipefail

cd "$(dirname "$0")/.."
VERSION=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' bin/sol)
[ -n "$VERSION" ] || { echo "build-deb: no VERSION in bin/sol" >&2; exit 1; }

ROOT=$(mktemp -d)
trap 'rm -rf "$ROOT"' EXIT
PKG="sol_${VERSION}_all.deb"

install -d "$ROOT/DEBIAN" "$ROOT/usr/bin" "$ROOT/usr/lib/sol" \
           "$ROOT/usr/share/sol/config" "$ROOT/usr/share/sol/tools" \
           "$ROOT/usr/share/doc/sol" "$ROOT/usr/share/wayland-sessions" \
           "$ROOT/usr/share/xdg-desktop-portal" "$ROOT/usr/lib/systemd/user"

# The code, and the seven-line doorway in front of it. See install.sh for why
# it is imported rather than run: Python caches bytecode for what it imports
# and never for a script it was handed, which is 31ms on every keypress.
install -m644 bin/sol "$ROOT/usr/lib/sol/solmod.py"
cat > "$ROOT/usr/bin/sol" <<'STUB'
#!/usr/bin/env python3
# The sol command. The code is /usr/lib/sol/solmod.py, imported rather than
# run so its compiled form is cached — see packaging/build-deb.sh.
#
# The guard is not decoration. Anything that loads sol for its functions
# rather than its command — sol-menu does — would otherwise find this file on
# the path, import it, and run a command nobody asked for.
import sys
sys.path.insert(0, "/usr/lib/sol")
import solmod
if __name__ == "__main__":
    solmod.main()
STUB
chmod 755 "$ROOT/usr/bin/sol"

install -m755 bin/sol-menu bin/sol-help bin/sol-map bin/sol-cmd \
              bin/sol-ripple bin/sol-session bin/sol-mcp \
              bin/sol-planetarium bin/sol-spin \
              bin/driftwm-up bin/driftwm-background-next "$ROOT/usr/bin/"

# The two files that are the machine's business rather than a person's, and
# so belong to the package: the session a login screen offers, and the portal
# backends that session uses. Both are keyed to XDG_CURRENT_DESKTOP, which is
# why they are named for it and not for the compositor underneath.
install -m644 config/sol.desktop "$ROOT/usr/share/wayland-sessions/sol.desktop"
install -m644 config/sol-portals.conf \
              "$ROOT/usr/share/xdg-desktop-portal/sol-portals.conf"
# The handle `sol session-ready` pulls: graphical-session.target refuses to be
# started by hand, so something has to depend on it, and this is that thing.
install -m644 config/sol-session.target \
              "$ROOT/usr/lib/systemd/user/sol-session.target"

# The config template. Not installed into anyone's home directory — `sol
# setup` does that, when the person it belongs to asks for it.
install -m644 config/* "$ROOT/usr/share/sol/config/"
# ...and not those two again, which are not yours to edit per-user.
rm -f "$ROOT/usr/share/sol/config/sol.desktop" \
      "$ROOT/usr/share/sol/config/sol-portals.conf" \
      "$ROOT/usr/share/sol/config/sol-session.target"
chmod 755 "$ROOT/usr/share/sol/config/label.sh"
install -m755 tools/acceptance.py tools/sol-hand.py tools/sol-positions.py \
              "$ROOT/usr/share/sol/tools/"
install -m644 README.md "$ROOT/usr/share/doc/sol/"
install -m644 LICENSE "$ROOT/usr/share/doc/sol/copyright"
gzip -9n -c packaging/changelog > "$ROOT/usr/share/doc/sol/changelog.Debian.gz"

sed "s/@VERSION@/$VERSION/" packaging/control > "$ROOT/DEBIAN/control"
install -m755 packaging/postinst "$ROOT/DEBIAN/postinst"
install -m755 packaging/prerm "$ROOT/DEBIAN/prerm"
# The config template is a conffile in spirit but not in fact: nothing reads
# it from /usr/share, so dpkg has no reason to ask about replacing it.

fakeroot dpkg-deb --build --root-owner-group "$ROOT" "$PKG" >/dev/null
echo "$PKG"
dpkg-deb --info "$PKG" | sed -n '2,12p'
