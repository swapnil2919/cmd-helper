# CMD Helper

A smart command-line helper that maps simple, friendly commands to real system commands. Works on **Linux, Mac, and Windows**.

Instead of remembering long terminal commands, you type short natural ones — the tool figures out the rest, asks questions when needed, and runs the right command for your OS automatically.

---

## How It Works

Everything is driven by `config.json`. It holds:
- Your **alias** (the name you use to call the tool)
- An **apps dictionary** (friendly name → real command per OS)
- A **list commands dictionary** (category → system command per OS)

No code changes needed to add new apps — just edit the JSON.

---

## Setup

**1. Set your alias** in `config.json`:
```json
{ "alias": "smart" }
```

**2. Run setup once:**
```bash
# Linux / Mac
python3 setup.py

# Windows
python setup.py
```

**3. Reload your shell (Linux/Mac only):**
```bash
source ~/.bashrc   # or ~/.zshrc
```

---

## Commands

| Command | What it does |
|---|---|
| `smart run chrome` | Launch Chrome |
| `smart run private chrome` | Launch Chrome in incognito/private mode |
| `smart run` | Show a picker — choose app, then private or normal |
| `smart list processes` | Show running processes |
| `smart list` | Pick a category interactively |
| `smart kill chrome` | Kill a running process |
| `smart open /path/to/folder` | Open a file or folder |
| `smart find report.pdf` | Search for files by name |
| `smart --help` | Show full usage |

> Replace `smart` with whatever alias you set in `config.json`.

---

## Adding Apps

Open `config.json` and add an entry under `"apps"`:

```json
"vlc": {
  "linux": ["vlc"],
  "mac": ["open", "-a", "VLC"],
  "windows": ["cmd", "/c", "start", "vlc"]
}
```

To support private/incognito mode for a browser, add it under `"private_flags"`:

```json
"chrome": {
  "linux": "--incognito",
  "mac": "--incognito",
  "windows": "--incognito"
}
```

---

## Adding List Categories

Under `"list_commands"` in `config.json`:

```json
"services": {
  "linux": ["systemctl", "list-units", "--type=service"],
  "mac": ["launchctl", "list"],
  "windows": ["sc", "query"]
}
```

---

## Files

```
cmd-script/
├── main.py       — core logic
├── config.json   — your command dictionary
└── setup.py      — one-time install script
```

---

## Requirements

- Python 3.6+
- No external packages needed
