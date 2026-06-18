#!/usr/bin/env python3
"""
Creates a desktop shortcut for Spider CMD Helper.
Works on Linux, Mac, and Windows — run once, no extra packages needed.

    python3 create_shortcut.py
"""

import os
import sys
import json
import stat
import platform
import subprocess

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
MAIN_PATH   = os.path.join(SCRIPT_DIR, "main.py")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
OS          = platform.system().lower()

# ── colors ──────────────────────────────────────────────────────────────────

USE_COLOR = OS != "windows" or os.environ.get("TERM") == "xterm"

def _c(t, code): return f"\033[{code}m{t}\033[0m" if USE_COLOR else t
def bold(t):   return _c(t, "1")
def cyan(t):   return _c(t, "96")
def green(t):  return _c(t, "92")
def yellow(t): return _c(t, "93")
def red(t):    return _c(t, "91")

def tick(msg):  print(green(f"  [OK]  {msg}"))
def info(msg):  print(cyan( f"  [>>]  {msg}"))
def warn(msg):  print(yellow(f"  [!!]  {msg}"))
def fail(msg):  print(red(  f"  [XX]  {msg}")); sys.exit(1)


# ── helpers ──────────────────────────────────────────────────────────────────

def load_alias():
    if not os.path.exists(CONFIG_PATH):
        fail("config.json not found — run this from the cmd-script folder.")
    with open(CONFIG_PATH) as f:
        return json.load(f).get("alias", "spider")


def make_exec(path):
    st = os.stat(path)
    os.chmod(path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def write_file(path, content, executable=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    if executable:
        make_exec(path)


# ── Linux ─────────────────────────────────────────────────────────────────────

def trust_desktop_file(path):
    """Mark a .desktop file as trusted so GNOME launches it instead of opening it as text."""
    # Method 1: gio set (GNOME 3.x, Ubuntu 18.04+)
    try:
        result = subprocess.run(
            ["gio", "set", path, "metadata::trusted", "true"],
            capture_output=True, timeout=10,
        )
        if result.returncode == 0:
            return "gio"
    except FileNotFoundError:
        pass

    # Method 2: dbus-send to Nautilus (older GNOME)
    try:
        result = subprocess.run(
            ["dbus-send", "--session", "--print-reply",
             "--dest=org.gnome.Shell",
             "/org/gnome/Shell",
             "org.gnome.Shell.Eval",
             f"string:trustedFiles.push('{path}')"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return "dbus"
    except FileNotFoundError:
        pass

    return None


def create_linux(alias):
    entry = "\n".join([
        "[Desktop Entry]",
        "Version=1.0",
        "Type=Application",
        f"Name={alias.capitalize()} CMD Helper",
        "GenericName=CMD Helper",
        "Comment=Smart command-line helper — double-click to open",
        f'Exec=python3 "{MAIN_PATH}" shell',
        "Icon=utilities-terminal",
        "Terminal=true",
        "StartupNotify=false",
        "Categories=Utility;System;",
        "",
    ])

    # app menu entry
    menu_dir  = os.path.expanduser("~/.local/share/applications")
    menu_file = os.path.join(menu_dir, f"{alias}.desktop")
    write_file(menu_file, entry, executable=True)
    tick(f"App menu  →  {menu_file}")

    # desktop icon
    desk_dir  = os.path.expanduser("~/Desktop")
    desk_file = os.path.join(desk_dir, f"{alias}.desktop")
    os.makedirs(desk_dir, exist_ok=True)
    with open(desk_file, "w") as f:
        f.write(entry)
    make_exec(desk_file)
    tick(f"Desktop   →  {desk_file}")

    # mark both files as trusted so GNOME launches them instead of opening as text
    for path in (menu_file, desk_file):
        method = trust_desktop_file(path)
        if method:
            tick(f"Trusted   →  {os.path.basename(path)}  (via {method})")
        else:
            warn(f"Could not auto-trust {os.path.basename(path)} — see manual step below.")

    # final check: if gio is available, confirm the trust attribute is set
    try:
        result = subprocess.run(
            ["gio", "info", "-a", "metadata::trusted", desk_file],
            capture_output=True, timeout=5,
        )
        if b"trusted: true" in result.stdout:
            info("File is trusted — double-click to launch immediately.")
        else:
            warn("Auto-trust may not have taken effect yet.")
            warn("If double-click still opens as text, run:")
            print(f"\n      gio set \"{desk_file}\" metadata::trusted true\n")
    except FileNotFoundError:
        warn("'gio' command not found — if double-click opens as text, run:")
        print(f"\n      chmod +x \"{desk_file}\" && gio set \"{desk_file}\" metadata::trusted true\n")


# ── macOS ─────────────────────────────────────────────────────────────────────

def create_mac(alias):
    name     = f"{alias.capitalize()} CMD Helper"
    desk_dir = os.path.expanduser("~/Desktop")

    # --- Option A: minimal .app bundle (shows up as a real app with icon) ---
    app_path   = os.path.join(desk_dir, f"{name}.app")
    macos_dir  = os.path.join(app_path, "Contents", "MacOS")
    exec_path  = os.path.join(macos_dir, "launcher")
    plist_path = os.path.join(app_path, "Contents", "Info.plist")

    os.makedirs(macos_dir, exist_ok=True)

    write_file(exec_path, (
        "#!/usr/bin/env bash\n"
        f'python3 "{MAIN_PATH}" shell\n'
    ), executable=True)

    write_file(plist_path, f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>         <string>{name}</string>
  <key>CFBundleExecutable</key>   <string>launcher</string>
  <key>CFBundleIdentifier</key>   <string>com.cmdhelper.{alias}</string>
  <key>CFBundleVersion</key>      <string>1.0</string>
  <key>CFBundlePackageType</key>  <string>APPL</string>
</dict>
</plist>
""")
    tick(f"App       →  {app_path}")

    # --- Option B: .command file as a plain fallback ---
    cmd_file = os.path.join(desk_dir, f"{name}.command")
    write_file(cmd_file, (
        "#!/usr/bin/env bash\n"
        f'python3 "{MAIN_PATH}" shell\n'
    ), executable=True)
    tick(f"Fallback  →  {cmd_file}  (.command opens in Terminal directly)")

    warn("First launch: right-click the .app → Open → Open (bypasses Gatekeeper once).")
    info("After that, double-click freely.")


# ── Windows ───────────────────────────────────────────────────────────────────

def create_windows(alias):
    name      = f"{alias.capitalize()} CMD Helper"
    desk_dir  = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desk_dir, exist_ok=True)

    lnk_path = os.path.join(desk_dir, f"{name}.lnk")

    # PowerShell creates a proper Windows shortcut (.lnk) with a terminal icon
    ps_cmd = (
        f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{lnk_path}');"
        f"$s.TargetPath='python';"
        f"$s.Arguments='\"{MAIN_PATH}\" shell';"
        f"$s.WorkingDirectory='{SCRIPT_DIR}';"
        f"$s.IconLocation='shell32.dll,21';"
        f"$s.Description='{name}';"
        f"$s.Save()"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, timeout=15,
        )
        if result.returncode == 0:
            tick(f"Shortcut  →  {lnk_path}")
            return
        warn(f"PowerShell shortcut failed (code {result.returncode}), falling back to .bat")
    except FileNotFoundError:
        warn("PowerShell not found, falling back to .bat")
    except Exception as exc:
        warn(f"PowerShell error: {exc}, falling back to .bat")

    # Fallback: plain .bat file
    bat_path = os.path.join(desk_dir, f"{name}.bat")
    write_file(bat_path, (
        "@echo off\n"
        f'python "{MAIN_PATH}" shell\n'
        "pause\n"
    ))
    tick(f"Batch     →  {bat_path}")
    info("Double-click the .bat to launch. The window stays open until you type 'exit'.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(MAIN_PATH):
        fail("main.py not found — run this from the cmd-script folder.")

    alias = load_alias()

    print(bold(cyan(f"\n  Creating desktop shortcut for '{alias}' on {OS}...\n")))

    if OS == "linux":
        create_linux(alias)
    elif OS == "darwin":
        create_mac(alias)
    elif OS == "windows":
        create_windows(alias)
    else:
        fail(f"Unsupported OS: '{OS}'  (expected linux / darwin / windows)")

    print(green(f"\n  Done! Double-click the shortcut to launch {alias} CMD Helper.\n"))


if __name__ == "__main__":
    main()
