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
        ("LIST",  f"{alias} list",                  "Pick category interactively"),
        ("KILL",  f"{alias} kill <process>",        "Kill a running process"),
        ("OPEN",  f"{alias} open <path>",           "Open a file or folder"),
        ("FIND",  f"{alias} find <name>",           "Search files by name"),
        ("AI",    f"{alias} ask <question>",        "Ask AI for command help"),
        ("AI",    f"{alias}: <question>",           "AI shortcut (no 'ask' needed)"),
        ("SHELL", f"{alias} guide",                 "Full command guide"),
        ("SHELL", f"{alias} shell",                 "Interactive mode"),
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

def save_api_key(key):
    try:
        with open(CONFIG_PATH, "r") as f:
            cfg = json.load(f)
        cfg["openrouter_api_key"] = key
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as exc:
        print(error(f"  Could not save to config.json: {exc}"))
        return False


def handle_ask(args, config, os_name):
    api_key = os.environ.get("OPENROUTER_API_KEY") or config.get("openrouter_api_key", "")

    if not api_key:
        print(yellow(f"\n  {BULLET} No OpenRouter API key set."))
        print(f"  Get a free key at: {bold(cyan('https://openrouter.ai/keys'))}\n")
        try:
            api_key = input(f"  {bold(cyan('Paste key:'))} ").strip()
        except KeyboardInterrupt:
            print(error("\n  Cancelled."))
            sys.exit(0)

        if not api_key:
            print(error(f"  {CROSS} No key entered."))
            sys.exit(1)

        try:
            save = input(f"  {bold(cyan('Save to config.json?'))} {dim('(y/n)')} ").strip().lower()
        except KeyboardInterrupt:
            save = "n"

        if save in ("y", "yes"):
            if save_api_key(api_key):
                print(green(f"  {CHECK} Key saved.\n"))
            config["openrouter_api_key"] = api_key
        else:
            print(dim("  Using for this session only.\n"))

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

    alias        = config.get("alias", "spider")
    model        = config.get("ai_model", "google/gemma-4-31b-it:free")
    apps         = sorted(config.get("apps", {}).keys())
    lists        = sorted(config.get("list_commands", {}).keys())
    private_apps = sorted(config.get("private_flags", {}).keys())

    system_prompt = (
        f'You are a helpful assistant for a command-line tool called "{alias}".\n'
        f'Your only job is to help the user figure out which "{alias}" command to type.\n\n'
        f"Available commands:\n"
        f"  {alias} run <app>             — Launch an app\n"
        f"  {alias} run private <app>    — Launch in private/incognito mode\n"
        f"  {alias} list <category>      — Show system information\n"
        f"  {alias} kill <process>       — Kill a running process\n"
        f"  {alias} open <path>          — Open a file or folder\n"
        f"  {alias} find <name>          — Search files by name\n"
        f"  {alias} guide               — Show full command guide\n\n"
        f"Configured apps : {', '.join(apps)}\n"
        f"Private support : {', '.join(private_apps)}\n"
        f"List categories : {', '.join(lists)}\n"
        f"Current OS      : {os_name}\n\n"
        f"Rules:\n"
        f"- Reply in 3 parts: (1) one sentence explanation, "
        f"(2) exact command on its own line prefixed with >, "
        f"(3) short optional tip.\n"
        f"- Keep total response under 80 words.\n"
        f"- Do not make up apps or categories not listed above.\n"
        f"- Format the exact command like:  > {alias} run chrome"
    )

    payload = json.dumps({
        "model":      model,
        "stream":     False,
        "max_tokens": 200,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": question},
        ],
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

    print()
    answer = ""
    with Spinner("Asking AI"):
        try:
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            answer = result["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            print(error(f"\n  {CROSS} OpenRouter error {exc.code}: {body}"))
            sys.exit(1)
        except Exception as exc:
            print(error(f"\n  {CROSS} Request failed: {exc}"))
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

# ── Shell ─────────────────────────────────────────────────────────────────────

def handle_shell(args, config, os_name):
    alias = config.get("alias", "spider")

    handlers = {
        "run":   handle_run,
        "list":  handle_list,
        "kill":  handle_kill,
        "open":  handle_open,
        "find":  handle_find,
        "guide": handle_guide,
        "ask":   handle_ask,
    }

    banner(alias)

    print(f"  {bold(cyan('Interactive Mode'))}  "
          f"{dim('— type a command, or')} {bold(red('exit'))} {dim('to quit.')}")
    print(f"  {dim('Tip: prefix with')} {cyan(':')}"
          f" {dim('to ask AI  e.g.')} {cyan(': open chrome in private')}\n")

    prompt = f"  {bold(cyan(alias))} {bold(cyan(ARROW))} "

    while True:
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

        if raw.startswith(":"):
            try:
                handle_ask(raw[1:].strip().split(), config, os_name)
            except SystemExit:
                pass
            continue

        parts   = raw.split()
        command = parts[0].lower()
        rest    = parts[1:]

        if command in handlers:
            try:
                handlers[command](rest, config, os_name)
            except SystemExit:
                pass
        else:
            suggestion = fuzzy_match(command, list(handlers.keys()))
            if suggestion:
                print(yellow(f"\n  {BULLET} '{command}' → did you mean '{bold(suggestion)}'? Running that..."))
                try:
                    handlers[suggestion](rest, config, os_name)
                except SystemExit:
                    pass
            else:
                avail = list(handlers.keys()) + ["exit"]
                print(error(f"\n  {CROSS} Unknown: '{command}'"))
                print(dim(f"  Try: {', '.join(avail)}\n"))

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
