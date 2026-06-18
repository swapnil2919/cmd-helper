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

# ── Colors ────────────────────────────────────────────────────────────────────

USE_COLOR = not IS_WIN or os.environ.get("TERM") == "xterm"

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

# ── Glyphs (ASCII fallback on old Windows terminals) ──────────────────────────

ARROW  = "❯" if not IS_WIN else ">"
BULLET = "▸" if not IS_WIN else "*"
CHECK  = "✔" if not IS_WIN else "+"
CROSS  = "✘" if not IS_WIN else "x"
DOT    = "·" if not IS_WIN else "."

# ── Banner ────────────────────────────────────────────────────────────────────

def banner(alias):
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

# ── Section header ─────────────────────────────────────────────────────────────

def section(num, title, color_fn=yellow):
    label = f"  {num}. {title}  "
    line  = "─" * max(0, 60 - len(label))
    print(bold(color_fn(label + line)))

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

_FRAMES = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"] if not IS_WIN else ["|","/","-","\\"]

class Spinner:
    def __init__(self, msg="Working"):
        self.msg   = msg
        self._stop = threading.Event()
        self._t    = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        for f in itertools.cycle(_FRAMES):
            if self._stop.is_set():
                break
            print(f"\r  {bold(cyan(f))}  {dim(self.msg + '...')}", end="", flush=True)
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

    print(f"  {dim('Usage:')}  {bold(cyan(alias))} {dim('<command> [options]')}\n")

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
    ]

    for bdg, cmd, desc in rows:
        print(cmd_row(bdg, cmd, desc))

    print()
    if apps:
        print(f"  {dim('Apps:')}   {cyan(', '.join(apps))}")
    if lists:
        print(f"  {dim('Lists:')}  {cyan(', '.join(lists))}")
    print()

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

# ── Shell ─────────────────────────────────────────────────────────────────────

def handle_shell(args, config, os_name):
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
    }
    spider_cmds = list(handlers.keys()) + ["exit"]

    banner(alias)

    print(f"  {bold(cyan('Interactive Mode'))}")
    print(f"  {dim('Spider:')}  {cyan('  '.join(spider_cmds))}")
    print(f"  {dim('System:')}  {dim('any real command — ls, cd, git, ping, docker, ps ...')}")
    print(f"  {dim('AI:')}      {cyan(':')} {dim('prefix — e.g.')} {cyan(': how do I zip a folder')}\n")

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

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    config  = load_config()
    os_name = get_os()
    args    = sys.argv[1:]

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
