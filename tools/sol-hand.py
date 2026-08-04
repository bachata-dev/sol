#!/usr/bin/env python3
"""sol-hand — an emulated hand, for exercising sol's mouse and trackpad story.

There is no way to test a four-finger swipe over SSH, and no way to know the
drag-catcher survives a real hand — one that decelerates into the drop — when
every test so far moved windows by IPC teleport. So this creates the hand:
two virtual devices through /dev/uinput, real enough that udev classifies
them and libinput runs its actual gesture engine over them. driftwm cannot
tell the difference, which is the point.

    sudo tools/sol-hand.py point 960 540            # put the cursor somewhere
    sudo tools/sol-hand.py click right 300 800      # a button, optionally aimed
    sudo tools/sol-hand.py drag 400 300 900 700     # press, travel, release
    sudo tools/sol-hand.py wheel -3                 # scroll notches
    sudo tools/sol-hand.py swipe 4 left             # four fingers, travelling
    sudo tools/sol-hand.py pinch out 4              # spreading / gathering
    sudo tools/sol-hand.py hold 4                   # resting, then lifting
    sudo tools/sol-hand.py key down down enter      # keys, for driving a menu
    sudo tools/sol-hand.py script                   # the same verbs, one per line
    sudo tools/sol-hand.py probe 30                 # create both, hold, report

The mouse is absolute — position maps straight onto the output — so a test
can say "click at (300, 800)" and mean it. The touchpad is a 100x66mm
protocol-B multitouch device with per-axis resolution, because libinput's
gesture engine measures fingers in millimetres and ignores devices that
will not say how big they are.

Root, because /dev/uinput is. The devices exist only while this runs.
"""

import math
import os
import struct
import sys
import time
from fcntl import ioctl

# ── evdev vocabulary ──────────────────────────────────────────────────────
EV_SYN, EV_KEY, EV_REL, EV_ABS = 0x00, 0x01, 0x02, 0x03
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
BTN_TOUCH = 0x14A
TOOL = {1: 0x145, 2: 0x14D, 3: 0x14E, 4: 0x14F, 5: 0x148}   # BTN_TOOL_*TAP
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL = 0x00, 0x01, 0x06, 0x08
ABS_X, ABS_Y = 0x00, 0x01
MT_SLOT, MT_X, MT_Y, MT_ID = 0x2F, 0x35, 0x36, 0x39
PROP_POINTER, PROP_BUTTONPAD = 0x00, 0x02
KEY_LEFTALT = 56


# ── uinput ioctls, derived rather than hardcoded ──────────────────────────
def _IOW(nr, size):
    return (1 << 30) | (size << 16) | (ord("U") << 8) | nr


UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
UI_DEV_SETUP = _IOW(3, 92)     # struct uinput_setup
UI_ABS_SETUP = _IOW(4, 28)     # struct uinput_abs_setup
UI_SET_EVBIT = _IOW(100, 4)
UI_SET_KEYBIT = _IOW(101, 4)
UI_SET_RELBIT = _IOW(102, 4)
UI_SET_ABSBIT = _IOW(103, 4)
UI_SET_PROPBIT = _IOW(110, 4)

SCREEN_W, SCREEN_H = 1920, 1080     # driftwm's logical output
PAD_W, PAD_H, PAD_RES = 1200, 800, 12   # 100 x 66 mm at 12 units/mm
RATE = 90                            # frames per second, same as glide()


class Hand:
    """One virtual input device: bits declared, then created, then written."""

    def __init__(self, name, keys=(), rels=(), props=(), abses=()):
        self.f = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        if keys:
            ioctl(self.f, UI_SET_EVBIT, EV_KEY)
            for k in keys:
                ioctl(self.f, UI_SET_KEYBIT, k)
        if rels:
            ioctl(self.f, UI_SET_EVBIT, EV_REL)
            for r in rels:
                ioctl(self.f, UI_SET_RELBIT, r)
        if abses:
            ioctl(self.f, UI_SET_EVBIT, EV_ABS)
            for code, lo, hi, res in abses:
                ioctl(self.f, UI_SET_ABSBIT, code)
                ioctl(self.f, UI_ABS_SETUP,
                      struct.pack("<H2x6i", code, 0, lo, hi, 0, 0, res))
        for p in props:
            ioctl(self.f, UI_SET_PROPBIT, p)
        ioctl(self.f, UI_DEV_SETUP,
              struct.pack("<HHHH80sI", 0x03, 0x501, 0x501, 1,
                          name.encode(), 0))
        ioctl(self.f, UI_DEV_CREATE)
        time.sleep(0.7)          # udev and the compositor notice the hotplug

    def emit(self, etype, code, value):
        os.write(self.f, struct.pack("<qqHHi", 0, 0, etype, code, value))

    def syn(self):
        self.emit(EV_SYN, 0, 0)

    def close(self):
        time.sleep(0.25)         # let the last events land before vanishing
        ioctl(self.f, UI_DEV_DESTROY)
        os.close(self.f)


def mouse():
    return Hand("sol hand (mouse)",
                keys=(BTN_LEFT, BTN_RIGHT, BTN_MIDDLE),
                rels=(REL_WHEEL, REL_HWHEEL),
                abses=((ABS_X, 0, SCREEN_W - 1, 0),
                       (ABS_Y, 0, SCREEN_H - 1, 0)))


def rel_mouse():
    """A relative mouse, for drags.

    driftwm's grabs are not all alike: pan-viewport follows the pointer's
    absolute location, but move-window accumulates relative deltas — feed it
    an absolute stream and the grab holds a window that never moves. So the
    hand aims with the absolute mouse, then drags with this one. libinput's
    pointer acceleration applies to the deltas, which makes long relative
    drags land approximately; tests should aim for regions, not pixels.
    """
    return Hand("sol hand (mouse rel)",
                keys=(BTN_LEFT, BTN_RIGHT, BTN_MIDDLE),
                rels=(REL_X, REL_Y))


def keyboard():
    """A keyboard, so the hand can hold alt while the mouse drags.

    driftwm does not move windows by their title bars — moving is the
    alt+left mouse binding — so a drag test needs an alt key from somewhere.
    The whole main block is declared, not just alt: udev decides whether a
    device is a keyboard by which keys it carries, and a device that can
    press only KEY_LEFTALT is not enough of a keyboard to count. Its alt
    then never reaches the seat, and the grab never starts.

    Through 127 rather than 89, because the arrow keys live at 103-108 and a
    key a device never declared is dropped by the kernel, not by anything
    you can see: esc and enter arrived, the arrows silently did not, and the
    menu looked broken when it was the hand that could not reach the keys.
    """
    return Hand("sol hand (keyboard)", keys=tuple(range(1, 128)))


def touchpad():
    span = ((MT_SLOT, 0, 4, 0), (MT_ID, 0, 65535, 0),
            (MT_X, 0, PAD_W - 1, PAD_RES), (MT_Y, 0, PAD_H - 1, PAD_RES),
            (ABS_X, 0, PAD_W - 1, PAD_RES), (ABS_Y, 0, PAD_H - 1, PAD_RES))
    return Hand("sol hand (touchpad)",
                keys=(BTN_TOUCH, BTN_LEFT) + tuple(TOOL.values()),
                props=(PROP_POINTER, PROP_BUTTONPAD),
                abses=span)


# ── the mouse's verbs ─────────────────────────────────────────────────────
def point(d, x, y):
    d.emit(EV_ABS, ABS_X, int(x))
    d.emit(EV_ABS, ABS_Y, int(y))
    d.syn()


def click(d, btn, x=None, y=None):
    if x is not None:
        point(d, x, y)
        time.sleep(0.05)
    code = {"left": BTN_LEFT, "right": BTN_RIGHT, "middle": BTN_MIDDLE}[btn]
    d.emit(EV_KEY, code, 1)
    d.syn()
    time.sleep(0.06)
    d.emit(EV_KEY, code, 0)
    d.syn()


def wheel(d, notches):
    step = 1 if notches > 0 else -1
    for _ in range(abs(int(notches))):
        d.emit(EV_REL, REL_WHEEL, step)
        d.syn()
        time.sleep(0.05)


# ── the keyboard's verbs ──────────────────────────────────────────────────
# Enough of a keyboard to drive a menu. The hand could always hold alt for a
# drag; it could not press esc, which is the only way to find out whether a
# surface that asks for the keyboard is actually given it.
KEYS = {"esc": 1, "escape": 1, "tab": 15, "enter": 28, "return": 28,
        "space": 57, "up": 103, "down": 108, "left": 105, "right": 106,
        "j": 36, "k": 37, "q": 16, "n": 49, "p": 25,
        "0": 11, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8,
        "8": 9, "9": 10}


def key(d, *names):
    for name in names:
        code = KEYS.get(str(name).lower())
        if code is None:
            raise SystemExit("sol-hand key: unknown key %r (have: %s)"
                             % (name, " ".join(sorted(KEYS))))
        d.emit(EV_KEY, code, 1)
        d.syn()
        time.sleep(0.04)
        d.emit(EV_KEY, code, 0)
        d.syn()
        time.sleep(0.08)


def drag(d, x0, y0, x1, y1, ms=700, kbd=None, rel=None):
    """Press, travel, release — with a human's deceleration into the drop.

    The ease-out tail is the point of this function: the drag-catcher decides
    a drag has ended by 200ms of stillness, and an IPC teleport never tested
    whether a hand slowing to a stop reads as still or as many tiny drags.

    With `rel`, the button and the travel go through the relative mouse —
    which is what a window-move grab requires — while `d` only aims the
    pointer at the start point first.
    """
    point(d, x0, y0)
    time.sleep(0.15)
    if kbd:
        kbd.emit(EV_KEY, KEY_LEFTALT, 1)
        kbd.syn()
        time.sleep(0.08)
    mover = rel or d
    mover.emit(EV_KEY, BTN_LEFT, 1)
    mover.syn()
    time.sleep(0.15)
    steps = max(2, int(ms / 1000.0 * RATE))
    start = time.perf_counter()
    ex = ey = 0.0                # what the eased path owes us so far
    px, py = x0, y0
    for i in range(1, steps + 1):
        t = i / steps
        e = 0.5 - 0.5 * math.cos(math.pi * t)
        nx, ny = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
        if rel:
            ex += nx - px
            ey += ny - py
            dx, dy = int(ex), int(ey)
            if dx or dy:
                if dx:
                    rel.emit(EV_REL, REL_X, dx)
                if dy:
                    rel.emit(EV_REL, REL_Y, dy)
                rel.syn()
                ex -= dx
                ey -= dy
        else:
            point(d, nx, ny)
        px, py = nx, ny
        ahead = (start + t * ms / 1000.0) - time.perf_counter()
        if ahead > 0:
            time.sleep(ahead)
    time.sleep(0.12)
    mover.emit(EV_KEY, BTN_LEFT, 0)
    mover.syn()
    if kbd:
        time.sleep(0.08)
        kbd.emit(EV_KEY, KEY_LEFTALT, 0)
        kbd.syn()


# ── the touchpad's verbs ──────────────────────────────────────────────────
def fingers_down(d, pts):
    for i, (x, y) in enumerate(pts):
        d.emit(EV_ABS, MT_SLOT, i)
        d.emit(EV_ABS, MT_ID, 100 + i)
        d.emit(EV_ABS, MT_X, int(x))
        d.emit(EV_ABS, MT_Y, int(y))
    d.emit(EV_KEY, BTN_TOUCH, 1)
    d.emit(EV_KEY, TOOL[len(pts)], 1)
    d.emit(EV_ABS, ABS_X, int(pts[0][0]))
    d.emit(EV_ABS, ABS_Y, int(pts[0][1]))
    d.syn()


def fingers_move(d, pts):
    for i, (x, y) in enumerate(pts):
        d.emit(EV_ABS, MT_SLOT, i)
        d.emit(EV_ABS, MT_X, int(x))
        d.emit(EV_ABS, MT_Y, int(y))
    d.emit(EV_ABS, ABS_X, int(pts[0][0]))
    d.emit(EV_ABS, ABS_Y, int(pts[0][1]))
    d.syn()


def fingers_up(d, n):
    for i in range(n):
        d.emit(EV_ABS, MT_SLOT, i)
        d.emit(EV_ABS, MT_ID, -1)
    d.emit(EV_KEY, BTN_TOUCH, 0)
    d.emit(EV_KEY, TOOL[n], 0)
    d.syn()


def glide_fingers(d, frm, to, ms):
    steps = max(2, int(ms / 1000.0 * RATE))
    start = time.perf_counter()
    for i in range(1, steps + 1):
        t = i / steps
        fingers_move(d, [(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                         for a, b in zip(frm, to)])
        ahead = (start + t * ms / 1000.0) - time.perf_counter()
        if ahead > 0:
            time.sleep(ahead)


def swipe(d, n, direction, mm=45, ms=180):
    """N fingers in a row, travelling together. Directions are physical."""
    dx, dy = {"left": (-1, 0), "right": (1, 0),
              "up": (0, -1), "down": (0, 1)}[direction]
    travel = mm * PAD_RES
    cx, cy = PAD_W / 2 - dx * travel / 2, PAD_H / 2 - dy * travel / 2
    frm = [(cx + (i - (n - 1) / 2.0) * 130, cy) for i in range(n)]
    to = [(x + dx * travel, y + dy * travel) for x, y in frm]
    fingers_down(d, frm)
    time.sleep(0.03)
    glide_fingers(d, frm, to, ms)
    time.sleep(0.03)
    fingers_up(d, n)


def pinch(d, way, n=4, ms=260):
    """N fingers on a circle, spreading out or gathering in.

    The angles are ordered in opposing pairs — 45° then 225°, 135° then
    315° — not walked around the circle. libinput decides swipe-versus-pinch
    by comparing the directions of finger motion, and four fingers marching
    around a circle move at 90° to their neighbours: neither together nor
    opposed, so it never decides anything and no gesture is emitted at all.
    A real pinch is a thumb opposing fingers, and this is the synthetic
    version of that fact.
    """
    r0, r1 = (110, 265) if way == "out" else (265, 110)
    cx, cy = PAD_W / 2, PAD_H / 2
    angles = []
    for k in range((n + 1) // 2):
        a = math.pi / 4 + k * math.pi / max(1, (n + 1) // 2)
        angles += [a, a + math.pi]
    angles = angles[:n]

    def ring(r):
        return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles]

    frm, to = ring(r0), ring(r1)
    fingers_down(d, frm)
    time.sleep(0.12)             # a beat of stillness, like a hand settling
    glide_fingers(d, frm, to, ms)
    time.sleep(0.03)
    fingers_up(d, n)


def hold(d, n=4, ms=600):
    pts = [(PAD_W / 2 + (i - (n - 1) / 2.0) * 130, PAD_H / 2) for i in range(n)]
    fingers_down(d, pts)
    time.sleep(ms / 1000.0)
    fingers_up(d, n)


# ── entry ─────────────────────────────────────────────────────────────────
MOUSE_VERBS = {"point", "click", "drag", "wheel"}
PAD_VERBS = {"swipe", "pinch", "hold"}
KEY_VERBS = {"key"}


def run(dev, verb, a):
    if verb == "point":
        point(dev, float(a[0]), float(a[1]))
    elif verb == "click":
        click(dev, a[0], *(float(v) for v in a[1:3]))
    elif verb == "drag":
        opts = a[4:]
        kbd = keyboard() if "--alt" in opts else None
        rel = rel_mouse() if "--rel" in opts else None
        ms = int(opts[opts.index("--ms") + 1]) if "--ms" in opts else 700
        drag(dev, *(float(v) for v in a[:4]), ms=ms, kbd=kbd, rel=rel)
        for extra in (kbd, rel):
            if extra:
                extra.close()
    elif verb == "wheel":
        wheel(dev, int(a[0]))
    elif verb == "swipe":
        swipe(dev, int(a[0]), a[1])
    elif verb == "pinch":
        pinch(dev, a[0], int(a[1]) if len(a) > 1 else 4)
    elif verb == "hold":
        hold(dev, int(a[0]) if a else 4)
    elif verb == "key":
        key(dev, *a)


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    verb = args[0]

    if verb == "probe":
        m, p = mouse(), touchpad()
        names = {}
        for ev in sorted(os.listdir("/sys/class/input")):
            if ev.startswith("event"):
                try:
                    with open("/sys/class/input/%s/device/name" % ev) as f:
                        names[ev] = f.read().strip()
                except OSError:
                    pass
        for ev, name in names.items():
            if name.startswith("sol hand"):
                print("%s  %s" % (ev, name))
        time.sleep(float(args[1]) if len(args) > 1 else 30)
        p.close()
        m.close()
        return

    if verb == "script":
        m = p = r = k = None
        for line in sys.stdin:
            words = line.split()
            if not words or words[0].startswith("#"):
                continue
            if words[0] == "quit":
                print("ok quit", flush=True)
                break
            if words[0] == "sleep":
                time.sleep(float(words[1]))
            elif words[0] in MOUSE_VERBS:
                m = m or mouse()
                run(m, words[0], words[1:])
            elif words[0] in PAD_VERBS:
                p = p or touchpad()
                run(p, words[0], words[1:])
            elif words[0] in KEY_VERBS:
                k = k or keyboard()
                run(k, words[0], words[1:])
            elif words[0] in ("altdown", "altup"):
                k = k or keyboard()
                k.emit(EV_KEY, KEY_LEFTALT, 1 if words[0] == "altdown" else 0)
                k.syn()
            elif words[0] in ("rpress", "rrelease"):
                r = r or rel_mouse()
                r.emit(EV_KEY, BTN_LEFT, 1 if words[0] == "rpress" else 0)
                r.syn()
            elif words[0] == "rmove":
                r = r or rel_mouse()
                dx, dy = int(words[1]), int(words[2])
                if dx:
                    r.emit(EV_REL, REL_X, dx)
                if dy:
                    r.emit(EV_REL, REL_Y, dy)
                r.syn()
            print("ok %s" % " ".join(words), flush=True)
        for dev in (m, p, r, k):
            if dev:
                dev.close()
        return

    if verb in MOUSE_VERBS:
        dev = mouse()
    elif verb in PAD_VERBS:
        dev = touchpad()
    elif verb in KEY_VERBS:
        dev = keyboard()
    else:
        sys.exit("sol-hand: unknown verb '%s'" % verb)
    run(dev, verb, args[1:])
    dev.close()


if __name__ == "__main__":
    main()
