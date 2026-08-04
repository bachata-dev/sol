#!/usr/bin/env python3
"""sol acceptance tests — run inside a live driftwm session.

Not unit tests. This drives the installed commands against a real compositor
and a real canvas, because almost everything sol has ever got wrong has been
about the seam between them: a claim file that disagreed with the census, a
menu row that could be clicked but not selected, a window that settled onto
the wrong planet. Those do not show up against a mock.

    sol-hand is used where a test needs a hand — the ☉ menu's keyboard is not
    reachable any other way. Where a test would otherwise take the machine
    down, the power commands are swapped for `touch`, so "Restart" is proved
    to fire without proving it by rebooting.

Usage:  ./acceptance.py [pattern ...]     (no pattern runs everything)
"""

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time

SOL = "/usr/local/bin/sol"
HAND = "/usr/local/bin/sol-hand"
GREEN, RED, YELLOW, DIM, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m")

results = []
_spawned = []


# ── the harness ───────────────────────────────────────────────────────────
def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    mark = GREEN + "PASS" + OFF if ok else RED + "FAIL" + OFF
    line = "  %s  %s" % (mark, name)
    if detail and not ok:
        line += "\n        %s%s%s" % (DIM, detail, OFF)
    print(line, flush=True)
    return ok


def run(*argv, **kw):
    return subprocess.run(list(argv), capture_output=True, text=True,
                          timeout=kw.get("timeout", 30))


def sol(*args, **kw):
    return run(SOL, *args, **kw)


def msg(*args, **kw):
    return run("driftwm", "msg", *args, **kw)


def state():
    out = msg("state", "--json").stdout
    return json.loads(out)["Ok"]["State"]


def load_sol():
    """The installed sol, as a module, for the parts worth testing directly."""
    loader = importlib.machinery.SourceFileLoader("sol_mod", SOL)
    spec = importlib.util.spec_from_loader("sol_mod", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def spawn(n, settle=0.6):
    """n terminals on the canvas, and the ids they arrived as."""
    before = {w["id"] for w in state().get("windows", [])}
    for _ in range(n):
        msg("action", "spawn", "foot")
        time.sleep(0.35)
    time.sleep(settle)
    after = state().get("windows", [])
    fresh = [w["id"] for w in after if w["id"] not in before]
    _spawned.extend(fresh)
    return fresh


def cleanup():
    for wid in _spawned:
        msg("close", "--id", str(wid))
        time.sleep(0.08)


def windows_of(st, place_n, mod):
    return [w["id"] for w in mod.assignment(st).get(place_n, [])]


# ── 1. the commands answer at all ─────────────────────────────────────────
def test_command_surface(mod):
    print("\n1. every command answers")
    for args in (["here"], ["here", "--waybar"], ["list"], ["system"],
                 ["goto", "3"], ["goto", "earth"], ["goto", "home"],
                 ["hop", "out"], ["hop", "in"], ["arrange"], ["gather"],
                 ["sweep"], ["plate", "3"], ["bar", "where"],
                 ["bar", "holding"], ["bar", "strip"], ["bar", "last"],
                 ["next"], ["prev"], ["help"], ["doctor"]):
        r = sol(*args)
        check("sol %s exits 0" % " ".join(args), r.returncode == 0,
              (r.stderr or r.stdout)[:200])


def test_json_lines(mod):
    print("\n2. what waybar reads is valid json")
    for part in ("where", "holding", "strip", "last"):
        r = sol("bar", part)
        try:
            got = json.loads(r.stdout)
            ok = isinstance(got, dict) and "text" in got
        except ValueError as e:
            got, ok = e, False
        check("sol bar %s is a json object with text" % part, ok, got)
    r = sol("here", "--waybar")
    try:
        ok = "text" in json.loads(r.stdout)
    except ValueError:
        ok = False
    check("sol here --waybar is json", ok, r.stdout[:120])


# ── 3. bad input is refused, not crashed on ───────────────────────────────
def test_error_paths(mod):
    print("\n3. bad input is refused clearly")
    r = sol("goto", "pluto")
    check("unknown planet exits non-zero", r.returncode != 0, r.stdout[:120])
    check("unknown planet says what it wanted",
          "planet" in (r.stderr + r.stdout).lower(), r.stderr[:120])

    r = sol("bar", "nonsense")
    check("unknown bar part exits non-zero", r.returncode != 0)

    r = sol("gather", "atlantis")
    check("gather to nowhere exits non-zero", r.returncode != 0)

    # The CLI and the footer's command line are two dispatchers with two
    # different jobs. The CLI is talking to a shell, so it exits non-zero and
    # lists what it does know; the prompt is talking to a person mid-keystroke,
    # so it guesses at what they meant.
    r = sol("xyzzy", timeout=20)
    out = r.stdout + r.stderr
    check("the CLI refuses an unknown command non-zero", r.returncode != 0)
    check("the CLI names the command it did not know", "xyzzy" in out, out[:200])
    check("the CLI lists what it does know", "gather" in out and "goto" in out,
          out[:200])

    def prompt(line):
        return subprocess.run([SOL, "prompt"], input=line + "\n",
                              capture_output=True, text=True, timeout=25)

    r = prompt("gathr")
    check("the prompt suggests the nearest real word for a typo",
          "no such command" in r.stdout and "gather?" in r.stdout,
          r.stdout[:200])

    r = prompt("qqqqqq")
    # " — word?" is the suggestion; nothing is near enough to qqqqqq to earn
    # one. (Not a bare "?" test: the cursor escape \033[?25h contains one.)
    check("the prompt says 'no such command' with nothing to suggest",
          "no such command" in r.stdout and "?\n" not in r.stdout,
          repr(r.stdout[:200]))

    r = prompt("jupiter")
    check("the prompt reads a bare planet name as 'go there'",
          r.returncode == 0, (r.stderr or r.stdout)[:200])


# ── 4. a damaged claims file must not take sol down ───────────────────────
def test_corrupt_state_files(mod):
    print("\n4. damaged state files are survived (the read_map regression)")
    claims = mod.CLAIMS
    saved = None
    if os.path.exists(claims):
        saved = open(claims).read()
    try:
        for label, content in (("a json list", "[1,2,3]"),
                               ("a null value", '{"1": null}'),
                               ("truncated", '{"1": 3, "2":'),
                               ("not json", "hello"),
                               ("a nested map", '{"1": {"a": 1}}')):
            open(claims, "w").write(content)
            r = sol("here")
            check("sol survives a claims file that is %s" % label,
                  r.returncode == 0, (r.stderr or r.stdout)[:200])
    finally:
        if saved is None:
            os.path.exists(claims) and os.remove(claims)
        else:
            open(claims, "w").write(saved)


# ── 5. districts: the rule, and its two halves ────────────────────────────
def test_districts(mod):
    print("\n5. districts, claims and the adrift list")
    ids = spawn(3)
    check("three terminals arrived", len(ids) == 3, ids)
    if len(ids) != 3:
        return

    # send one to Neptune and check the claim took
    r = sol("send", "8", "--stay")
    check("sol send exits 0", r.returncode == 0, r.stderr[:200])
    time.sleep(1.2)
    st = state()
    on8 = windows_of(st, 8, mod)
    check("a window is now on Neptune", len(on8) >= 1, on8)

    # the census and the adrift list must partition every real window
    st = state()
    counted = sum(len(v) for v in mod.assignment(st).values())
    lost = len(mod.adrift(st))
    total = len(mod.real_windows(st))
    check("census + adrift == every window (%d + %d == %d)"
          % (counted, lost, total), counted + lost == total)

    # drag one into deep space: it must become adrift, and gather must fetch it
    victim = ids[0]
    msg("move", "--id", str(victim), "--", "99000", "99000")
    time.sleep(1.5)
    st = state()
    check("a window in deep space is reported adrift",
          victim in [w["id"] for w in mod.adrift(st)],
          [w["id"] for w in mod.adrift(st)])

    r = sol("gather")
    check("sol gather exits 0", r.returncode == 0, r.stderr[:200])
    time.sleep(2.0)
    st = state()
    check("nothing is adrift after gather", len(mod.adrift(st)) == 0,
          [w["id"] for w in mod.adrift(st)])
    check("the gathered window is on the Sun",
          victim in windows_of(st, 0, mod), windows_of(st, 0, mod))


# ── 6. arrange lays a grid that does not overlap ──────────────────────────
def test_arrange(mod):
    print("\n6. arrange lays a grid")
    sol("goto", "3")
    time.sleep(1.0)
    spawn(4)
    r = sol("arrange", "3")
    check("sol arrange exits 0", r.returncode == 0, r.stderr[:200])
    time.sleep(2.0)
    st = state()
    wins = mod.assignment(st).get(3, [])
    check("Earth holds the windows", len(wins) >= 4, len(wins))

    boxes = [(w["position"], w["size"]) for w in wins[:mod.DECK]]
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (ax, ay), (aw, ah) = boxes[i]
            (bx, by), (bw, bh) = boxes[j]
            if abs(ax - bx) * 2 < (aw + bw) and abs(ay - by) * 2 < (ah + bh):
                overlaps.append((i, j))
    check("no two tidied windows overlap", not overlaps, overlaps)


# ── 7. the shader gets its cards ──────────────────────────────────────────
def test_cards(mod):
    print("\n7. the district cards reach the shader")
    sol("arrange", "3")
    time.sleep(1.5)
    src = open(mod.SHADER).read()
    check("the shader still has its markers",
          mod.CARD_HEAD in src and mod.CARD_TAIL in src)
    block = src.split(mod.CARD_HEAD)[1].split(mod.CARD_TAIL)[0]
    live = [ln for ln in block.splitlines()
            if ln.startswith("const vec4 D") and "0.0, 0.0, 0.0, 0.0" not in ln]
    check("at least one district has a real card", len(live) >= 1,
          block.strip()[:200])
    check("every card line is well formed",
          all(ln.rstrip().endswith(");") for ln in block.splitlines()
              if ln.startswith("const vec4")))


# ── 8. the camera travels, and lands ──────────────────────────────────────
def test_flight(mod):
    print("\n8. the camera goes where it is sent")
    for token, place in (("3", mod.PLANETS[2]), ("8", mod.PLANETS[7]),
                         ("sun", mod.SUN)):
        sol("goto", token)
        time.sleep(1.6)
        st = state()
        cx, cy = mod.active_output(st)["camera"]
        near, dist = mod.nearest(cx, cy)
        check("goto %s lands nearest %s (%.0f away)"
              % (token, place.name, dist), near.n == place.n,
              "landed nearest %s at (%.0f, %.0f)" % (near.name, cx, cy))

    # From Neptune, not the Sun: the whole-system view is centred on the Sun,
    # so starting there would prove nothing about the camera having travelled.
    sol("goto", "8")
    time.sleep(1.6)
    before = mod.active_output(state())["camera"]
    sol("system")
    time.sleep(1.8)
    st = state()
    out = mod.active_output(st)
    z, (cx, cy) = out["zoom"], out["camera"]
    check("sol system zooms out to show the system", z < 0.5, "zoom %.3f" % z)
    check("sol system travelled from Neptune to the middle",
          (cx, cy) != tuple(before) and abs(cx) < 200 and abs(cy) < 200,
          "from %s to (%.0f, %.0f)" % (before, cx, cy))


# ── 9. the drag-catcher ───────────────────────────────────────────────────
def test_watch(mod):
    print("\n9. sol watch finishes a drag")
    watcher = subprocess.Popen([SOL, "watch"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True)
    try:
        time.sleep(1.5)
        ids = spawn(1)
        if not check("a terminal to drag", len(ids) == 1, ids):
            return
        wid = ids[0]
        # drop it squarely in Jupiter's neighbourhood, as a hand would
        j = mod.PLANETS[4]
        msg("move", "--id", str(wid), "--", str(j.x + 120), str(j.y + 90))
        time.sleep(3.0)
        st = state()
        check("the dropped window was claimed by Jupiter",
              wid in windows_of(st, 5, mod), windows_of(st, 5, mod))
    finally:
        watcher.terminate()
        try:
            _, err = watcher.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            watcher.kill()
            err = ""
        check("the watcher logged no shrugs", "failed:" not in err, err[:300])


# ── 10. the ☉ menu, by hand and by keyboard ───────────────────────────────
def menu_sandbox():
    """A copy of sol whose power commands only touch a file."""
    import re
    box = tempfile.mkdtemp(prefix="sol-menu-test-")
    src = open(SOL).read()
    for verb in ("lock", "sleep", "restart", "shutdown", "logout"):
        src, n = re.subn(r'"%s":\s*\[[^\]]*\]' % verb,
                         '"%s": ["touch", "%s/%s"]' % (verb, box, verb), src)
        if n != 1:
            raise AssertionError("could not stub POWER[%r] (%d matches)" % (verb, n))
    open(os.path.join(box, "sol"), "w").write(src)
    open(os.path.join(box, "sol-menu"), "w").write(open("/usr/local/bin/sol-menu").read())
    for f in ("sol", "sol-menu"):
        os.chmod(os.path.join(box, f), 0o755)
    open(os.path.join(box, "open.sh"), "w").write(
        "#!/bin/sh\nexec %s/sol-menu --system >%s/out 2>%s/err\n" % (box, box, box))
    os.chmod(os.path.join(box, "open.sh"), 0o755)
    return box


def menu_open(box, park=False):
    """Open the ☉ menu. `park` puts the pointer somewhere harmless first.

    Before, not after: highlight() answers to the arrow keys and to
    enter-notify alike, and a pointer that crosses or lands on a row as it
    moves selects that row. Park it while there is no menu to cross and the
    keyboard is the only thing touching the selection — which is the
    difference between a deterministic test and one that reports whichever
    row the last mouse test happened to leave the cursor over.
    """
    if park:
        run("sudo", HAND, "point", "1700", "1000")
        time.sleep(0.5)
    msg("action", "spawn", os.path.join(box, "open.sh"))
    time.sleep(2.5)
    return run("pgrep", "-f", "sol-men[u]").returncode == 0


def fired(box):
    return sorted(f for f in os.listdir(box)
                  if f in ("lock", "sleep", "restart", "shutdown", "logout"))


def forget(box):
    for f in fired(box):
        os.remove(os.path.join(box, f))


def test_menu(mod):
    print("\n10. the ☉ menu (power commands stubbed — nothing is taken down)")
    if os.geteuid() != 0 and not os.path.exists(HAND):
        check("sol-hand is installed", False, "no %s" % HAND)
        return
    box = menu_sandbox()
    err = lambda: open(os.path.join(box, "err")).read()      # noqa: E731

    # a) keyboard only. Rows: 0 Lock, 1 Sleep, 2 Restart…, 3 Shut down…,
    #    4 Log out… — so three downs land on Restart…, and enter must open
    #    its question rather than restart anything.
    check("the ☉ menu opens", menu_open(box, park=True), err()[:300])
    run("sudo", HAND, "key", "down", "down", "down", "enter")
    time.sleep(1.3)
    check("no ValueError from the row highlight (the keyboard regression)",
          "ValueError" not in err(), err()[:300])
    check("three downs and enter reach the question, firing nothing",
          not fired(box) and run("pgrep", "-f", "sol-men[u]").returncode == 0,
          "fired %s; menu %s" % (fired(box) or "nothing",
                                 "open" if run("pgrep", "-f", "sol-men[u]").returncode == 0
                                 else "gone"))

    # the question has two rows: 0 Restart, 1 Cancel
    run("sudo", HAND, "key", "down", "enter")
    time.sleep(1.5)
    check("the keyboard alone drives Restart… through to firing",
          fired(box) == ["restart"], "fired %s" % (fired(box) or "nothing"))
    run("pkill", "-f", "sol-men[u]")
    time.sleep(0.5)

    # b) esc leaves without doing anything
    forget(box)
    if menu_open(box, park=True):
        run("sudo", HAND, "key", "esc")
        time.sleep(1.2)
        check("esc closes the menu and fires nothing",
              run("pgrep", "-f", "sol-men[u]").returncode != 0 and not fired(box),
              "fired %s" % (fired(box) or "nothing"))
    run("pkill", "-f", "sol-men[u]")
    time.sleep(0.5)

    # c) a plain row fires on a single click
    forget(box)
    if menu_open(box, park=True):
        run("sudo", HAND, "click", "left", "100", "91")      # "Lock screen"
        time.sleep(1.3)
        check("a plain row fires on a single click",
              fired(box) == ["lock"], "fired %s; %s"
              % (fired(box) or "nothing", err()[:200]))
    run("pkill", "-f", "sol-men[u]")
    time.sleep(0.5)

    # d) an ellipsis row must ask first — nothing below that line happens on
    #    a single misclick
    forget(box)
    if menu_open(box, park=True):
        run("sudo", HAND, "click", "left", "100", "158")     # "Restart…"
        time.sleep(1.3)
        check("an ellipsis row asks before it acts", not fired(box),
              "fired %s" % (fired(box) or "nothing"))
        check("the menu is still open, showing the question",
              run("pgrep", "-f", "sol-men[u]").returncode == 0)
        # and the question's own Cancel really cancels
        run("sudo", HAND, "click", "left", "100", "119")     # "Cancel"
        time.sleep(1.2)
        check("Cancel closes the question without acting",
              not fired(box) and run("pgrep", "-f", "sol-men[u]").returncode != 0,
              "fired %s" % (fired(box) or "nothing"))
    run("pkill", "-f", "sol-men[u]")


# ── 11. doctor tells the truth from both sides ────────────────────────────
def test_doctor(mod):
    print("\n11. sol doctor")
    r = sol("doctor")
    out = r.stdout
    check("doctor exits 0 in a healthy session", r.returncode == 0, out[-400:])
    check("doctor sees driftwm", "driftwm is up" in out)
    check("doctor sees the config", "config installed" in out)
    check("doctor reports the power verdict",
          "restart" in out.lower(), out[-400:])
    check("doctor knows the machine boots into sol", "boots into sol" in out,
          out[-300:])


def main():
    want = sys.argv[1:]
    mod = load_sol()
    tests = [
        ("commands", test_command_surface), ("json", test_json_lines),
        ("errors", test_error_paths), ("corrupt", test_corrupt_state_files),
        ("districts", test_districts), ("arrange", test_arrange),
        ("cards", test_cards), ("flight", test_flight),
        ("watch", test_watch), ("menu", test_menu), ("doctor", test_doctor),
    ]
    print("%ssol acceptance — %d groups, live canvas%s"
          % (DIM, len(tests), OFF))
    try:
        for name, fn in tests:
            if want and not any(w in name for w in want):
                continue
            try:
                fn(mod)
            except Exception:
                import traceback
                check("%s group completed" % name, False,
                      traceback.format_exc()[-600:])
    finally:
        cleanup()

    bad = [n for n, ok in results if not ok]
    print("\n%s%d passed, %d failed%s"
          % (RED if bad else GREEN, len(results) - len(bad), len(bad), OFF))
    for n in bad:
        print("  %sfailed:%s %s" % (RED, OFF, n))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
