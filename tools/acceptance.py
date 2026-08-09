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
import shutil
import subprocess
import sys
import tempfile
import time

def _which(name, *extra):
    """Where a sol command actually is, in whichever layout is installed.

    /usr under a package and /usr/local from install.sh, and the suite has to
    drive whichever one this machine has — hardcoding /usr/local meant the
    menu group tore itself down the first time it met a .deb.
    """
    for path in extra + ("/usr/bin/" + name, "/usr/local/bin/" + name):
        if os.path.exists(path):
            return path
    return shutil.which(name) or "/usr/bin/" + name


SOL = _which("sol")
HAND = _which("sol-hand", "/usr/share/sol/tools/sol-hand.py")
MENU = _which("sol-menu")
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


MODULES = ("/usr/lib/sol/solmod.py", "/usr/local/lib/sol/solmod.py")
MODULE = next((m for m in MODULES if os.path.exists(m)), MODULES[-1])


def load_sol():
    """The installed sol, as a module, for the parts worth testing directly.

    `sol` on the path is a stub in front of this, so that Python caches the
    compiled form instead of re-parsing 190KB on every keypress. The tests
    want the code, not the doorway — but they fall back to the doorway, so
    that a tree installed the old way still runs them.
    """
    where = MODULE if os.path.exists(MODULE) else SOL
    loader = importlib.machinery.SourceFileLoader("sol_mod", where)
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
    # `next` and `prev` refuse when the planet you are standing on is holding
    # nothing, which is correct and is not what this group is asking about.
    # So it stands somewhere with a window in it first, and the exit code
    # stays a claim about the command rather than about the canvas.
    sol("goto", "3")
    time.sleep(1.5)
    stock(3, 1, mod)
    for args in (["here"], ["here", "--waybar"], ["list"], ["system"],
                 ["goto", "3"], ["goto", "earth"], ["goto", "home"],
                 ["hop", "out"], ["hop", "in"], ["arrange"], ["gather"],
                 ["sweep"], ["plate", "3"], ["bar", "where"],
                 ["bar", "holding"], ["bar", "strip"], ["bar", "last"],
                 ["next"], ["prev"], ["help"], ["doctor"],
                 ["mode"], ["mode", "off"],
                 ["night", "off"], ["dark", "off"], ["pick", "right"]):
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
    # The code, not the stub in front of it: `sol` on the path imports the
    # module so Python can cache its bytecode, and the POWER table being
    # rewritten here lives in the module. The copy keeps its shebang and its
    # __main__ guard, so it still runs directly as this sandbox needs.
    src = open(MODULE if os.path.exists(MODULE) else SOL).read()
    for verb in ("lock", "sleep", "restart", "shutdown", "logout"):
        src, n = re.subn(r'"%s":\s*\[[^\]]*\]' % verb,
                         '"%s": ["touch", "%s/%s"]' % (verb, box, verb), src)
        if n != 1:
            raise AssertionError("could not stub POWER[%r] (%d matches)" % (verb, n))
    open(os.path.join(box, "sol"), "w").write(src)
    open(os.path.join(box, "sol-menu"), "w").write(open(MENU).read())
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


def test_menu_wiring(mod):
    """The installed sol-menu can find the installed sol.

    The group below builds a sandbox copy of both and drives that, which is
    right for testing behaviour and blind to how the real pair are wired
    together — it passed while right-click on the live desktop printed the
    keybinding card and opened nothing, because `sol` on the path became a
    stub in front of the module and sol-menu was still loading the stub.
    So this asks the installed files, in place, the way the mouse does.
    """
    print("\n10a. the installed menu is wired to the installed sol")
    r = run("python3", "-c",
            "import importlib.machinery as m, importlib.util as u, sys;"
            "l = m.SourceFileLoader('probe', %r);" % MENU +
            "spec = u.spec_from_loader('probe', l);"
            "mod = u.module_from_spec(spec);"
            "sys.argv = ['probe', '--print-rows'];"
            "l.exec_module(mod);"
            "print('ROWS', len(mod.sol.menu_items(mod.sol.PLANETS[2], 3, True)))",
            timeout=25)
    out = r.stdout + r.stderr
    check("sol-menu loads a sol that still has its places in it",
          "ROWS" in out and "S O L" not in out,
          out.strip()[:200] or "no output")

    # And the doorway itself: importing it must not run a command.
    r = run("python3", "-c",
            "import importlib.machinery as m, importlib.util as u;"
            "l = m.SourceFileLoader('stub', %r);" % SOL +
            "mod = u.module_from_spec(u.spec_from_loader('stub', l));"
            "l.exec_module(mod); print('IMPORTED')", timeout=25)
    out = r.stdout + r.stderr
    check("importing the sol on the path runs nothing",
          "IMPORTED" in out and "S O L" not in out, out.strip()[:200])


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


# ── 14. the modes: geometry, before the canvas is involved ────────────────
def test_mode_geometry(mod):
    """The arithmetic a mode is made of, checked without a compositor.

    Everything here is a pure function of a screen size and a window count,
    and every one of them has a failure that is invisible on the machine it
    was written on: a split that overlaps only at seven windows, a column
    that is a maximise only on a laptop, a neighbour that wraps only in the
    bottom row. So they are checked across the screens sol will actually meet
    rather than against the one it is being run on.
    """
    print("\n14. what a mode computes")
    screens = [(1366, 768), (1600, 900), (1920, 1080), (2560, 1440), (3840, 2160)]
    bad_fill, bad_bounds, bad_overlap, bad_floor = [], [], [], []
    for sw, sh in screens:
        uw = sw - 2 * mod.FOCUS_EDGE
        uh = sh - 2 * mod.CHROME - 2 * mod.FOCUS_EDGE
        for n in range(1, 13):
            cells = mod.panes(n, uw, uh)
            if len(cells) != n:
                bad_fill.append((sw, n, len(cells)))
                continue
            for cx, cy, cw, ch in cells:
                if (cx - cw / 2 < -uw / 2 - 1 or cx + cw / 2 > uw / 2 + 1
                        or cy - ch / 2 < -uh / 2 - 1 or cy + ch / 2 > uh / 2 + 1):
                    bad_bounds.append((sw, sh, n))
            for i in range(len(cells)):
                for j in range(i + 1, len(cells)):
                    ax, ay, aw, ah = cells[i]
                    bx, by, bw, bh = cells[j]
                    if (abs(ax - bx) * 2 < aw + bw - 1
                            and abs(ay - by) * 2 < ah + bh - 1):
                        bad_overlap.append((sw, sh, n, i, j))
        room = mod.fits(12, uw, uh)
        smallest = min((cw, ch) for _, _, cw, ch in mod.panes(room, uw, uh))
        if room > 1 and (smallest[0] < mod.MIN_TILE[0]
                         or smallest[1] < mod.MIN_TILE[1]):
            bad_floor.append((sw, sh, room, smallest))
    check("panes hands back exactly the tiles asked for", not bad_fill, bad_fill)
    check("no tile leaves the usable area", not bad_bounds, bad_bounds[:4])
    check("no two tiles overlap, on any screen", not bad_overlap, bad_overlap[:4])
    check("fits never returns a tile under the floor", not bad_floor, bad_floor)

    # The block should be nearly all of the screen: what is left is the gaps,
    # and a split that wasted a fifth of a screen would still pass every
    # check above.
    uw, uh = 1920 - 2 * mod.FOCUS_EDGE, 1080 - 2 * mod.CHROME - 2 * mod.FOCUS_EDGE
    thin = [(n, round(sum(cw * ch for _, _, cw, ch in mod.panes(n, uw, uh))
                      / (uw * uh), 3)) for n in range(1, 13)]
    check("every split covers at least 94% of the block",
          all(f >= 0.94 for _, f in thin), thin)

    # Two windows side by side rather than stacked: the tie in the shape test
    # has to break towards columns, because text is taller than it is wide.
    two = mod.panes(2, uw, uh)
    check("two windows land side by side", two[0][1] == two[1][1], two)

    # A reading column stays a column on a small screen.
    wide = [(sw, round(min(mod.READ_COL, (sw - 2 * mod.FOCUS_EDGE) * mod.READ_MOST)
                       / (sw - 2 * mod.FOCUS_EDGE), 2)) for sw, _ in screens]
    check("solo is never more than READ_MOST of the screen",
          all(f <= mod.READ_MOST + 0.01 for _, f in wide), wide)

    # Directional picking across a 2x2: every arrow lands on the right tile,
    # and an edge stays put rather than wrapping to the far side.
    cells = mod.panes(4, uw, uh)
    grid = [{"id": i, "position": (cx, cy)} for i, (cx, cy, _, _) in enumerate(cells)]
    want = {(0, "right"): 1, (0, "down"): 2, (0, "left"): 0, (0, "up"): 0,
            (1, "left"): 0, (1, "down"): 3, (1, "right"): 1,
            (3, "up"): 1, (3, "left"): 2, (3, "down"): 3}
    wrong = [(i, way, mod.neighbour(grid[i], grid, way)["id"], expect)
             for (i, way), expect in want.items()
             if mod.neighbour(grid[i], grid, way)["id"] != expect]
    check("the arrows move one tile, and stop at the edge", not wrong, wrong)


# ── 15. the shader block and the corner survive being written ─────────────
def test_mode_paint(mod):
    print("\n15. the palette is written and read back")
    src = open(mod.SHADER).read()
    check("the shader has its mode markers",
          mod.MODE_HEAD in src and mod.MODE_TAIL in src)

    was_shade, was_night, was_dark = mod.read_paint()
    d = mod.Drift()
    try:
        mod.paint(d, night=0.25)
        _, n, k = mod.read_paint()
        check("night is written and read back", abs(n - 0.25) < 1e-6, n)
        mod.paint(d, shade=(0.1, 0.2, 0.3, 0.9))
        s, n, k = mod.read_paint()
        check("a mode's shade does not disturb the evening",
              abs(n - 0.25) < 1e-6 and abs(s[3] - 0.9) < 1e-6, (s, n))
        mod.paint(d, shade=(0.0, 0.0, 0.0, 0.0))
        _, n, _ = mod.read_paint()
        check("leaving a mode does not turn the evening off",
              abs(n - 0.25) < 1e-6, n)
    finally:
        mod.paint(d, shade=was_shade, night=was_night, dark=was_dark)

    # night and dark are two answers to one question: each turns the other off
    r = sol("night", "on")
    _, n, k = mod.read_paint()
    check("night on clears dark", r.returncode == 0 and n > 0 and k == 0, (n, k))
    sol("dark", "on")
    _, n, k = mod.read_paint()
    check("dark on clears night", k > 0 and n == 0, (n, k))
    sol("dark", "off")
    _, n, k = mod.read_paint()
    check("dark off leaves both at rest", n == 0 and k == 0, (n, k))

    # The corner radius is somebody else's config file: only the
    # [decorations] key may move, and it must round-trip exactly.
    before = open(mod.CONFIG).read()
    rest = mod.read_corner()
    check("the resting corner radius is readable", isinstance(rest, int), rest)
    mod.write_corner(mod.MODE_CORNER)
    others = [ln for ln in open(mod.CONFIG).read().splitlines()
              if ln.startswith("corner_radius")]
    check("only one corner_radius line moved",
          others.count("corner_radius = %d" % mod.MODE_CORNER) == 1, others)
    mod.write_corner(rest)
    check("the config round-trips byte for byte",
          open(mod.CONFIG).read() == before)
    check("writing the same value again changes nothing",
          mod.write_corner(rest) is False)


# ── 16. focus, on the real canvas ─────────────────────────────────────────
def mode_tiles(mod, st=None):
    """The windows a mode has put on the screen, as screen-space rects."""
    st = state() if st is None else st
    out = mod.active_output(st)
    cx, cy = out["camera"]
    sw, sh = out["size"]
    rects = []
    for w in st.get("windows", []):
        if mod.is_furniture(w):
            continue
        x, y = w["position"]
        ww, wh = w["size"]
        l, r = x - ww / 2.0 - cx + sw / 2.0, x + ww / 2.0 - cx + sw / 2.0
        t, b = -(y + wh / 2.0) + cy + sh / 2.0, -(y - wh / 2.0) + cy + sh / 2.0
        if r > 0 and l < sw and b > 0 and t < sh:
            rects.append((w["id"], l, t, r, b))
    return rects, sw, sh


def test_focus_live(mod):
    print("\n16. focus fills the screen, and gives it back")
    sol("mode", "off")
    time.sleep(1.0)
    reset_canvas()
    time.sleep(1.2)
    sol("goto", "3")
    time.sleep(1.8)
    have = stock(3, 4, mod)
    sol("arrange", "3")
    time.sleep(2.0)

    st = state()
    before = {w["id"]: (tuple(w["position"]), tuple(w["size"]))
              for w in mod.assignment(st).get(3, [])}
    rest_corner = mod.read_corner()
    check("Earth is holding something to focus", len(before) >= 4, have)

    r = sol("focus")
    check("sol focus exits 0", r.returncode == 0, (r.stderr or r.stdout)[:200])
    time.sleep(3.0)

    check("the bar says which mode it is in", "focus" in sol("mode").stdout)
    check("the corner comes down while a mode is on",
          mod.read_corner() == mod.MODE_CORNER, mod.read_corner())
    _, _, shade_a = (lambda p: (p[1], p[2], p[0][3]))(mod.read_paint())
    check("the sky is shaded", shade_a > 0.5, shade_a)

    rects, sw, sh = mode_tiles(mod)
    check("every window on Earth is a tile", len(rects) >= 4, len(rects))
    off = [t for t in rects
           if t[1] < -1 or t[2] < mod.CHROME - 1
           or t[3] > sw + 1 or t[4] > sh - mod.CHROME + 1]
    check("no tile lands under the bar or off the screen", not off, off[:3])
    over = []
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            _, al, at, ar, ab = rects[i]
            _, bl, bt, br, bb = rects[j]
            if al < br - 1 and bl < ar - 1 and at < bb - 1 and bt < ab - 1:
                over.append((rects[i][0], rects[j][0]))
    check("no two tiles overlap on screen", not over, over)
    covered = sum((r - l) * (b - t) for _, l, t, r, b in rects)
    usable_area = sw * (sh - 2 * mod.CHROME)
    check("the tiles cover most of the usable screen",
          covered / usable_area >= 0.92, round(covered / usable_area, 3))

    # The camera is on the planet, not wherever a resize dragged it.
    check("the camera is parked on the planet",
          near(camera(mod), (mod.PLANETS[2].x, mod.PLANETS[2].y), slack=6.0),
          camera(mod))

    # ...and the arrows move focus without moving the camera.
    was = camera(mod)
    sol("pick", "right")
    time.sleep(0.8)
    check("picking a tile does not move the camera", near(camera(mod), was, 6.0))

    r = sol("mode", "off")
    check("sol mode off exits 0", r.returncode == 0, r.stderr[:150])
    time.sleep(3.5)
    st = state()
    after = {w["id"]: (tuple(w["position"]), tuple(w["size"]))
             for w in mod.real_windows(st)}
    wrong = [(wid, before[wid], after.get(wid))
             for wid in before
             if wid in after and after[wid][1] != before[wid][1]]
    check("every window is handed back the size it had", not wrong, wrong[:3])
    drifted = [(wid, before[wid][0], after[wid][0]) for wid in before
               if wid in after
               and (abs(after[wid][0][0] - before[wid][0][0]) > 3
                    or abs(after[wid][0][1] - before[wid][0][1]) > 3)]
    check("and the place it had", not drifted, drifted[:3])
    check("the corner radius comes back", mod.read_corner() == rest_corner,
          mod.read_corner())
    check("the shade is cleared", mod.read_paint()[0][3] == 0.0,
          mod.read_paint()[0])


# ── 17. a mode keeps up with the district under it ────────────────────────
def watcher_alive():
    """Is `sol watch` up? Re-laying a mode is its job, like catching drags."""
    out = run("ps", "-eo", "pid,cmd").stdout
    return any("sol watch" in ln and "grep" not in ln for ln in out.splitlines())


def ensure_watcher():
    """Start the watcher if nothing is watching.

    The homes group deliberately kills it and runs its own, and leaves the
    machine without one — which is fine for the groups that only drive the
    CLI and fatal for the ones about a mode following its district. Started
    rather than asserted, because a suite that fails for want of a daemon it
    could have started is a suite that teaches you nothing.
    """
    if watcher_alive():
        return
    subprocess.Popen([SOL, "watch"], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    time.sleep(2.5)


def stock(place_n, want, mod, tries=6):
    """Get `want` windows into a district, and be sure of it before going on.

    Spawning four and sleeping is a coin toss once the machine is busy: a
    window is announced before it has a size, `gather` only claims what has
    arrived, and a group that starts a window short fails on a check about
    geometry. So this asks the canvas rather than the clock.
    """
    for _ in range(tries):
        have = len(mod.assignment(state()).get(place_n, []))
        if have >= want:
            return have
        sol("goto", str(place_n))
        time.sleep(1.2)
        spawn(min(want - have, 3), settle=1.5)
        sol("gather", str(place_n))
        time.sleep(1.8)
    return len(mod.assignment(state()).get(place_n, []))


def reset_canvas():
    """Close every terminal the groups before this one left lying about.

    The mode groups measure a whole screen, so they cannot inherit forty
    windows from their predecessors: a district that deep tiles twelve and
    parks the remainder, and a window parked off-screen on purpose is
    indistinguishable from a layout that went wrong. Worse, forty overlapping
    windows around one planet give the compositor a collision to resolve on
    every resize, and it resolves them by moving the camera — which is a real
    fault to have found, and not the one these groups are looking for.
    """
    for w in state().get("windows", []):
        if w.get("app_id") == "foot":
            msg("close", "--id", str(w["id"]))
            time.sleep(0.06)
    # Wait for them to actually be gone. A client is closed when it says so,
    # not when it was asked, and a group that starts counting windows while
    # the last four are still dying counts four windows too many.
    for _ in range(20):
        if not any(w.get("app_id") == "foot" for w in state().get("windows", [])):
            break
        time.sleep(0.3)


def test_mode_follows(mod):
    print("\n17. closing a tile closes the gap")
    # Said first and plainly: a mode follows its district from inside the
    # watcher, so a watcher that is not running turns every check below into
    # a puzzle about geometry when the answer is that nobody was listening.
    ensure_watcher()
    if not check("the watcher is running to notice", watcher_alive(),
                 "re-laying a mode is its job, and it would not start"):
        return
    reset_canvas()
    sol("mode", "off")
    time.sleep(1.2)
    sol("goto", "3")
    time.sleep(1.8)
    stock(3, 3, mod)
    sol("arrange", "3")
    time.sleep(2.0)
    sol("focus")
    time.sleep(3.0)

    rects, sw, sh = mode_tiles(mod)
    was = len(rects)
    check("focus is holding several tiles", was >= 3, was)
    doomed = rects[0][0]
    msg("close", "--id", str(doomed))
    time.sleep(4.5)                   # the watcher has to notice and re-lay

    rects, sw, sh = mode_tiles(mod)
    check("the closed tile is gone", all(t[0] != doomed for t in rects),
          [t[0] for t in rects])
    check("one fewer tile is on the screen", len(rects) == was - 1, len(rects))
    covered = sum((r - l) * (b - t) for _, l, t, r, b in rects)
    usable_area = sw * (sh - 2 * mod.CHROME)
    check("the survivors close the gap",
          covered / usable_area >= 0.92, round(covered / usable_area, 3))

    ids = {t[0] for t in rects}
    before_open = len(rects)
    spawn(1)
    time.sleep(5.0)
    rects, _, _ = mode_tiles(mod)
    check("a window opening lands on the tiling",
          len(rects) == before_open + 1 and {t[0] for t in rects} > ids,
          [t[0] for t in rects])
    sol("mode", "off")
    time.sleep(3.0)


# ── 18. one mode at a time, and it belongs to its planet ──────────────────
def test_mode_exclusive(mod):
    print("\n18. one mode at a time")
    sol("mode", "off")
    time.sleep(1.0)
    reset_canvas()
    time.sleep(1.2)
    sol("goto", "3")
    time.sleep(1.8)
    stock(3, 2, mod)
    sol("focus")
    time.sleep(3.0)
    check("focus is on", "focus" in sol("mode").stdout)
    sol("solo")
    time.sleep(3.0)
    out = sol("mode").stdout
    check("entering solo left focus", "solo" in out and "focus" not in out, out)

    # A mode belongs to the place it was entered on.
    sol("goto", "8")
    time.sleep(3.0)
    check("flying to another planet ends the mode",
          "no mode" in sol("mode").stdout, sol("mode").stdout)
    check("the corner radius came back with it",
          mod.read_corner() != mod.MODE_CORNER, mod.read_corner())

    # And a mode refuses where it cannot mean anything.
    sol("system")
    time.sleep(2.2)
    r = sol("focus")
    check("focus refuses from the whole-system view", r.returncode != 0,
          (r.stdout + r.stderr)[:160])


def main():
    want = sys.argv[1:]
    mod = load_sol()
    tests = [
        ("commands", test_command_surface), ("json", test_json_lines),
        ("errors", test_error_paths), ("corrupt", test_corrupt_state_files),
        ("districts", test_districts), ("arrange", test_arrange),
        ("cards", test_cards), ("flight", test_flight),
        ("watch", test_watch), ("wiring", test_menu_wiring), ("menu", test_menu), ("doctor", test_doctor),
        ("verbs", test_new_verbs), ("homes", test_homes_routing),
        ("geometry", test_mode_geometry), ("paint", test_mode_paint),
        ("focus", test_focus_live), ("follows", test_mode_follows),
        ("exclusive", test_mode_exclusive),
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
