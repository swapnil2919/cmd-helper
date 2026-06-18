#!/usr/bin/env python3
import sys
import os
import json
import platform
import subprocess
import urllib.request
import urllib.error
import difflib

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(error("config.json not found next to main.py"))
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def get_os():
    system = platform.system().lower()
    if system == "darwin":
        return "mac"
    elif system == "windows":
        return "windows"
    return "linux"


# ---- Colors (ANSI, skipped on older Windows) ----

USE_COLOR = platform.system() != "Windows" or os.environ.get("TERM") == "xterm"

def _c(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

def bold(t):    return _c(t, "1")
def cyan(t):    return _c(t, "96")
def green(t):   return _c(t, "92")
def yellow(t):  return _c(t, "93")
def error(t):   return _c(t, "91")


# ---- Fuzzy match ----

def fuzzy_match(query, choices, cutoff=0.55):
    matches = difflib.get_close_matches(query, choices, n=1, cutoff=cutoff)
    return matches[0] if matches else None


# ---- Interactive helpers ----

def pick_from_list(items, prompt="Select an option"):
    print(cyan(f"\n{prompt}:"))
    for i, item in enumerate(items, 1):
        print(f"  {yellow(str(i))}. {item}")
    print()
    while True:
        try:
            raw = input(bold("Enter number: ")).strip()
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(error("Invalid choice, try again."))
        except ValueError:
            print(error("Please enter a number."))
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)


def ask_yes_no(prompt):
    while True:
        try:
            raw = input(bold(f"{prompt} (y/n): ")).strip().lower()
            if raw in ("y", "yes"):
                return True
            if raw in ("n", "no"):
                return False
            print(error("Please enter y or n."))
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)


# ---- Command runner ----

def run_detached(cmd):
    try:
        if platform.system() == "Windows":
            subprocess.Popen(cmd, shell=True, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(error(f"Command not found: {cmd[0]}"))
        sys.exit(1)


def run_inline(cmd):
    try:
        subprocess.run(cmd)
    except FileNotFoundError:
        print(error(f"Command not found: {cmd[0]}"))
        sys.exit(1)


# ---- Handlers ----

def handle_run(args, config, os_name):
    apps = config.get("apps", {})
    private_flags = config.get("private_flags", {})

    private = False
    remaining = list(args)

    if remaining and remaining[0].lower() == "private":
        private = True
        remaining.pop(0)

    app_name = remaining[0].lower() if remaining else None

    if not app_name:
        choices = list(apps.keys())
        if not choices:
            print(error("No apps configured in config.json"))
            sys.exit(1)
        app_name = pick_from_list(choices, "Select an app to launch")

    if app_name not in apps:
        suggestion = fuzzy_match(app_name, list(apps.keys()))
        if suggestion:
            print(yellow(f"  '{app_name}' → did you mean '{suggestion}'? Running that..."))
            app_name = suggestion
        else:
            print(error(f"Unknown app: '{app_name}'"))
            print(f"Available: {', '.join(apps.keys())}")
            sys.exit(1)

    if not private and app_name in private_flags:
        private = ask_yes_no(f"Open {app_name} in private/incognito mode?")

    cmd = apps[app_name].get(os_name)
    if not cmd:
        print(error(f"No command configured for '{app_name}' on {os_name}"))
        sys.exit(1)

    cmd = list(cmd)

    if private and app_name in private_flags:
        flag = private_flags[app_name].get(os_name)
        if flag:
            cmd.append(flag)

    mode = " (private)" if private else ""
    print(green(f"Launching {app_name}{mode}..."))
    run_detached(cmd)


def handle_list(args, config, os_name):
    list_commands = config.get("list_commands", {})

    category = args[0].lower() if args else None

    if not category:
        choices = list(list_commands.keys())
        if not choices:
            print(error("No list commands configured in config.json"))
            sys.exit(1)
        category = pick_from_list(choices, "What do you want to list?")

    if category not in list_commands:
        suggestion = fuzzy_match(category, list(list_commands.keys()))
        if suggestion:
            print(yellow(f"  '{category}' → did you mean '{suggestion}'? Running that..."))
            category = suggestion
        else:
            print(error(f"Unknown category: '{category}'"))
            print(f"Available: {', '.join(list_commands.keys())}")
            sys.exit(1)

    cmd = list_commands[category].get(os_name)
    if not cmd:
        print(error(f"No command for '{category}' on {os_name}"))
        sys.exit(1)

    print(cyan(f"\n--- {category.upper()} ---\n"))
    run_inline(list(cmd))


def handle_kill(args, config, os_name):
    process_name = args[0] if args else None

    if not process_name:
        try:
            process_name = input(bold("Enter process name to kill: ")).strip()
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)

    if not process_name:
        print(error("No process name provided."))
        sys.exit(1)

    if not ask_yes_no(f"Kill '{process_name}'?"):
        print(yellow("Cancelled."))
        return

    if os_name == "windows":
        cmd = ["taskkill", "/IM", f"{process_name}.exe", "/F"]
    else:
        cmd = ["pkill", "-f", process_name]

    print(yellow(f"Killing {process_name}..."))
    run_inline(cmd)


def handle_open(args, config, os_name):
    path = " ".join(args) if args else None

    if not path:
        try:
            path = input(bold("Enter file or folder path to open: ")).strip()
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)

    if not path:
        print(error("No path provided."))
        sys.exit(1)

    if os_name == "mac":
        cmd = ["open", path]
    elif os_name == "windows":
        cmd = ["explorer", path]
    else:
        cmd = ["xdg-open", path]

    print(green(f"Opening {path}..."))
    run_detached(cmd)


def handle_find(args, config, os_name):
    query = " ".join(args) if args else None

    if not query:
        try:
            query = input(bold("Enter filename or pattern to search: ")).strip()
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)

    if not query:
        print(error("No search query provided."))
        sys.exit(1)

    print(cyan(f"\n--- Searching for '{query}' ---\n"))

    if os_name == "windows":
        run_inline(["cmd", "/c", "dir", "/s", "/b", f"*{query}*"])
    else:
        run_inline(["find", ".", "-iname", f"*{query}*", "-not", "-path", "*/.git/*"])


# ---- Help ----

def print_help(config):
    alias = config.get("alias", "smart")
    apps = list(config.get("apps", {}).keys())
    lists = list(config.get("list_commands", {}).keys())

    print(bold(cyan("\n=== CMD Helper ===")))
    print(f"\n  {cyan('USAGE:')} {bold(alias)} <command> [options]\n")

    print(yellow("  COMMANDS:"))
    print(f"    {bold(alias + ' run <app>')}              Launch an app")
    print(f"    {bold(alias + ' run private <app>')}      Launch in private/incognito mode")
    print(f"    {bold(alias + ' run')}                    Pick app interactively")
    print(f"    {bold(alias + ' list <category>')}        Show system info")
    print(f"    {bold(alias + ' list')}                   Pick category interactively")
    print(f"    {bold(alias + ' kill <process>')}         Kill a running process")
    print(f"    {bold(alias + ' open <path>')}            Open a file or folder")
    print(f"    {bold(alias + ' find <name>')}            Find files by name")
    print(f"    {bold(alias + ' guide')}                  Show full interactive guide")
    print(f"    {bold(alias + ' ask <question>')}         Ask AI for command help")

    if apps:
        print(yellow("\n  CONFIGURED APPS:"))
        print(f"    {', '.join(apps)}")

    if lists:
        print(yellow("\n  LIST CATEGORIES:"))
        print(f"    {', '.join(lists)}")

    print(f"\n  Edit {cyan('config.json')} to add more apps and commands.\n")


# ---- Guide ----

def handle_guide(args, config, os_name):
    alias = config.get("alias", "smart")
    apps = config.get("apps", {})
    lists = config.get("list_commands", {})
    private_flags = config.get("private_flags", {})

    divider = cyan("  " + "─" * 56)

    print(bold(cyan("\n╔══════════════════════════════════════════════════════╗")))
    print(bold(cyan("║           CMD Helper — Interactive Guide             ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════════╝")))
    print(f"\n  Your alias is {bold(green(alias))}. Type {bold(green(alias + ' <command>'))} to use it.\n")

    # ── RUN ──
    print(divider)
    print(bold(yellow("  1. LAUNCH APPS  —  smart run")))
    print(divider)
    print(f"  Open any app by name:\n")
    print(f"    {bold(green(alias + ' run chrome'))}          → opens Chrome")
    print(f"    {bold(green(alias + ' run vscode'))}          → opens VS Code")
    print(f"    {bold(green(alias + ' run'))}                 → shows picker, you choose\n")
    print(f"  Private / incognito mode (for supported browsers):\n")
    print(f"    {bold(green(alias + ' run private chrome'))}  → Chrome incognito")
    print(f"    {bold(green(alias + ' run private firefox'))} → Firefox private window\n")

    if apps:
        browser_apps = [a for a in apps if a in private_flags]
        other_apps   = [a for a in apps if a not in private_flags]
        print(f"  {cyan('Configured apps:')}  {', '.join(sorted(apps.keys()))}")
        if browser_apps:
            print(f"  {cyan('Private support:')}  {', '.join(sorted(browser_apps))}")
    print()

    # ── LIST ──
    print(divider)
    print(bold(yellow("  2. SYSTEM INFO  —  smart list")))
    print(divider)
    print(f"  Show live system information:\n")
    print(f"    {bold(green(alias + ' list processes'))}      → running processes")
    print(f"    {bold(green(alias + ' list memory'))}         → RAM usage")
    print(f"    {bold(green(alias + ' list cpu'))}            → CPU load")
    print(f"    {bold(green(alias + ' list network'))}        → network ports")
    print(f"    {bold(green(alias + ' list disks'))}          → disk space")
    print(f"    {bold(green(alias + ' list ports'))}          → listening ports")
    print(f"    {bold(green(alias + ' list files'))}          → files in current folder")
    print(f"    {bold(green(alias + ' list users'))}          → who is logged in")
    print(f"    {bold(green(alias + ' list'))}                → shows picker, you choose\n")
    if lists:
        print(f"  {cyan('All categories:')}  {', '.join(sorted(lists.keys()))}")
    print()

    # ── KILL ──
    print(divider)
    print(bold(yellow("  3. KILL PROCESS  —  smart kill")))
    print(divider)
    print(f"  Stop any running program by name:\n")
    print(f"    {bold(green(alias + ' kill chrome'))}         → force-close Chrome")
    print(f"    {bold(green(alias + ' kill python'))}         → kill Python process")
    print(f"    {bold(green(alias + ' kill'))}                → prompts you for a name")
    print(f"\n  {yellow('Tip:')} It asks for confirmation before killing.\n")

    # ── OPEN ──
    print(divider)
    print(bold(yellow("  4. OPEN FILE / FOLDER  —  smart open")))
    print(divider)
    print(f"  Open any path in your file manager:\n")
    print(f"    {bold(green(alias + ' open /home/user/docs'))}  → opens folder")
    print(f"    {bold(green(alias + ' open report.pdf'))}       → opens the file")
    print(f"    {bold(green(alias + ' open .'))}                → opens current folder")
    print(f"    {bold(green(alias + ' open'))}                  → prompts you for a path\n")

    # ── FIND ──
    print(divider)
    print(bold(yellow("  5. FIND FILES  —  smart find")))
    print(divider)
    print(f"  Search for files by name pattern:\n")
    print(f"    {bold(green(alias + ' find report.pdf'))}      → exact filename")
    print(f"    {bold(green(alias + ' find .log'))}            → any file ending in .log")
    print(f"    {bold(green(alias + ' find notes'))}           → any file with 'notes' in name")
    print(f"    {bold(green(alias + ' find'))}                 → prompts you for a pattern\n")

    # ── TIPS ──
    print(divider)
    print(bold(yellow("  6. TIPS & CUSTOMISATION")))
    print(divider)
    print(f"  • Edit {cyan('config.json')} to add your own apps and list categories.")
    alias_key = '"alias"'
    print(f"  • Change {cyan(alias_key)} in config.json to rename the command.")
    print(f"  • Run {bold(green('python3 setup.py'))} once after changing the alias.")
    print(f"  • Use {bold(green(alias + ' --help'))} for a quick reference at any time.")
    print(f"  • Works on {cyan('Linux')}, {cyan('Mac')}, and {cyan('Windows')} — same commands everywhere.\n")

    # ── ASK AI ──
    print(divider)
    print(bold(yellow("  7. ASK AI  —  smart ask")))
    print(divider)
    print(f"  Describe what you want in plain English — AI tells you the command:\n")
    print(f"    {bold(green(alias + ' ask I want to open a file and edit the text'))}")
    print(f"    {bold(green(alias + ' ask how do I see what is using my RAM'))}")
    print(f"    {bold(green(alias + ' ask open chrome in private mode'))}")
    print(f"    {bold(green(alias + ' ask'))}                  → prompts you to type your question\n")
    print(f"  {yellow('Requires:')} {cyan('OPENROUTER_API_KEY')} env var  (free key at openrouter.ai/keys)\n")

    print(bold(cyan("  ─────────────────────────────────────────────────────")))
    print(f"  Detected OS: {bold(green(os_name.upper()))}")
    print(bold(cyan("  ─────────────────────────────────────────────────────\n")))


# ---- AI Ask ----

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
        print(yellow("\n  No OpenRouter API key set."))
        print(f"  Get a free key at: {bold(cyan('https://openrouter.ai/keys'))}\n")
        try:
            api_key = input(bold("  Paste your key here: ")).strip()
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)

        if not api_key:
            print(error("  No key entered. Exiting."))
            sys.exit(1)

        try:
            save = input(bold("  Save this key to config.json for next time? (y/n): ")).strip().lower()
        except KeyboardInterrupt:
            save = "n"

        if save in ("y", "yes"):
            if save_api_key(api_key):
                print(green("  Key saved to config.json.\n"))
            config["openrouter_api_key"] = api_key
        else:
            print(cyan("  Using key for this session only.\n"))

    question = " ".join(args).strip() if args else None
    if not question:
        try:
            question = input(bold("What do you want to do? ")).strip()
        except KeyboardInterrupt:
            print(error("\nCancelled."))
            sys.exit(0)

    if not question:
        print(error("No question provided."))
        sys.exit(1)

    alias        = config.get("alias", "smart")
    model        = config.get("ai_model", "meta-llama/llama-3.1-8b-instruct:free")
    apps         = sorted(config.get("apps", {}).keys())
    lists        = sorted(config.get("list_commands", {}).keys())
    private_apps = sorted(config.get("private_flags", {}).keys())

    system_prompt = f"""You are a helpful assistant for a command-line tool called "{alias}".
Your only job is to help the user figure out which "{alias}" command to type to accomplish their goal.

Available commands:
  {alias} run <app>              — Launch an app (opens detached)
  {alias} run private <app>     — Launch app in private/incognito mode
  {alias} run                   — Pick an app interactively from a list
  {alias} list <category>       — Show live system information
  {alias} list                  — Pick a category interactively
  {alias} kill <process>        — Kill a running process by name
  {alias} open <path>           — Open a file or folder in the default app / file manager
  {alias} find <name>           — Search for files by name pattern
  {alias} guide                 — Show the full command guide
  {alias} --help                — Quick usage reference

Configured apps : {', '.join(apps)}
Private support : {', '.join(private_apps)}
List categories : {', '.join(lists)}
Current OS      : {os_name}

Rules:
- Reply in 3 parts: (1) one-sentence explanation, (2) the exact command on its own line prefixed with ">", (3) a short optional tip.
- Keep the total response under 80 words.
- If the goal cannot be done with the available commands, say so briefly and suggest the closest alternative.
- Do not make up apps or categories not listed above.
- Format the exact command like this:  > {alias} run chrome"""

    payload = json.dumps({
        "model": model,
        "stream": True,
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

    print(cyan("\n  Asking AI...\n"))
    print(f"  {bold('AI Guide:')}\n")

    try:
        with urllib.request.urlopen(req) as resp:
            pending = ""
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    token = chunk["choices"][0]["delta"].get("content", "")
                except (KeyError, json.JSONDecodeError):
                    continue

                pending += token
                # Print complete lines so we can colour ">" lines
                while "\n" in pending:
                    line_out, pending = pending.split("\n", 1)
                    if line_out.strip().startswith(">"):
                        print(f"  {bold(green(line_out))}")
                    else:
                        print(f"  {line_out}")

            # flush any remaining partial line
            if pending.strip():
                if pending.strip().startswith(">"):
                    print(f"  {bold(green(pending))}")
                else:
                    print(f"  {pending}")

        print()

    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        print(error(f"\n  OpenRouter error {exc.code}: {body}"))
        sys.exit(1)
    except Exception as exc:
        print(error(f"\n  Request failed: {exc}"))
        sys.exit(1)


# ---- Interactive shell ----

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

    print_help(config)
    print(cyan(f"  Interactive mode — type commands below, or 'exit' to quit.\n"))

    while True:
        try:
            raw = input(bold(f"  {alias}> ")).strip()
        except (KeyboardInterrupt, EOFError):
            print(green("\n  Goodbye!"))
            break

        if not raw:
            continue

        if raw.lower() in ("exit", "quit", "q", "bye"):
            print(green("  Goodbye!"))
            break

        # support "spider: question" style inside the shell too
        if raw.startswith(":"):
            rest = raw[1:].strip().split()
            try:
                handle_ask(rest, config, os_name)
            except SystemExit:
                pass
            continue

        parts = raw.split()
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
                print(yellow(f"  '{command}' → did you mean '{suggestion}'? Running that..."))
                try:
                    handlers[suggestion](rest, config, os_name)
                except SystemExit:
                    pass
            else:
                print(error(f"  Unknown: '{command}'  —  try: {', '.join(handlers)} or exit"))


# ---- Entry point ----

def main():
    config = load_config()
    os_name = get_os()
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h", "help"):
        print_help(config)
        return

    command = args[0].lower()
    rest = args[1:]

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
            print(yellow(f"  '{command}' → did you mean '{suggestion}'? Running that..."))
            handlers[suggestion](rest, config, os_name)
        else:
            print(error(f"Unknown command: '{command}'"))
            print(f"Run '{config.get('alias', 'spider')} --help' for usage.")
            sys.exit(1)


if __name__ == "__main__":
    main()
