#!/usr/bin/env python3
import sys
import os
import json
import platform
import subprocess
import urllib.request
import urllib.error
import difflib
import threading
import time
import itertools
import random
import shutil

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))

# ── OS ────────────────────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print("\033[91mconfig.json not found next to main.py\033[0m")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

def get_os():
    s = platform.system().lower()
    if s == "darwin":  return "mac"
    if s == "windows": return "windows"
    return "linux"

IS_WIN = platform.system() == "Windows"

# ── Console init: enable ANSI + UTF-8 so gradients/glyphs work on Windows too ──

def _init_console():
    """Turn on true-colour ANSI + UTF-8 output. Returns (color_ok, unicode_ok)."""
    color, uni = True, True
    if IS_WIN:
        color = uni = False
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)                        # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if k.GetConsoleMode(h, ctypes.byref(mode)):
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                k.SetConsoleMode(h, mode.value | 0x0004)
                color = True
        except Exception:
            color = os.environ.get("TERM") == "xterm"
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            uni = True
        except Exception:
            uni = False
    return color, uni

USE_COLOR, USE_UNICODE = _init_console()

try:
    ANIMATE = USE_COLOR and sys.stdout.isatty()
except Exception:
    ANIMATE = False

def set_animation(on):
    """Let callers (e.g. a --no-anim flag) force animations off."""
    global ANIMATE
    ANIMATE = bool(on) and USE_COLOR

# ── Colors ────────────────────────────────────────────────────────────────────

def _c(t, code): return f"\033[{code}m{t}\033[0m" if USE_COLOR else t

def bold(t):    return _c(t, "1")
def dim(t):     return _c(t, "2")
def cyan(t):    return _c(t, "96")
def green(t):   return _c(t, "92")
def yellow(t):  return _c(t, "93")
def red(t):     return _c(t, "91")
def magenta(t): return _c(t, "95")
def blue(t):    return _c(t, "94")
def white(t):   return _c(t, "97")
def error(t):   return red(t)

def rgb(t, r, g, b):
    return f"\033[38;2;{r};{g};{b}m{t}\033[0m" if USE_COLOR else t

# ── Neon gradient palette ──────────────────────────────────────────────────────

NEON_A = (0, 255, 200)     # teal
NEON_B = (0, 170, 255)     # sky blue
NEON_C = (170, 90, 255)    # violet
NEON_D = (255, 70, 170)    # pink
FLOW   = (NEON_A, NEON_B, NEON_C, NEON_D)

# warm "Spidey" sweep — pops against the green rain
SPIDEY = ((255, 80, 80), (255, 150, 50), (255, 215, 90))

def _lerp(a, b, t):
    return (int(a[0] + (b[0]-a[0])*t),
            int(a[1] + (b[1]-a[1])*t),
            int(a[2] + (b[2]-a[2])*t))

def _stop_at(t, stops):
    if t <= 0: return stops[0]
    if t >= 1: return stops[-1]
    seg = t * (len(stops) - 1)
    i   = int(seg)
    return _lerp(stops[i], stops[i + 1], seg - i)

def gradient(text, stops=FLOW, shift=0.0):
    """Colour a PLAIN string with a horizontal multi-stop gradient.
    `shift` (0..1) rotates the gradient — animate it for a shimmer."""
    if not USE_COLOR or not text:
        return text
    chars = list(text)
    n     = max(1, len(chars) - 1)
    out   = []
    for i, ch in enumerate(chars):
        pos = (i / n + shift) % 1.0
        r, g, b = _stop_at(pos, stops)
        out.append(f"\033[38;2;{r};{g};{b}m{ch}")
    return "".join(out) + "\033[0m"

# ── Glyphs (ASCII fallback when the console can't render unicode) ──────────────

ARROW  = "❯" if USE_UNICODE else ">"
BULLET = "▸" if USE_UNICODE else "*"
CHECK  = "✔" if USE_UNICODE else "+"
CROSS  = "✘" if USE_UNICODE else "x"
DOT    = "·" if USE_UNICODE else "."
STAR   = "✦" if USE_UNICODE else "*"
SPARK  = "✧" if USE_UNICODE else "."

# ── Animation helpers (auto-skip when output isn't an interactive terminal) ────

def type_out(text, delay=0.006, end="\n"):
    if not ANIMATE:
        sys.stdout.write(text + end); sys.stdout.flush(); return
    for ch in text:
        sys.stdout.write(ch); sys.stdout.flush()
        if ch not in " \t":
            time.sleep(delay)
    sys.stdout.write(end); sys.stdout.flush()

def reveal(line, delay=0.018):
    """Print a (possibly pre-coloured) line with a small fade-in pause."""
    if ANIMATE:
        time.sleep(delay)
    print(line)

def shimmer(text, stops=FLOW, cycles=2, step=0.06, speed=0.08):
    """Print `text` once, then sweep a moving gradient across it a few times."""
    if not ANIMATE:
        print(gradient(text, stops)); return
    shift = 0.0
    reps  = int(cycles / step)
    for _ in range(reps):
        sys.stdout.write("\r" + gradient(text, stops, shift))
        sys.stdout.flush()
        shift = (shift + step) % 1.0
        time.sleep(speed)
    sys.stdout.write("\r" + gradient(text, stops) + "\n")
    sys.stdout.flush()

# ── Block font banner ──────────────────────────────────────────────────────────

_FONT_H = 5
_FONT = {
    " ": ["   "] * 5,
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
    "B": ["████ ", "█   █", "████ ", "█   █", "████ "],
    "C": [" ████", "█    ", "█    ", "█    ", " ████"],
    "D": ["████ ", "█   █", "█   █", "█   █", "████ "],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "F": ["█████", "█    ", "████ ", "█    ", "█    "],
    "G": [" ████", "█    ", "█  ██", "█   █", " ████"],
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "J": ["█████", "   █ ", "   █ ", "█  █ ", " ██  "],
    "K": ["█   █", "█  █ ", "███  ", "█  █ ", "█   █"],
    "L": ["█    ", "█    ", "█    ", "█    ", "█████"],
    "M": ["█   █", "██ ██", "█ █ █", "█   █", "█   █"],
    "N": ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    "O": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "P": ["████ ", "█   █", "████ ", "█    ", "█    "],
    "Q": [" ███ ", "█   █", "█ █ █", "█  █ ", " ██ █"],
    "R": ["████ ", "█   █", "████ ", "█  █ ", "█   █"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "U": ["█   █", "█   █", "█   █", "█   █", " ███ "],
    "V": ["█   █", "█   █", "█   █", " █ █ ", "  █  "],
    "W": ["█   █", "█   █", "█ █ █", "██ ██", "█   █"],
    "X": ["█   █", " █ █ ", "  █  ", " █ █ ", "█   █"],
    "Y": ["█   █", " █ █ ", "  █  ", "  █  ", "  █  "],
    "Z": ["█████", "   █ ", "  █  ", " █   ", "█████"],
    "0": [" ███ ", "█  ██", "█ █ █", "██  █", " ███ "],
    "1": ["  █  ", " ██  ", "  █  ", "  █  ", "█████"],
    "2": [" ███ ", "█   █", "  ██ ", " █   ", "█████"],
    "3": ["████ ", "   █ ", " ██  ", "   █ ", "████ "],
    "4": ["█  █ ", "█  █ ", "█████", "   █ ", "   █ "],
    "5": ["█████", "█    ", "████ ", "    █", "████ "],
    "6": [" ████", "█    ", "████ ", "█   █", " ███ "],
    "7": ["█████", "   █ ", "  █  ", " █   ", "█    "],
    "8": [" ███ ", "█   █", " ███ ", "█   █", " ███ "],
    "9": [" ███ ", "█   █", " ████", "    █", "████ "],
    "-": ["     ", "     ", " ███ ", "     ", "     "],
    ":": ["     ", "  █  ", "     ", "  █  ", "     "],
    "!": ["  █  ", "  █  ", "  █  ", "     ", "  █  "],
}

def _big_text(text):
    rows = ["" for _ in range(_FONT_H)]
    for ch in text:
        glyph = _FONT.get(ch.upper(), ["  "] * _FONT_H)
        for r in range(_FONT_H):
            rows[r] += glyph[r] + "  "
    return [r.rstrip() for r in rows]

def _banner_simple(alias):
    spaced  = (" " + DOT + " ").join(alias.upper())
    sub     = "C M D   H E L P E R"
    width   = max(len(spaced), len(sub)) + 8
    s_pad   = " " * ((width - len(spaced)) // 2)
    b_pad   = " " * ((width - len(sub))   // 2)
    s_trail = " " * (width - len(spaced) - len(s_pad))
    b_trail = " " * (width - len(sub)    - len(b_pad))

    print()
    print(bold(cyan("  ╔" + "═" * width + "╗")))
    print(bold(cyan("  ║")) + " " * width               + bold(cyan("║")))
    print(bold(cyan("  ║")) + s_pad + bold(cyan(spaced)) + s_trail + bold(cyan("║")))
    print(bold(cyan("  ║")) + b_pad + yellow(sub)        + b_trail + bold(cyan("║")))
    print(bold(cyan("  ║")) + " " * width               + bold(cyan("║")))
    print(bold(cyan("  ╚" + "═" * width + "╝")))
    print()

def banner(alias):
    if not USE_UNICODE:
        return _banner_simple(alias)

    lines = _big_text(alias)
    width = max((len(l) for l in lines), default=0)
    pad   = "  "
    rule  = "─" * (width + 4)
    sub   = "C M D   H E L P E R"
    s_pad = " " * max(0, (width + 4 - len(sub)) // 2)

    print()
    print(pad + gradient("╭" + rule + "╮", FLOW))
    for ln in lines:
        body = "  " + ln.ljust(width) + "  "
        reveal(pad + gradient("│", FLOW) + gradient(body, FLOW) + gradient("│", tuple(reversed(FLOW))),
               delay=0.035)
    print(pad + gradient("│", FLOW) + " " * (width + 4) + gradient("│", tuple(reversed(FLOW))))
    print(pad + "  " + bold(dim(s_pad.replace(" ", " ") + sub)))
    print(pad + gradient("╰" + rule + "╯", tuple(reversed(FLOW))))
    print()

# ── Matrix rain intro with a Spider-Man emblem ────────────────────────────────

_RAIN_KATA  = ("ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
               "0123456789:.=*+<>|$%#&@")
_RAIN_ASCII = "01<>|/\\+*=$%#&@:.0123456789ABCDEFXYZ"

def _bres(r0, c0, r1, c1):
    """Bresenham line — returns the list of (row, col) cells between two points."""
    pts = []
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dr - dc
    r, c = r0, c0
    while True:
        pts.append((r, c))
        if r == r1 and c == c1:
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc; r += sr
        if e2 < dr:
            err += dr; c += sc
    return pts

def _build_spider():
    """Rasterise a symmetric 8-legged spider emblem.
    Returns (mask, body, height, width) where mask/body are sets of (row, col)."""
    H, W   = 17, 33
    cr, cc = 8, 16                       # centre
    mask, body = set(), set()

    # body = abdomen (lower, larger) + head (upper, smaller)
    for r in range(H):
        for c in range(W):
            if ((c - cc) / 4.6) ** 2 + ((r - (cr + 1)) / 2.3) ** 2 <= 1:
                mask.add((r, c)); body.add((r, c))
            if ((c - cc) / 2.6) ** 2 + ((r - (cr - 3)) / 1.6) ** 2 <= 1:
                mask.add((r, c)); body.add((r, c))

    # 4 legs per side: (elbow_dr, elbow_dc, foot_dr, foot_dc) for the RIGHT side
    legs = [(-4, 8, -6, 14), (-1, 10, -2, 16), (2, 10, 3, 16), (5, 8, 7, 14)]
    for edr, edc, fdr, fdc in legs:
        for sign in (1, -1):
            attach = (cr, cc + 3 * sign)
            elbow  = (cr + edr, cc + edc * sign)
            foot   = (cr + fdr, cc + fdc * sign)
            for seg in (_bres(*attach, *elbow), _bres(*elbow, *foot)):
                mask.update(seg)

    mask = {(r, c) for (r, c) in mask if 0 <= r < H and 0 <= c < W}
    body = {(r, c) for (r, c) in body if 0 <= r < H and 0 <= c < W}
    return mask, body, H, W

def _key_skip():
    """Non-blocking check: did the user press a key to skip the intro?"""
    if IS_WIN:
        try:
            import msvcrt
            if msvcrt.kbhit():
                msvcrt.getch()
                return True
        except Exception:
            pass
    return False

def matrix_intro(duration=2.6, fps=18):
    """Full-screen Matrix rain with a static red Spider-Man emblem in the centre."""
    if not (ANIMATE and USE_COLOR):
        return
    try:
        size = shutil.get_terminal_size(fallback=(90, 28))
    except Exception:
        return
    W = max(40, size.columns - 1)
    H = max(16, size.lines - 1)

    charset = _RAIN_KATA if USE_UNICODE else _RAIN_ASCII
    block   = "█" if USE_UNICODE else "#"

    # centre the spider
    smask, sbody, sh, sw = _build_spider()
    off_r, off_c = (H - sh) // 2, (W - sw) // 2
    spider = {(off_r + r, off_c + c): ((r, c) in sbody) for (r, c) in smask}

    # per-column rain state
    head   = [random.uniform(-H, 0)      for _ in range(W)]
    speed  = [random.uniform(0.45, 1.15) for _ in range(W)]
    length = [random.randint(6, 18)      for _ in range(W)]
    active = [random.random() < 0.9      for _ in range(W)]
    prev_i = [-999] * W
    grid   = [[" "] * W for _ in range(H)]

    def rnd():
        return charset[random.randrange(len(charset))]

    frames = max(1, int(duration * fps))
    delay  = 1.0 / fps

    sys.stdout.write("\033[?25l\033[2J")          # hide cursor + clear
    sys.stdout.flush()
    try:
        for _ in range(frames):
            if _key_skip():
                break
            for c in range(W):
                if not active[c]:
                    if random.random() < 0.03:
                        active[c], head[c] = True, random.uniform(-6, 0)
                        speed[c]  = random.uniform(0.45, 1.15)
                        length[c] = random.randint(6, 18)
                        prev_i[c] = -999
                    continue
                head[c] += speed[c]
                ih    = int(head[c])
                start = prev_i[c] + 1 if prev_i[c] > -999 else ih
                for y in range(max(0, start), min(H, ih + 1)):
                    grid[y][c] = rnd()
                prev_i[c] = ih
                if random.random() < 0.45:         # shimmer
                    yy = random.randrange(H)
                    if grid[yy][c] != " ":
                        grid[yy][c] = rnd()
                if ih - length[c] > H:             # respawn off the bottom
                    active[c] = random.random() < 0.9
                    head[c]   = random.uniform(-8, -1)
                    speed[c]  = random.uniform(0.45, 1.15)
                    length[c] = random.randint(6, 18)
                    prev_i[c] = -999
                    for y in range(H):
                        grid[y][c] = " "

            out = ["\033[H"]
            for r in range(H):
                line = []
                for c in range(W):
                    hit = spider.get((r, c))
                    if hit is not None:
                        if hit:
                            line.append(f"\033[1;38;2;255;45;45m{block}")   # body
                        else:
                            line.append(f"\033[1;38;2;205;25;25m{block}")   # legs
                        continue
                    ch = grid[r][c]
                    if ch == " ":
                        line.append(" ")
                        continue
                    d = int(head[c]) - r
                    L = length[c]
                    if d < 0 or d > L:
                        line.append(" ")
                    elif d == 0:
                        line.append(f"\033[1;38;2;215;255;215m{ch}")        # bright head
                    else:
                        v  = 1 - d / L
                        g  = int(70 + 165 * v)
                        rr = int(10 + 20 * v)
                        bb = int(30 + 30 * v)
                        line.append(f"\033[38;2;{rr};{g};{bb}m{ch}")        # fading tail
                line.append("\033[0m")
                out.append("".join(line))
                if r < H - 1:
                    out.append("\n")
            sys.stdout.write("".join(out))
            sys.stdout.flush()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")   # reset + show cursor + clear
        sys.stdout.flush()

# ── Live Matrix background + animated home menu ───────────────────────────────

class _MatrixField:
    """Holds and advances the state of a full-screen Matrix rain."""
    def __init__(self, W, H, bright=0.6):
        self.W, self.H, self.bright = W, H, bright
        self.head    = [random.uniform(-H, 0)    for _ in range(W)]
        self.speed   = [random.uniform(0.4, 1.1) for _ in range(W)]
        self.length  = [random.randint(6, 18)    for _ in range(W)]
        self.active  = [random.random() < 0.9    for _ in range(W)]
        self.prev    = [-999] * W
        self.grid    = [[" "] * W for _ in range(H)]
        self.charset = _RAIN_KATA if USE_UNICODE else _RAIN_ASCII
        # pre-baked classic-green palette: identical shades reuse ONE SGR code so
        # the renderer can coalesce long runs — this is what kills the lag.
        self.shades = []
        for i in range(6):
            v = i / 5
            r = int((0  + 35  * v) * bright)
            g = int((70 + 185 * v) * bright)
            b = int((8  + 28  * v) * bright)
            self.shades.append(f"\033[49;38;2;{r};{g};{b}m")
        self.head_sgr = "\033[49;1;38;2;190;255;190m"

    def _rnd(self):
        return self.charset[random.randrange(len(self.charset))]

    def step(self):
        H = self.H
        for c in range(self.W):
            if not self.active[c]:
                if random.random() < 0.03:
                    self.active[c] = True
                    self.head[c]   = random.uniform(-6, 0)
                    self.speed[c]  = random.uniform(0.4, 1.1)
                    self.length[c] = random.randint(6, 18)
                    self.prev[c]   = -999
                continue
            self.head[c] += self.speed[c]
            ih    = int(self.head[c])
            start = self.prev[c] + 1 if self.prev[c] > -999 else ih
            for y in range(max(0, start), min(H, ih + 1)):
                self.grid[y][c] = self._rnd()
            self.prev[c] = ih
            if random.random() < 0.4:
                yy = random.randrange(H)
                if self.grid[yy][c] != " ":
                    self.grid[yy][c] = self._rnd()
            if ih - self.length[c] > H:
                self.active[c] = random.random() < 0.9
                self.head[c]   = random.uniform(-8, -1)
                self.speed[c]  = random.uniform(0.4, 1.1)
                self.length[c] = random.randint(6, 18)
                self.prev[c]   = -999
                for y in range(H):
                    self.grid[y][c] = " "

    def cell(self, r, c):
        """Return (sgr_or_None, glyph) for rain at (r, c); None means default bg."""
        ch = self.grid[r][c]
        if ch == " ":
            return (None, " ")
        d = int(self.head[c]) - r
        L = self.length[c]
        if d < 0 or d > L:
            return (None, " ")
        if d == 0:
            return (self.head_sgr, ch)
        v = 1 - d / L
        return (self.shades[min(5, int(v * 6))], ch)


_HOME_MENU = [
    ("1", "run",       "Run"),
    ("2", "list",      "List"),
    ("3", "kill",      "Kill"),
    ("4", "open",      "Open"),
    ("5", "find",      "Find"),
    ("6", "ask",       "AI"),
    ("7", "check",     "Check"),
    ("8", "learn",     "Learn"),
    ("9", "guide",     "Guide"),
    ("s", "__shell__", "Shell"),
    ("q", "__quit__",  "Quit"),
]

def _sgr_fg(fg, bold_=False):
    pre = "1;" if bold_ else ""
    return f"\033[49;{pre}38;2;{fg[0]};{fg[1]};{fg[2]}m"

def _ocell(bg, fg, ch, bold_=False):
    pre = "1;" if bold_ else ""
    sgr = f"\033[{pre}48;2;{bg[0]};{bg[1]};{bg[2]};38;2;{fg[0]};{fg[1]};{fg[2]}m"
    return (sgr, ch)

def _stamp(ov, r, c, text, fg, bg=None, bold_=False):
    """Write `text` into overlay dict `ov` as (sgr, char) tuples from (r, c).
    `fg` may be an (r,g,b) tuple or a callable (i, n) -> rgb. Returns the end col."""
    n = len(text)
    for i, ch in enumerate(text):
        col = c + i
        if col < 0:
            continue
        color = fg(i, n) if callable(fg) else fg
        if bg is None:
            ov[(r, col)] = (_sgr_fg(color, bold_), ch)
        else:
            ov[(r, col)] = _ocell(bg, color, ch, bold_)
    return c + n

def _build_bottom_bar(alias, sel, W, H):
    """Overlay dict for the dark, readable command bar pinned to the bottom."""
    DARK = (12, 12, 18)
    segs = [(f" {key.upper()} {lab} ", i == sel)
            for i, (key, _a, lab) in enumerate(_HOME_MENU)]

    rows, cur = [[]], 0
    for text, seld in segs:                       # wrap segments to terminal width
        if cur + len(text) > W and rows[-1]:
            rows.append([]); cur = 0
        rows[-1].append((text, seld)); cur += len(text)

    title = f"{alias.upper()}  {DOT}  CMD HELPER"
    hint  = f"arrows move  {DOT}  Enter run  {DOT}  Q quit"
    top   = max(0, H - (len(rows) + 1))
    overlay = {}

    for c in range(W):                            # title / hint row
        overlay[(top, c)] = _ocell(DARK, (60, 60, 72), " ")
    for j, chc in enumerate(title):
        cc = 2 + j
        if cc < W - 1:
            overlay[(top, cc)] = _ocell(DARK, _stop_at(j / max(1, len(title) - 1), FLOW), chc, True)
    hs = W - len(hint) - 2
    for j, chc in enumerate(hint):
        cc = hs + j
        if 0 <= cc < W:
            overlay[(top, cc)] = _ocell(DARK, (120, 120, 135), chc)

    for ri, row in enumerate(rows):               # option rows
        rr = top + 1 + ri
        for c in range(W):
            overlay[(rr, c)] = _ocell(DARK, (200, 200, 212), " ")
        cc = 0
        for text, seld in row:
            for chc in text:
                if cc < W:
                    if seld:
                        overlay[(rr, cc)] = ("\033[1;48;2;210;30;35;38;2;255;255;255m", chc)
                    else:
                        overlay[(rr, cc)] = _ocell(DARK, (205, 205, 216), chc)
                cc += 1
    return overlay

def _compose_home(field, spider, alias, sel):
    W, H = field.W, field.H
    ov   = _build_bottom_bar(alias, sel, W, H)
    blk  = "█" if USE_UNICODE else "#"
    body_sgr = _sgr_fg((255, 45, 45), True)
    leg_sgr  = _sgr_fg((205, 25, 25), True)
    for (r, c), is_body in spider.items():
        if (r, c) not in ov:
            ov[(r, c)] = (body_sgr if is_body else leg_sgr, blk)
    return _render(field, ov, W, H)

# ── non-blocking key input (keeps the rain running while we wait) ──────────────

def _enter_cbreak():
    if IS_WIN:
        return None
    try:
        import termios, tty
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        attrs = termios.tcgetattr(fd)      # also silence echo so typing doesn't double-print
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        return (fd, old)
    except Exception:
        return None

def _exit_cbreak(state):
    if not state:
        return
    try:
        import termios
        fd, old = state
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass

def _poll_key():
    """Return a key token ('UP'/'DOWN'/'LEFT'/'RIGHT'/'ENTER'/'ESC'/char) or None."""
    if IS_WIN:
        try:
            import msvcrt
            if not msvcrt.kbhit():
                return None
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                return {"H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT"}.get(msvcrt.getwch())
            if ch in ("\r", "\n"):  return "ENTER"
            if ch == "\x1b":        return "ESC"
            if ch == "\x08":        return "BACKSPACE"
            return ch
        except Exception:
            return None
    try:
        import select
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if not dr:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            dr2, _, _ = select.select([sys.stdin], [], [], 0.001)
            if dr2:
                seq = sys.stdin.read(2)
                return {"[A": "UP", "[B": "DOWN", "[C": "RIGHT", "[D": "LEFT"}.get(seq, "ESC")
            return "ESC"
        if ch in ("\r", "\n"):     return "ENTER"
        if ch in ("\x7f", "\x08"): return "BACKSPACE"
        return ch
    except Exception:
        return None

def _screen_enter():
    sys.stdout.write("\033[?25l\033[2J"); sys.stdout.flush()

def _screen_leave(cbreak):
    sys.stdout.write("\033[0m\033[?25h\033[2J\033[H"); sys.stdout.flush()
    _exit_cbreak(cbreak)

def home_screen(config, os_name):
    """Continuous Matrix background with a live, navigable command menu on top."""
    if not (ANIMATE and USE_COLOR):
        print_help(config); return
    try:
        size = shutil.get_terminal_size(fallback=(90, 28))
    except Exception:
        print_help(config); return
    if size.columns < 50 or size.lines < 16:
        print_help(config); return
    try:
        _home_loop(config, os_name, size)
    except Exception:
        try:
            sys.stdout.write("\033[0m\033[?25h\033[2J\033[H"); sys.stdout.flush()
        except Exception:
            pass
        print_help(config)

def _home_loop(config, os_name, size):
    alias = config.get("alias", "spider")
    W = max(50, size.columns - 1)
    H = max(16, size.lines - 1)

    cmd_handlers = {
        "run": handle_run, "list": handle_list, "kill": handle_kill,
        "open": handle_open, "find": handle_find, "ask": handle_ask,
        "check": handle_check, "learn": handle_learn, "guide": handle_guide,
    }

    field  = _MatrixField(W, H, bright=0.72)
    smask, sbody, sh, sw = _build_spider()
    off_r  = max(1, (H - sh) // 2 - 3)
    off_c  = max(0, (W - sw) // 2)
    spider = {(off_r + r, off_c + c): ((r, c) in sbody) for (r, c) in smask}

    sel, n = 0, len(_HOME_MENU)
    delay  = 1.0 / 16

    cbreak = _enter_cbreak()
    _screen_enter()
    try:
        while True:
            field.step()
            sys.stdout.write(_compose_home(field, spider, alias, sel))
            sys.stdout.flush()

            chosen = None
            k = _poll_key()
            if k is not None:
                if k in ("LEFT", "UP"):
                    sel = (sel - 1) % n
                elif k in ("RIGHT", "DOWN"):
                    sel = (sel + 1) % n
                elif k in ("ESC", "q", "Q"):
                    chosen = "__quit__"
                elif k == "ENTER":
                    chosen = _HOME_MENU[sel][1]
                else:
                    for i, (key, act, _l) in enumerate(_HOME_MENU):
                        if k.lower() == key:
                            sel, chosen = i, act
                            break

            if chosen == "__quit__":
                break
            if chosen:
                _screen_leave(cbreak)
                try:
                    if chosen == "__shell__":
                        handle_repl([], config, os_name)
                    else:
                        cmd_handlers[chosen]([], config, os_name)
                except SystemExit:
                    pass
                except KeyboardInterrupt:
                    pass
                except Exception as exc:
                    print(error(f"\n  {CROSS} {exc}"))
                try:
                    input(f"\n  {dim('Press Enter to return to the matrix')} {bold(cyan(ARROW))} ")
                except (EOFError, KeyboardInterrupt):
                    pass
                cbreak = _enter_cbreak()
                _screen_enter()
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        _screen_leave(cbreak)
    print(f"  {green(CHECK)}  {gradient('Stay legendary.', FLOW)}\n")

# ── Live Matrix shell (banner + header + typed prompt over the rain) ───────────

def _render(field, overlay, W, H):
    """Composite a Matrix frame + overlay of (sgr, char) tuples, coalescing runs of
    the same colour into one SGR code so the terminal has far less to parse."""
    RESET = "\033[0m"
    parts = ["\033[H"]
    cur   = None
    get   = overlay.get
    fcell = field.cell
    for r in range(H):
        row = []
        for c in range(W):
            cell = get((r, c)) or fcell(r, c)
            sgr, ch = cell
            if sgr is None:
                sgr = RESET
            if sgr != cur:
                row.append(sgr)
                cur = sgr
            row.append(ch)
        row.append(RESET)
        cur = RESET
        parts.append("".join(row))
        if r < H - 1:
            parts.append("\n")
    return "".join(parts)

_BANNER_GREEN = ((0, 200, 90), (140, 255, 150))

def _shell_overlay(alias, buffer, cwd_disp, W, H, cursor_on):
    """Readable banner + header + prompt overlay — classic green-on-black theme."""
    ov   = {}
    DARK = (6, 10, 6)                       # near-black, like a console cell

    # SPIDER block banner (green gradient letters straight over the rain)
    lines = _big_text(alias)
    bw    = max((len(l) for l in lines), default=1)
    for i, ln in enumerate(lines):
        for j, ch in enumerate(ln):
            if ch != " ":
                fg  = _stop_at(j / max(1, bw - 1), _BANNER_GREEN)
                col = 2 + j
                if col < W:
                    ov[(1 + i, col)] = (_sgr_fg(fg, True), "█")
    _stamp(ov, 1 + len(lines), 4, "C M D   H E L P E R", (90, 175, 110), DARK)

    r0    = len(lines) + 3
    cmdcol = lambda i, n: _stop_at(i / max(1, n - 1), ((120, 255, 140), (205, 255, 175)))

    c = _stamp(ov, r0, 2, "Interactive Mode", (235, 255, 235), DARK, True)
    _stamp(ov, r0, c, f"  {STAR} live terminal + AI ", (120, 185, 130), DARK)

    cmds = "run  list  kill  open  find  check  learn  guide  ask  intro  exit"
    c = _stamp(ov, r0 + 1, 2, f"{alias.capitalize()}: ", (120, 185, 130), DARK, True)
    _stamp(ov, r0 + 1, c, cmds + " ", cmdcol, DARK)

    _stamp(ov, r0 + 2, 2,
           "System:  any real command — ls, cd, git, ping, docker, ps ... ",
           (120, 165, 130), DARK)

    c = _stamp(ov, r0 + 3, 2, "AI:      ", (120, 165, 130), DARK)
    c = _stamp(ov, r0 + 3, c, ":", (180, 255, 120), DARK, True)
    _stamp(ov, r0 + 3, c, " prefix — e.g. : how do I zip a folder ", (120, 165, 130), DARK)

    # prompt line
    prow = r0 + 5
    pc = _stamp(ov, prow, 2, alias, (120, 255, 140), DARK, True)
    pc = _stamp(ov, prow, pc, " ", (0, 0, 0), DARK)
    pc = _stamp(ov, prow, pc, cwd_disp, (110, 185, 150), DARK)
    pc = _stamp(ov, prow, pc, f" {ARROW} ", (150, 255, 150), DARK, True)

    avail = max(4, W - pc - 3)
    shown = buffer[-avail:] if len(buffer) > avail else buffer
    pc = _stamp(ov, prow, pc, shown, (235, 255, 235), DARK, True)

    cur = ("█" if USE_UNICODE else "_") if cursor_on else " "
    if pc < W:
        ov[(prow, pc)] = _ocell(DARK, (150, 255, 150), cur, True)
        _stamp(ov, prow, pc + 1, " ", (0, 0, 0), DARK)        # trailing pad
    return ov

def _dispatch_repl_line(raw, config, os_name):
    """Execute one typed line the same way the plain REPL does."""
    handlers = {
        "run":   handle_run,  "list":  handle_list,  "kill":  handle_kill,
        "open":  handle_open, "find":  handle_find,  "check": handle_check,
        "learn": handle_learn, "guide": handle_guide, "ask":  handle_ask,
        "intro": handle_intro,
    }
    if raw.startswith(":"):
        try:
            handle_ask(raw[1:].strip().split(), config, os_name)
        except SystemExit:
            pass
        return
    parts   = raw.split()
    command = parts[0].lower()
    rest    = parts[1:]
    if command in handlers:
        try:
            handlers[command](rest, config, os_name)
        except SystemExit:
            pass
        return
    if command == "cd":
        target = os.path.expanduser(" ".join(rest)) if rest else os.path.expanduser("~")
        try:
            os.chdir(target)
        except FileNotFoundError:
            print(error(f"  {CROSS} cd: no such directory: {target}\n"))
        except PermissionError:
            print(error(f"  {CROSS} cd: permission denied: {target}\n"))
        except Exception as exc:
            print(error(f"  {CROSS} cd: {exc}\n"))
        return
    print()
    try:
        result = subprocess.run(raw, shell=True)
        if result.returncode != 0:
            print(dim(f"  (exit {result.returncode})"))
    except Exception as exc:
        print(error(f"  {CROSS} {exc}"))
    print()

def _animated_repl(config, os_name):
    """Interactive REPL drawn over a continuously animated Matrix background."""
    alias = config.get("alias", "spider")
    try:
        size = shutil.get_terminal_size(fallback=(90, 28))
    except Exception:
        return handle_repl([], config, os_name)
    if size.columns < 54 or size.lines < 18:
        return handle_repl([], config, os_name)

    W = max(54, size.columns - 1)
    H = max(18, size.lines - 1)
    field  = _MatrixField(W, H, bright=0.6)
    buffer = ""
    frame  = 0

    cbreak = _enter_cbreak()
    _screen_enter()
    try:
        while True:
            field.step()
            cwd  = os.getcwd()
            home = os.path.expanduser("~")
            disp = ("~" + cwd[len(home):]) if cwd.startswith(home) else cwd
            ov   = _shell_overlay(alias, buffer, disp, W, H, (frame // 8) % 2 == 0)
            sys.stdout.write(_render(field, ov, W, H))
            sys.stdout.flush()
            frame += 1

            run_now = False
            for _ in range(4):
                k = _poll_key()
                if k is None:
                    time.sleep(0.015)
                    continue
                if k == "ENTER":
                    run_now = True
                elif k == "BACKSPACE":
                    buffer = buffer[:-1]
                elif k == "ESC":
                    buffer = ""
                elif k in ("UP", "DOWN", "LEFT", "RIGHT"):
                    pass
                elif len(k) == 1 and k.isprintable():
                    buffer += k
                break

            if run_now:
                raw, buffer = buffer.strip(), ""
                if raw.lower() in ("exit", "quit", "q", "bye"):
                    break
                if raw:
                    _screen_leave(cbreak)
                    _dispatch_repl_line(raw, config, os_name)
                    try:
                        input(f"\n  {dim('Press Enter to return to the matrix')} {bold(cyan(ARROW))} ")
                    except (EOFError, KeyboardInterrupt):
                        pass
                    cbreak = _enter_cbreak()
                    _screen_enter()
    except KeyboardInterrupt:
        pass
    finally:
        _screen_leave(cbreak)
    print(f"  {green(CHECK)}  {gradient('See you in the shadows.', FLOW)}\n")

# ── Section header ─────────────────────────────────────────────────────────────

def section(num, title, color_fn=None):
    label = f"  {num}. {title}  "
    line  = "─" * max(0, 60 - len(label))
    print(bold(gradient(label + line, FLOW)))

# ── Badges + command rows ──────────────────────────────────────────────────────

_BADGE_COLORS = {
    "RUN": blue, "LIST": cyan, "KILL": red,
    "OPEN": green, "FIND": magenta, "AI": yellow, "SHELL": white,
}

def badge(label):
    color = _BADGE_COLORS.get(label, white)
    return bold(color(f"[{label}]"))

def cmd_row(bdg, cmd, desc):
    b   = badge(bdg)
    c   = bold(green(cmd))
    gap = max(1, 46 - len(cmd))
    return f"  {b}  {c}{' ' * gap}{dim(desc)}"

# ── Spinner ────────────────────────────────────────────────────────────────────

_FRAMES = (["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
           if USE_UNICODE else ["|","/","-","\\"])
_SPIN_COLORS = [NEON_A, NEON_B, NEON_C, NEON_D, NEON_C, NEON_B]

class Spinner:
    def __init__(self, msg="Working"):
        self.msg   = msg
        self._stop = threading.Event()
        self._t    = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        ci = 0
        for f in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                break
            r, g, b = _SPIN_COLORS[ci % len(_SPIN_COLORS)]
            ci += 1
            spin = rgb(f, r, g, b) if USE_COLOR else f
            print(f"\r  {bold(spin)}  {dim(self.msg + '...')}", end="", flush=True)
            time.sleep(0.08)
        print("\r" + " " * 55 + "\r", end="", flush=True)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._t.join()

# ── Fuzzy match ────────────────────────────────────────────────────────────────

def fuzzy_match(query, choices, cutoff=0.55):
    m = difflib.get_close_matches(query, choices, n=1, cutoff=cutoff)
    return m[0] if m else None

# ── Interactive helpers ────────────────────────────────────────────────────────

def pick_from_list(items, prompt="Select an option"):
    print(f"\n  {bold(cyan(prompt))}")
    for i, item in enumerate(items, 1):
        print(f"    {bold(yellow(str(i)))}  {white(item)}")
    print()
    while True:
        try:
            raw = input(f"  {bold(cyan(ARROW))} ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(error(f"  {CROSS} Invalid choice, try again."))
        except ValueError:
            print(error(f"  {CROSS} Please enter a number."))
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)


def ask_yes_no(prompt):
    while True:
        try:
            raw = input(f"  {bold(prompt)} {dim('(y/n)')} ").strip().lower()
            if raw in ("y", "yes"): return True
            if raw in ("n", "no"):  return False
            print(error(f"  {CROSS} Please enter y or n."))
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

# ── Command runners ────────────────────────────────────────────────────────────

def run_detached(cmd):
    try:
        if IS_WIN:
            subprocess.Popen(cmd, shell=True,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(error(f"  {CROSS} Command not found: {cmd[0]}"))
        sys.exit(1)

def run_inline(cmd):
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        print(error(f"  {CROSS} Command not found: {cmd[0]}"))
        sys.exit(1)

# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_run(args, config, os_name):
    apps          = config.get("apps", {})
    private_flags = config.get("private_flags", {})
    private       = False
    remaining     = list(args)

    if remaining and remaining[0].lower() == "private":
        private = True
        remaining.pop(0)

    app_name = remaining[0].lower() if remaining else None

    if not app_name:
        choices = list(apps.keys())
        if not choices:
            print(error(f"  {CROSS} No apps configured in config.json"))
            sys.exit(1)
        app_name = pick_from_list(choices, "Select an app to launch")

    if app_name not in apps:
        suggestion = fuzzy_match(app_name, list(apps.keys()))
        if suggestion:
            print(yellow(f"\n  {BULLET} '{app_name}' → did you mean '{bold(suggestion)}'? Running that..."))
            app_name = suggestion
        else:
            print(error(f"\n  {CROSS} Unknown app: '{app_name}'"))
            print(dim(f"  Available: {', '.join(apps.keys())}"))
            sys.exit(1)

    if not private and app_name in private_flags:
        private = ask_yes_no(f"Open {bold(white(app_name))} in private/incognito mode?")

    cmd = apps[app_name].get(os_name)
    if not cmd:
        print(error(f"  {CROSS} No command configured for '{app_name}' on {os_name}"))
        sys.exit(1)

    cmd = list(cmd)
    if private and app_name in private_flags:
        flag = private_flags[app_name].get(os_name)
        if flag:
            cmd.append(flag)

    mode = dim("  (private)") if private else ""
    print(f"\n  {bold(green(CHECK))}  Launching {bold(white(app_name))}{mode}\n")
    run_detached(cmd)


def handle_list(args, config, os_name):
    list_commands = config.get("list_commands", {})
    category      = args[0].lower() if args else None

    if not category:
        choices = list(list_commands.keys())
        if not choices:
            print(error(f"  {CROSS} No list commands configured in config.json"))
            sys.exit(1)
        category = pick_from_list(choices, "What do you want to list?")

    if category not in list_commands:
        suggestion = fuzzy_match(category, list(list_commands.keys()))
        if suggestion:
            print(yellow(f"\n  {BULLET} '{category}' → did you mean '{bold(suggestion)}'? Running that..."))
            category = suggestion
        else:
            print(error(f"\n  {CROSS} Unknown category: '{category}'"))
            print(dim(f"  Available: {', '.join(list_commands.keys())}"))
            sys.exit(1)

    cmd = list_commands[category].get(os_name)
    if not cmd:
        print(error(f"  {CROSS} No command for '{category}' on {os_name}"))
        sys.exit(1)

    w = 56
    print()
    print(bold(cyan("  ┌" + "─" * w + "┐")))
    label = f"  {category.upper()}"
    print(bold(cyan("  │")) + bold(white(label)) + " " * (w - len(label)) + bold(cyan("│")))
    print(bold(cyan("  └" + "─" * w + "┘")))
    print()
    run_inline(list(cmd))
    print()


def handle_kill(args, config, os_name):
    process_name = args[0] if args else None

    if not process_name:
        try:
            process_name = input(f"\n  {bold(red('Process to kill:'))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    if not process_name:
        print(error(f"  {CROSS} No process name provided."))
        sys.exit(1)

    if not ask_yes_no(f"Kill {bold(red(process_name))}?"):
        print(dim("\n  Cancelled.\n"))
        return

    if os_name == "windows":
        cmd = ["taskkill", "/IM", f"{process_name}.exe", "/F"]
    else:
        cmd = ["pkill", "-f", process_name]

    print(f"\n  {bold(red(CROSS))}  Killing {bold(white(process_name))}...\n")
    run_inline(cmd)


def handle_open(args, config, os_name):
    path = " ".join(args) if args else None

    if not path:
        try:
            path = input(f"\n  {bold(green('Path to open:'))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    if not path:
        print(error(f"  {CROSS} No path provided."))
        sys.exit(1)

    if os_name == "mac":
        cmd = ["open", path]
    elif os_name == "windows":
        cmd = ["explorer", path]
    else:
        cmd = ["xdg-open", path]

    print(f"\n  {bold(green(CHECK))}  Opening {bold(white(path))}\n")
    run_detached(cmd)


def handle_find(args, config, os_name):
    query = " ".join(args) if args else None

    if not query:
        try:
            query = input(f"\n  {bold(magenta('Search pattern:'))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    if not query:
        print(error(f"  {CROSS} No search query provided."))
        sys.exit(1)

    w = 56
    print()
    print(bold(magenta("  ┌" + "─" * w + "┐")))
    label = f"  Searching for: {query}"
    print(bold(magenta("  │")) + bold(white(label)) + " " * (w - len(label)) + bold(magenta("│")))
    print(bold(magenta("  └" + "─" * w + "┘")))
    print()

    if os_name == "windows":
        run_inline(["cmd", "/c", "dir", "/s", "/b", f"*{query}*"])
    else:
        run_inline(["find", ".", "-iname", f"*{query}*", "-not", "-path", "*/.git/*"])
    print()

# ── Dev tools audit ───────────────────────────────────────────────────────────

DEV_TOOLS = [
    ("Core Tools", [
        ("git",    ["--version"],  "Version control — essential for every developer"),
        ("curl",   ["--version"],  "HTTP client — API testing and downloads"),
        ("wget",   ["--version"],  "File downloader"),
        ("ssh",    ["-V"],         "Secure shell — remote server access"),
        ("make",   ["--version"],  "Build automation"),
        ("vim",    ["--version"],  "Terminal text editor"),
        ("nano",   ["--version"],  "Beginner-friendly terminal editor"),
    ]),
    ("Languages", [
        ("python3", ["--version"], "Python 3 — scripting, automation, data"),
        ("python",  ["--version"], "Python (may be 2 or 3)"),
        ("node",    ["--version"], "Node.js — JavaScript runtime"),
        ("npm",     ["--version"], "Node package manager"),
        ("go",      ["version"],   "Go language"),
        ("cargo",   ["--version"], "Rust (via cargo)"),
        ("ruby",    ["--version"], "Ruby language"),
        ("java",    ["--version"], "Java runtime"),
        ("php",     ["--version"], "PHP runtime"),
    ]),
    ("Containers", [
        ("docker",         ["--version"],           "Container runtime"),
        ("docker-compose", ["--version"],           "Multi-container orchestration"),
        ("kubectl",        ["version", "--client"], "Kubernetes CLI"),
    ]),
    ("Useful Utilities", [
        ("htop",   ["--version"], "Better process viewer than top"),
        ("tree",   ["--version"], "Directory tree display"),
        ("jq",     ["--version"], "JSON processor for terminal"),
        ("tmux",   ["-V"],        "Terminal multiplexer — multiple panes"),
        ("fzf",    ["--version"], "Fuzzy finder for anything"),
        ("bat",    ["--version"], "Better cat with syntax highlighting"),
        ("rg",     ["--version"], "ripgrep — fast code search"),
    ]),
]


def handle_check(args, config, os_name):
    alias = config.get("alias", "spider")

    banner(alias)
    print(f"  {bold(cyan('Dev Environment Audit'))}  {dim('— checking installed tools')}\n")

    _CAT_COLORS = {
        "Core Tools":       cyan,
        "Languages":        green,
        "Containers":       blue,
        "Useful Utilities": magenta,
    }

    total = found = 0

    for cat_name, tools in DEV_TOOLS:
        color_fn = _CAT_COLORS.get(cat_name, white)
        w        = 60
        label    = f"  {cat_name}"
        print(bold(color_fn(f"  ┌{'─' * w}┐")))
        print(bold(color_fn(f"  │")) + bold(white(label)) + " " * (w - len(label)) + bold(color_fn(f"│")))
        print(bold(color_fn(f"  └{'─' * w}┘")))
        print()

        for tool, flags, desc in tools:
            total += 1
            name_col = (tool + ":").ljust(16)
            try:
                res = subprocess.run(
                    [tool] + flags,
                    capture_output=True, text=True, timeout=3
                )
                raw = (res.stdout + res.stderr).strip().split("\n")[0]
                version = raw[:52] if raw else "installed"
                print(f"  {bold(green(CHECK))}  {bold(white(name_col))} {dim(version)}")
                found += 1
            except (FileNotFoundError, PermissionError):
                print(f"  {bold(red(CROSS))}  {dim(name_col)} {dim(desc)}")
            except subprocess.TimeoutExpired:
                print(f"  {yellow('?')}   {yellow(name_col)} {dim('timed out')}")
            except Exception:
                print(f"  {bold(red(CROSS))}  {dim(name_col)} {dim(desc)}")

        print()

    missing = total - found
    status  = (bold(green(f"{found} installed")) + "  " +
               (bold(red(f"{missing} missing")) if missing else dim("0 missing")))
    print(f"  {bold(cyan('Result:'))}  {status}\n")

    if missing:
        if os_name == "linux":
            print(f"  {dim('Install missing:')}  {cyan('sudo apt install <tool>')}  "
                  f"{dim('or')}  {cyan('pip install <tool>')}\n")
        elif os_name == "mac":
            print(f"  {dim('Install missing:')}  {cyan('brew install <tool>')}\n")
        else:
            print(f"  {dim('Install missing:')}  {cyan('winget install <tool>')}  "
                  f"{dim('or search')}  {cyan('chocolatey.org')}\n")


# ── Learn ─────────────────────────────────────────────────────────────────────

def handle_learn(args, config, os_name):
    sys.path.insert(0, SCRIPT_DIR)
    import cmd_reference as ref

    alias = config.get("alias", "spider")
    paths = ref.LEARN_PATHS

    banner(alias)
    print(f"  {bold(cyan('Learning Paths'))}  {dim('— structured terminal skills for developers')}\n")

    path_keys = list(paths.keys())
    for i, key in enumerate(path_keys, 1):
        p        = paths[key]
        n        = len(p["lessons"])
        lesson_s = "lesson" if n == 1 else "lessons"
        print(f"    {bold(yellow(str(i)))}  {bold(white(key))}  "
              f"{dim(f'({n} {lesson_s})')}  {dim(p['desc'])}")
    print()

    while True:
        try:
            raw = input(f"  {bold(cyan(ARROW))} ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(path_keys):
                sel_path = path_keys[idx]
                break
            print(error(f"  {CROSS} Enter 1–{len(path_keys)}."))
        except ValueError:
            print(error(f"  {CROSS} Please enter a number."))
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    path_data = paths[sel_path]
    lessons   = path_data["lessons"]

    def print_lesson(lesson):
        w     = 60
        label = f"  {lesson['title']}"
        print()
        print(bold(yellow(f"  ┌{'─' * w}┐")))
        print(bold(yellow(f"  │")) + bold(white(label)) + " " * (w - len(label)) + bold(yellow(f"│")))
        print(bold(yellow(f"  └{'─' * w}┘")))
        print()
        print(f"  {bold(cyan('Concept'))}")
        for line in lesson["concept"]:
            print(f"    {white(line)}")
        print()
        print(f"  {bold(cyan('Commands'))}")
        for cmd_str, desc in lesson["commands"]:
            gap = max(1, 42 - len(cmd_str))
            print(f"    {bold(green(cmd_str))}{' ' * gap}{dim(desc)}")
        print()
        print(f"  {bold(yellow('Pro Tip'))}  {white(lesson['tip'])}")
        print()
        print(f"  {bold(magenta('Try It'))}  {white(lesson['challenge'])}")
        print()

    while True:
        w     = 60
        label = f"  {sel_path}"
        print()
        print(bold(cyan(f"  ┌{'─' * w}┐")))
        print(bold(cyan(f"  │")) + bold(white(label)) + " " * (w - len(label)) + bold(cyan(f"│")))
        print(bold(cyan(f"  └{'─' * w}┘")))
        print()

        lesson_options = [l["title"] for l in lessons] + ["All Lessons"]
        for i, opt in enumerate(lesson_options, 1):
            if opt == "All Lessons":
                print(f"    {bold(yellow(str(i)))}  {bold(white(opt))}")
            else:
                print(f"    {bold(yellow(str(i)))}  {white(opt)}")
        print()

        while True:
            try:
                raw = input(f"  {bold(cyan(ARROW))} ").strip()
                idx = int(raw) - 1
                if 0 <= idx < len(lesson_options):
                    sel = lesson_options[idx]
                    break
                print(error(f"  {CROSS} Enter 1–{len(lesson_options)}."))
            except ValueError:
                print(error(f"  {CROSS} Please enter a number."))
            except KeyboardInterrupt:
                print(error("\n  Cancelled."))
                sys.exit(0)

        if sel == "All Lessons":
            for i, lesson in enumerate(lessons):
                print_lesson(lesson)
                if i < len(lessons) - 1:
                    try:
                        cont = input(
                            f"  {dim('── Enter for next lesson, q to stop ──')} "
                        ).strip().lower()
                        if cont == "q":
                            break
                    except KeyboardInterrupt:
                        break
        else:
            lesson = next(l for l in lessons if l["title"] == sel)
            print_lesson(lesson)

        if not ask_yes_no("View another lesson?"):
            break

    print(f"\n  {dim('Session closed.')}  "
          f"{dim('Type')} {cyan(alias + ' learn')} {dim('to open again.')}\n")


# ── Help ──────────────────────────────────────────────────────────────────────

def print_help(config):
    alias = config.get("alias", "spider")
    apps  = list(config.get("apps", {}).keys())
    lists = list(config.get("list_commands", {}).keys())

    banner(alias)

    print(f"  {dim('Usage:')}  {bold(gradient(alias, FLOW))} {dim('<command> [options]')}\n")

    rows = [
        ("RUN",   f"{alias} run <app>",             "Launch an app"),
        ("RUN",   f"{alias} run private <app>",     "Launch in private/incognito"),
        ("LIST",  f"{alias} list <category>",       "Show system info"),
        ("KILL",  f"{alias} kill <process>",        "Kill a running process"),
        ("OPEN",  f"{alias} open <path>",           "Open a file or folder"),
        ("FIND",  f"{alias} find <name>",           "Search files by name"),
        ("AI",    f"{alias} ask <question>",        "Ask AI — any terminal/dev question"),
        ("AI",    f"{alias}: <question>",           "AI shortcut inside shell mode"),
        ("SHELL", f"{alias} check",                 "Audit installed dev tools"),
        ("SHELL", f"{alias} learn",                 "Interactive learning paths"),
        ("SHELL", f"{alias} guide",                 "Full command reference"),
        ("SHELL", f"{alias} shell",                 "Interactive terminal mode"),
        ("SHELL", f"{alias} intro",                 "Play the Matrix + spider intro"),
        ("SHELL", f"{alias} home",                  "Live Matrix menu (optional)"),
    ]

    for bdg, cmd, desc in rows:
        reveal(cmd_row(bdg, cmd, desc), delay=0.012)

    print()
    if apps:
        print(f"  {dim('Apps:')}   {gradient(', '.join(apps), (NEON_A, NEON_B))}")
    if lists:
        print(f"  {dim('Lists:')}  {gradient(', '.join(lists), (NEON_B, NEON_C))}")
    print(f"\n  {dim('Tip:')} {dim('add')} {cyan('--no-anim')} {dim('to any command to skip animations.')}\n")

# ── Guide ─────────────────────────────────────────────────────────────────────

def handle_guide(args, config, os_name):
    sys.path.insert(0, SCRIPT_DIR)
    import cmd_reference as ref

    alias = config.get("alias", "spider")
    banner(alias)

    _OS_COLOR = {"linux": green, "windows": blue, "mac": yellow}
    _OS_BADGE = {"linux": "LNX", "windows": "WIN", "mac": "MAC"}

    def guide_row(os_key, cmd_str, desc):
        color   = _OS_COLOR.get(os_key, cyan)
        bdg_txt = _OS_BADGE.get(os_key, "CMD")
        b       = bold(color(f"[{bdg_txt}]"))
        c       = bold(green(cmd_str))
        gap     = max(1, 44 - len(cmd_str))
        return f"  {b}  {c}{' ' * gap}{dim(desc)}"

    def print_category(cat_name, cmds, os_key):
        color   = _OS_COLOR.get(os_key, cyan)
        w       = 62
        label   = f"  {cat_name.upper()}"
        padding = " " * max(0, w - len(label))
        print()
        print(bold(color("  ┌" + "─" * w + "┐")))
        print(bold(color("  │")) + bold(white(label)) + padding + bold(color("│")))
        print(bold(color("  └" + "─" * w + "┘")))
        print()
        for cmd_str, desc in cmds:
            print(guide_row(os_key, cmd_str, desc))
        print()

    # ── OS picker ──────────────────────────────────────────────────────────────
    os_keys   = list(ref.OS_LABELS.keys())
    os_labels = [ref.OS_LABELS[k] for k in os_keys]

    print(f"  {bold(cyan('Command Reference'))}"
          f"  {dim('— real terminal commands, organized by category')}\n")
    print(f"  {bold(cyan('Select OS:'))}")
    for i, label in enumerate(os_labels, 1):
        print(f"    {bold(yellow(str(i)))}  {white(label)}")
    print()

    while True:
        try:
            raw = input(f"  {bold(cyan(ARROW))} ").strip()
            idx = int(raw) - 1
            if 0 <= idx < len(os_keys):
                sel_os = os_keys[idx]
                break
            print(error(f"  {CROSS} Enter 1–{len(os_keys)}."))
        except ValueError:
            print(error(f"  {CROSS} Please enter a number."))
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    cmd_map    = ref.ALL[sel_os]
    categories = list(cmd_map.keys())
    total_cmds = sum(len(v) for v in cmd_map.values())

    # ── Main loop: pick category → view → repeat ───────────────────────────────
    while True:
        color = _OS_COLOR.get(sel_os, cyan)
        print()
        print(f"  {bold(color(ref.OS_LABELS[sel_os]))}  "
              f"{dim(f'— {len(categories)} categories, {total_cmds} commands')}\n")

        cat_options = categories + ["All Categories"]
        for i, cat in enumerate(cat_options, 1):
            if cat == "All Categories":
                print(f"    {bold(yellow(str(i)))}  {bold(white(cat))}"
                      f"  {dim(f'({total_cmds} commands, paginated by section)')}")
            else:
                cnt = len(cmd_map[cat])
                print(f"    {bold(yellow(str(i)))}  {white(cat)}  {dim(f'({cnt})')}")
        print()

        while True:
            try:
                raw = input(f"  {bold(cyan(ARROW))} ").strip()
                idx = int(raw) - 1
                if 0 <= idx < len(cat_options):
                    sel_cat = cat_options[idx]
                    break
                print(error(f"  {CROSS} Enter 1–{len(cat_options)}."))
            except ValueError:
                print(error(f"  {CROSS} Please enter a number."))
            except KeyboardInterrupt:
                print(error("\n  Cancelled."))
                sys.exit(0)

        if sel_cat == "All Categories":
            all_cats = list(cmd_map.items())
            for i, (cat_name, cmds) in enumerate(all_cats):
                print_category(cat_name, cmds, sel_os)
                if i < len(all_cats) - 1:
                    try:
                        cont = input(
                            f"  {dim('── Press Enter for next section, q to stop ──')} "
                        ).strip().lower()
                        if cont == "q":
                            break
                    except KeyboardInterrupt:
                        break
        else:
            print_category(sel_cat, cmd_map[sel_cat], sel_os)

        if not ask_yes_no("View another category?"):
            break

    print(f"\n  {dim('Guide closed.')}  "
          f"{dim('Type')} {cyan(alias + ' guide')} {dim('to open again.')}\n")

# ── AI ────────────────────────────────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FREE_MODEL_FALLBACKS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "openai/gpt-oss-20b:free",
    "openai/gpt-oss-120b:free",
    "qwen/qwen3-coder:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]


def handle_ask(args, config, os_name):
    alias        = config.get("alias", "spider")
    apps         = sorted(config.get("apps", {}).keys())
    lists        = sorted(config.get("list_commands", {}).keys())

    # ── API key: use saved key or prompt and offer to save ────────────────────
    api_key        = config.get("openrouter_api_key", "").strip()
    prompted_key   = False

    if not api_key:
        print(f"  {dim('Get a free key at')} {cyan('openrouter.ai/keys')}\n")
        try:
            api_key = input(f"  {bold(cyan('Paste API key:'))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)
        if not api_key:
            print(error(f"  {CROSS} No key entered."))
            sys.exit(1)
        prompted_key = True
    print()

    question = " ".join(args).strip() if args else None
    if not question:
        try:
            question = input(f"\n  {bold(yellow(ARROW))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

    if not question:
        print(error(f"  {CROSS} No question provided."))
        sys.exit(1)

    configured_model = config.get("ai_model", FREE_MODEL_FALLBACKS[0])
    models_to_try    = [configured_model] + [m for m in FREE_MODEL_FALLBACKS if m != configured_model]

    system_prompt = (
        f'You are a professional terminal and developer workflow coach.\n'
        f'Help the user work like a professional developer in the terminal.\n'
        f'Current OS: {os_name}\n\n'
        f'The user also has a CLI helper called "{alias}" with commands:\n'
        f'  {alias} run <app>    — Launch an app  (apps: {", ".join(apps)})\n'
        f'  {alias} list <cat>   — System info     (cats: {", ".join(lists)})\n'
        f'  {alias} kill <proc>  — Kill a process\n'
        f'  {alias} check        — Audit installed dev tools\n'
        f'  {alias} learn        — Interactive learning paths\n'
        f'  {alias} guide        — Full command reference\n'
        f'  {alias} shell        — Interactive terminal mode\n\n'
        f'Answer rules:\n'
        f'- Answer ANY terminal, git, docker, SSH, or developer tool question\n'
        f'- Suggest a {alias} command only when directly relevant\n'
        f'- Reply in 3 parts: (1) one sentence explanation, '
        f'(2) exact terminal command on its own line starting with >, '
        f'(3) one short pro tip\n'
        f'- Keep total response under 100 words\n'
        f'- Always give real, runnable commands'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": question},
    ]

    print()
    answer = ""
    with Spinner("Asking AI"):
        last_err = ""
        for model in models_to_try:
            payload = json.dumps({
                "model":      model,
                "stream":     False,
                "max_tokens": 200,
                "messages":   messages,
            }).encode()

            req = urllib.request.Request(
                OPENROUTER_URL,
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://github.com/swapnil2919/cmd-helper",
                    "X-Title":       "CMD Helper",
                },
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    result = json.loads(resp.read())
                answer = result["choices"][0]["message"]["content"].strip()
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode()
                if exc.code in (404, 429):
                    last_err = f"{exc.code} on {model}"
                    continue
                print(error(f"\n  {CROSS} OpenRouter error {exc.code}: {body}"))
                sys.exit(1)
            except Exception as exc:
                print(error(f"\n  {CROSS} Request failed: {exc}"))
                sys.exit(1)
        else:
            print(error(f"\n  {CROSS} All free models unavailable ({last_err}). Try later."))
            sys.exit(1)

    # Display response in a box, line by line with a slight fade-in
    w = 56
    print(bold(yellow("  ┌" + "─" * w + "┐")))
    print(bold(yellow("  │")) + bold(white("  AI Guide")) + " " * (w - 10) + bold(yellow("│")))
    print(bold(yellow("  └" + "─" * w + "┘")))
    print()

    for line in answer.split("\n"):
        time.sleep(0.06)
        stripped = line.strip()
        if stripped.startswith(">"):
            print(f"  {bold(green(stripped))}")
        elif stripped:
            print(f"  {white(line)}")
        else:
            print()

    print()

    # ── "Run it?" — extract the > command and offer one-key execution ─────────
    if answer:
        suggestion = None
        for part in answer.split("\n"):
            s = part.strip()
            if s.startswith(">"):
                suggestion = s[1:].strip()
                break

        if suggestion:
            print(f"  {bold(cyan('Run it?'))}  "
                  f"{bold(green(suggestion))}  "
                  f"{dim('(Enter = run  ·  n = skip)')}")
            try:
                confirm = input(f"  {bold(cyan(ARROW))} ").strip().lower()
                if confirm in ("", "y", "yes"):
                    print()
                    try:
                        res = subprocess.run(suggestion, shell=True)
                        if res.returncode != 0:
                            print(dim(f"\n  (exit {res.returncode})"))
                    except Exception as exc:
                        print(error(f"  {CROSS} {exc}"))
                    print()
            except KeyboardInterrupt:
                print(error("\n  Cancelled.\n"))

    # ── Save key (once, first time only) ─────────────────────────────────────
    if prompted_key and answer:
        try:
            if ask_yes_no("Save API key to config so you don't retype it?"):
                config["openrouter_api_key"] = api_key
                save_config(config)
                print(f"\n  {green(CHECK)}  Key saved to config.json\n")
        except SystemExit:
            pass

    return answer

# ── Intro ─────────────────────────────────────────────────────────────────────

def handle_intro(args, config, os_name):
    # play the Matrix + spider splash, then return to the prompt
    alias = config.get("alias", "spider")
    matrix_intro()
    banner(alias)
    print(f"  {gradient('Welcome, ' + alias.capitalize() + '.', FLOW)}  "
          f"{dim('Run')} {cyan(alias + ' --help')} {dim('to begin.')}\n")

# ── Interactive REPL ──────────────────────────────────────────────────────────

def handle_repl(args, config, os_name):
    alias = config.get("alias", "spider")

    handlers = {
        "run":   handle_run,
        "list":  handle_list,
        "kill":  handle_kill,
        "open":  handle_open,
        "find":  handle_find,
        "check": handle_check,
        "learn": handle_learn,
        "guide": handle_guide,
        "ask":   handle_ask,
        "intro": handle_intro,
    }
    spider_cmds = list(handlers.keys()) + ["exit"]

    banner(alias)

    reveal(f"  {bold(gradient('Interactive Mode', FLOW))}  {dim(STAR + ' live terminal + AI')}", 0.0)
    reveal(f"  {dim(alias.capitalize() + ':')}  {gradient('  '.join(spider_cmds), (NEON_A, NEON_C))}", 0.02)
    reveal(f"  {dim('System:')}  {dim('any real command — ls, cd, git, ping, docker, ps ...')}", 0.02)
    reveal(f"  {dim('AI:')}      {bold(yellow(':'))} {dim('prefix — e.g.')} {cyan(': how do I zip a folder')}\n", 0.02)

    while True:
        # rebuild prompt each loop so cd updates it
        cwd      = os.getcwd()
        home_dir = os.path.expanduser("~")
        disp_cwd = ("~" + cwd[len(home_dir):]) if cwd.startswith(home_dir) else cwd
        prompt   = f"  {bold(cyan(alias))} {dim(disp_cwd)} {bold(cyan(ARROW))} "

        try:
            raw = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {green(CHECK)}  {dim('Goodbye!')}\n")
            break

        if not raw:
            continue
        if raw.lower() in ("exit", "quit", "q", "bye"):
            print(f"\n  {green(CHECK)}  {dim('Goodbye!')}\n")
            break

        # AI shortcut — ask AI, suggest command, offer one-key run
        if raw.startswith(":"):
            try:
                handle_ask(raw[1:].strip().split(), config, os_name)
            except SystemExit:
                pass
            continue

        parts   = raw.split()
        command = parts[0].lower()
        rest    = parts[1:]

        # Spider own commands — exact match only
        if command in handlers:
            try:
                handlers[command](rest, config, os_name)
            except SystemExit:
                pass
            continue

        # cd is a shell built-in — subprocess can't change the process directory
        if command == "cd":
            target = os.path.expanduser(" ".join(rest)) if rest else os.path.expanduser("~")
            try:
                os.chdir(target)
            except FileNotFoundError:
                print(error(f"  {CROSS} cd: no such directory: {target}\n"))
            except PermissionError:
                print(error(f"  {CROSS} cd: permission denied: {target}\n"))
            except Exception as exc:
                print(error(f"  {CROSS} cd: {exc}\n"))
            continue

        # Everything else → real system command
        print()
        try:
            result = subprocess.run(raw, shell=True)
            if result.returncode != 0:
                print(dim(f"  (exit {result.returncode})"))
        except Exception as exc:
            print(error(f"  {CROSS} {exc}"))
        print()

# ── Home / Shell dispatch ─────────────────────────────────────────────────────

def handle_home(args, config, os_name):
    home_screen(config, os_name)

def handle_shell(args, config, os_name):
    # live Matrix background behind the shell landing + prompt; plain REPL otherwise
    if ANIMATE and USE_COLOR:
        try:
            _animated_repl(config, os_name)
            return
        except Exception:
            try:
                sys.stdout.write("\033[0m\033[?25h\033[2J\033[H"); sys.stdout.flush()
            except Exception:
                pass
    handle_repl(args, config, os_name)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    config  = load_config()
    os_name = get_os()
    args    = sys.argv[1:]

    # global flag: strip it before dispatch so any command can disable animations
    if "--no-anim" in args:
        set_animation(False)
        args = [a for a in args if a != "--no-anim"]

    if not args or args[0] in ("--help", "-h", "help"):
        print_help(config)
        return

    command = args[0].lower()
    rest    = args[1:]

    handlers = {
        "run":   handle_run,
        "list":  handle_list,
        "kill":  handle_kill,
        "open":  handle_open,
        "find":  handle_find,
        "check": handle_check,
        "learn": handle_learn,
        "guide": handle_guide,
        "ask":   handle_ask,
        "shell": handle_shell,
        "repl":  handle_repl,
        "home":  handle_home,
        "intro": handle_intro,
    }

    if command in handlers:
        handlers[command](rest, config, os_name)
    else:
        suggestion = fuzzy_match(command, list(handlers.keys()))
        if suggestion:
            print(yellow(f"\n  {BULLET} '{command}' → did you mean '{bold(suggestion)}'? Running that..."))
            handlers[suggestion](rest, config, os_name)
        else:
            al = config.get("alias", "spider")
            print(error(f"\n  {CROSS} Unknown command: '{command}'"))
            print(dim(f"  Run '{al} --help' for usage.\n"))
            sys.exit(1)


if __name__ == "__main__":
    main()
