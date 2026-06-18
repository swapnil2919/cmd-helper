#!/usr/bin/env python3
"""
Run this once to install your alias to the system PATH.
  Linux/Mac : python3 setup.py
  Windows   : python setup.py
"""
import os
import sys
import json
import platform
import stat

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
MAIN_PATH   = os.path.join(SCRIPT_DIR, "main.py")


def load_alias():
    if not os.path.exists(CONFIG_PATH):
        print("ERROR: config.json not found.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    alias = cfg.get("alias", "").strip()
    if not alias:
        print("ERROR: 'alias' is empty in config.json. Set it to your preferred command name.")
        sys.exit(1)
    return alias


def setup_linux_mac(alias):
    local_bin = os.path.expanduser("~/.local/bin")
    os.makedirs(local_bin, exist_ok=True)

    script_path = os.path.join(local_bin, alias)

    content = f"""#!/usr/bin/env bash
python3 "{MAIN_PATH}" "$@"
"""
    with open(script_path, "w") as f:
        f.write(content)

    # make executable
    st = os.stat(script_path)
    os.chmod(script_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Installed '{alias}' → {script_path}")

    # create "alias:" shortcut — typing "spider: ..." routes straight to AI
    ai_script_path = os.path.join(local_bin, alias + ":")
    ai_content = f"""#!/usr/bin/env bash
python3 "{MAIN_PATH}" "ask" "$@"
"""
    with open(ai_script_path, "w") as f:
        f.write(ai_content)
    st2 = os.stat(ai_script_path)
    os.chmod(ai_script_path, st2.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print(f"Installed '{alias}:' → {ai_script_path}  (AI shortcut)")

    path_env = os.environ.get("PATH", "")
    if local_bin not in path_env:
        shell = os.environ.get("SHELL", "bash")
        rc = "~/.zshrc" if "zsh" in shell else "~/.bashrc"
        print(f"\n~/.local/bin is not in your PATH.")
        print(f"Add this line to {rc}:\n")
        print(f'  export PATH="$HOME/.local/bin:$PATH"\n')
        print(f"Then reload it:\n  source {rc}\n")
        print(f"After that, run:  {alias} --help")
    else:
        print(f"\nDone! Try it now:\n  {alias} --help")


def setup_windows(alias):
    install_dir = os.path.join(os.environ.get("APPDATA", "C:\\Users\\Public"), "cmd-helper")
    os.makedirs(install_dir, exist_ok=True)

    bat_path = os.path.join(install_dir, f"{alias}.bat")
    content = f'@echo off\npython "{MAIN_PATH}" %*\n'

    with open(bat_path, "w") as f:
        f.write(content)

    print(f"Created {bat_path}")

    current_path = os.environ.get("PATH", "")
    if install_dir.lower() not in current_path.lower():
        ret = os.system(f'setx PATH "%PATH%;{install_dir}"')
        if ret == 0:
            print(f"Added {install_dir} to your PATH.")
        else:
            print(f"\nCould not update PATH automatically.")
            print(f"Add this manually to your system PATH:\n  {install_dir}")
        print(f"\nRestart your terminal, then run:  {alias} --help")
    else:
        print(f"\nDone! Try it now:\n  {alias} --help")


def create_desktop_shortcut_linux(alias):
    desktop_entry = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={alias.capitalize()} CMD Helper
GenericName=CMD Helper
Comment=Smart command-line helper — double-click to open
Exec=python3 "{MAIN_PATH}" shell
Icon=utilities-terminal
Terminal=true
StartupNotify=false
Categories=Utility;System;
"""
    # install to applications menu
    apps_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(apps_dir, exist_ok=True)
    app_file = os.path.join(apps_dir, f"{alias}.desktop")
    with open(app_file, "w") as f:
        f.write(desktop_entry)
    os.chmod(app_file, 0o755)
    print(f"  App menu entry  → {app_file}")

    # also drop one on the Desktop if it exists
    desktop_dir = os.path.expanduser("~/Desktop")
    if os.path.isdir(desktop_dir):
        desk_file = os.path.join(desktop_dir, f"{alias}.desktop")
        with open(desk_file, "w") as f:
            f.write(desktop_entry)
        os.chmod(desk_file, 0o755)
        print(f"  Desktop icon    → {desk_file}")
        print(f"  (Right-click it and choose 'Allow Launching' if needed)")


def create_desktop_shortcut_mac(alias):
    desktop_dir = os.path.expanduser("~/Desktop")
    os.makedirs(desktop_dir, exist_ok=True)
    command_file = os.path.join(desktop_dir, f"{alias.capitalize()}.command")
    with open(command_file, "w") as f:
        f.write(f'#!/usr/bin/env bash\npython3 "{MAIN_PATH}" shell\n')
    os.chmod(command_file, 0o755)
    print(f"  Desktop launcher → {command_file}")
    print(f"  Double-click it to open. (First run: right-click → Open to bypass Gatekeeper)")


def create_desktop_shortcut_windows(alias):
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    os.makedirs(desktop_dir, exist_ok=True)
    bat_file = os.path.join(desktop_dir, f"{alias.capitalize()}.bat")
    with open(bat_file, "w") as f:
        f.write(f'@echo off\npython "{MAIN_PATH}" shell\npause\n')
    print(f"  Desktop launcher → {bat_file}")
    print(f"  Double-click it to open.")


def main():
    alias = load_alias()
    system = platform.system().lower()

    print(f"\nSetting up '{alias}' command...")

    if system in ("linux", "darwin"):
        setup_linux_mac(alias)
    elif system == "windows":
        setup_windows(alias)
    else:
        print(f"Unsupported OS: {system}")
        sys.exit(1)

    print(f"\nCreating desktop shortcut...")
    if system == "linux":
        create_desktop_shortcut_linux(alias)
    elif system == "darwin":
        create_desktop_shortcut_mac(alias)
    elif system == "windows":
        create_desktop_shortcut_windows(alias)


if __name__ == "__main__":
    main()
