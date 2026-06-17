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


if __name__ == "__main__":
    main()
