#!/usr/bin/env python3
import sys
import os
import json
import platform
import subprocess

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


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

    if apps:
        print(yellow("\n  CONFIGURED APPS:"))
        print(f"    {', '.join(apps)}")

    if lists:
        print(yellow("\n  LIST CATEGORIES:"))
        print(f"    {', '.join(lists)}")

    print(f"\n  Edit {cyan('config.json')} to add more apps and commands.\n")


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
        "run":  handle_run,
        "list": handle_list,
        "kill": handle_kill,
        "open": handle_open,
        "find": handle_find,
    }

    if command in handlers:
        handlers[command](rest, config, os_name)
    else:
        print(error(f"Unknown command: '{command}'"))
        print(f"Run '{config.get('alias', 'smart')} --help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
