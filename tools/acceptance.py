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


def camera(mod):
    d = mod.Drift()
    return tuple(mod.active_output(d.state())["camera"])


def near(a, b, slack=2.0):
    """Cameras are floats with easing behind them; -471 comes back as
    -470.9999999999998 and that is arrival, not failure."""
    return abs(a[0] - b[0]) <= slack and abs(a[1] - b[1]) <= slack


def test_new_verbs(mod):
    print("\n12. back, find, tidy, homes")
    sol("goto", "3")
    time.sleep(2.2)
    at_earth = camera(mod)
    sol("goto", "8")
    time.sleep(2.2)
    at_neptune = camera(mod)
    check("goto moved the camera", not near(at_earth, at_neptune))

    r = sol("back")
    time.sleep(2.2)
    check("sol back exits 0", r.returncode == 0, r.stderr[:150])
    check("back returns to where the flight started",
          near(camera(mod), at_earth), "%s vs %s" % (camera(mod), at_earth))
    sol("back")
    time.sleep(2.2)
    check("back is a toggle — twice returns you",
          near(camera(mod), at_neptune), "%s vs %s" % (camera(mod), at_neptune))

    # find, by word, with no menu involved. Its own app_id, because two
    # windows sharing one is a legal canvas and "the" one would be a coin toss.
    sol("goto", "3")
    time.sleep(2.2)
    script = os.path.join(tempfile.mkdtemp(), "findme.sh")
    open(script, "w").write("#!/bin/sh\nexec foot -a acceptance-findme "
                            "-e sh -c 'while :; do sleep 1; done'\n")
    os.chmod(script, 0o755)
    msg("action", "spawn", script)
    time.sleep(3)
    target = next((w for w in state()["windows"]
                   if w.get("app_id") == "acceptance-findme"), None)
    if check("a window to find", target is not None):
        _spawned.append(target["id"])
        r = sol("find", "acceptance-findme")
        time.sleep(2.5)
        check("sol find exits 0", r.returncode == 0, r.stderr[:150])
        found = next((w for w in state()["windows"]
                      if w["id"] == target["id"]), {})
        check("find focused the window it was asked for",
              found.get("is_focused") is True)
        check("find flew to it",
              near(camera(mod), tuple(found.get("position") or (0, 0)), slack=900),
              "%s vs %s" % (camera(mod), tuple(found.get("position") or ())))
    r = sol("find", "no-such-window-anywhere")
    check("find refuses a word that matches nothing", r.returncode != 0)

    # tidy: one verb for the whole canvas
    ids = spawn(2)
    if ids:
        msg("move", "--id", str(ids[0]), "--", "70000", "70000")
        time.sleep(2.0)
        check("a window flung into deep space is adrift",
              len(mod.adrift(state())) >= 1)
        r = sol("tidy", timeout=90)
        time.sleep(6)
        check("sol tidy exits 0", r.returncode == 0, r.stderr[:150])
        check("nothing is adrift after tidy", not mod.adrift(state()),
              [w["id"] for w in mod.adrift(state())])

    r = sol("homes")
    check("sol homes exits 0", r.returncode == 0, r.stderr[:150])
    check("homes explains itself when none are set",
          "sol.toml" in r.stdout or "Jupiter" in r.stdout, r.stdout[:150])


def test_homes_routing(mod):
    """The one that needs the watcher restarted, so it stands on its own."""
    print("\n13. an app going home (restarts the watcher)")
    conf = os.path.expanduser("~/.config/driftwm/sol.toml")
    saved = open(conf).read() if os.path.exists(conf) else None
    watcher = None
    try:
        open(conf, "w").write("[homes]\nacceptance-home = 5\n")
        run("pkill", "-f", "sol watc[h]")
        time.sleep(0.6)
        watcher = subprocess.Popen([SOL, "watch"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True)
        time.sleep(2.5)
        sol("goto", "3")
        time.sleep(2.2)
        before = camera(mod)

        script = os.path.join(tempfile.mkdtemp(), "born.sh")
        open(script, "w").write("#!/bin/sh\nexec foot -a acceptance-home "
                                "-e sh -c 'while :; do sleep 1; done'\n")
        os.chmod(script, 0o755)
        msg("action", "spawn", script)
        time.sleep(6)

        st = state()
        w = next((x for x in st["windows"]
                  if x.get("app_id") == "acceptance-home"), None)
        if check("the window opened", w is not None):
            j = mod.PLANETS[4]
            away = ((w["position"][0] - j.x) ** 2
                    + (w["position"][1] - j.y) ** 2) ** 0.5
            check("it travelled to the planet it calls home (%.0f from Jupiter)"
                  % away, away <= mod.DISTRICT, tuple(w["position"]))
            check("and the camera did not follow it",
                  near(camera(mod), before), "%s vs %s" % (camera(mod), before))
            _spawned.append(w["id"])
    finally:
        if saved is None:
            os.path.exists(conf) and os.remove(conf)
        else:
            open(conf, "w").write(saved)
        if watcher:
            watcher.terminate()
            try:
                watcher.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watcher.kill()
        # hand the session's own watcher back
        subprocess.run(["driftwm", "msg", "action", "spawn", "/tmp/startwatch.sh"],
                       capture_output=True)
        time.sleep(1.5)


def main():
    want = sys.argv[1:]
    mod = load_sol()
    tests = [
        ("commands", test_command_surface), ("json", test_json_lines),
        ("errors", test_error_paths), ("corrupt", test_corrupt_state_files),
        ("districts", test_districts), ("arrange", test_arrange),
        ("cards", test_cards), ("flight", test_flight),
        ("watch", test_watch), ("menu", test_menu), ("doctor", test_doctor),
        ("verbs", test_new_verbs), ("homes", test_homes_routing),
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
