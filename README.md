# CMD Helper

A smart command-line helper that maps short, friendly commands to real system commands — and comes with a **built-in AI coach**, an **interactive shell**, a **dev-tool auditor**, and **guided learning paths** for the terminal. Works on **Linux, Mac, and Windows**.

Instead of memorizing long terminal commands, you type short natural ones. The tool figures out the rest, asks questions when needed, and runs the right command for your OS automatically. When you don't know the command at all, just ask the AI.

---

## Features

| | |
|---|---|
| **Run apps** | Launch browsers and apps by name — with private/incognito support |
| **System info** | List processes, network, disks, memory, CPU, ports, users |
| **AI coach** | Ask any terminal/dev question and get a runnable command back |
| **Interactive shell** | A REPL that mixes helper commands, real shell commands, and AI |
| **Dev audit** | Check which developer tools are installed on your machine |
| **Learn** | Structured, interactive lessons for Terminal, Git, Docker, SSH, and monitoring |
| **Guide** | Full command reference, organized by OS and category |
| **Desktop shortcut** | Double-click launcher for the interactive shell |

Everything is driven by `config.json` — add new apps or list categories without touching code.

---

## Setup

**1. Set your alias** in `config.json` (default is `spider`):
```json
{ "alias": "spider" }
```

**2. Run setup once:**
```bash
# Linux / Mac
python3 setup.py

# Windows
python setup.py
```

This installs the `alias` command (e.g. `spider`) to your PATH, an `alias:` AI shortcut (e.g. `spider:`), and a desktop shortcut for the interactive shell.

**3. Reload your shell (Linux/Mac only):**
```bash
source ~/.bashrc   # or ~/.zshrc
```

**4. (Optional) Create just the desktop shortcut:**
```bash
python3 create_shortcut.py
```

---

## Commands

Replace `spider` with whatever alias you set in `config.json`.

| Command | What it does |
|---|---|
| `spider run chrome` | Launch Chrome |
| `spider run private chrome` | Launch Chrome in incognito/private mode |
| `spider run` | Show a picker — choose an app to launch |
| `spider list processes` | Show running processes |
| `spider list` | Pick a category interactively |
| `spider kill chrome` | Kill a running process (asks to confirm) |
| `spider open /path/to/folder` | Open a file or folder |
| `spider find report.pdf` | Search for files by name |
| `spider ask "how do I zip a folder?"` | Ask the AI — get an explanation + runnable command |
| `spider: how do I zip a folder` | AI shortcut (installed by setup) |
| `spider check` | Audit installed dev tools |
| `spider learn` | Open interactive learning paths |
| `spider guide` | Full command reference |
| `spider shell` | Enter interactive terminal mode |
| `spider --help` | Show full usage |

Typos are handled with fuzzy matching — `spider run chrom` will suggest `chrome`.

---

## AI Assistant

The `ask` command (and the `:` shortcut) sends your question to a free model via [OpenRouter](https://openrouter.ai) and returns a short, structured answer with a ready-to-run command. It then offers to **run that command for you** with a single keypress.

**Configure it in `config.json`:**
```json
{
  "openrouter_api_key": "sk-or-v1-...",
  "ai_model": "meta-llama/llama-3.3-70b-instruct:free"
}
```

- Get a free key at [openrouter.ai/keys](https://openrouter.ai/keys).
- If no key is saved, the tool prompts you once and offers to save it.
- If your chosen model is unavailable, it automatically falls back through a list of other free models.

> **Security note:** `config.json` in this repo currently contains a real API key. Replace it with your own and **do not commit real keys** — rotate the existing one if it has been shared.

---

## Interactive Shell

`spider shell` opens a REPL where you can freely mix three kinds of input:

- **Helper commands** — `run`, `list`, `kill`, `open`, `find`, `check`, `learn`, `guide`, `ask`
- **Real system commands** — `ls`, `cd`, `git status`, `ping`, `docker ps`, ...
- **AI questions** — prefix with `:` — e.g. `: how do I undo the last git commit`

`cd` is handled internally so your working directory persists across commands. Type `exit` (or `q`) to leave.

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

Built-in categories: `processes`, `files`, `network`, `disks`, `users`, `ports`, `memory`, `cpu`.

---

## Learning Paths

`spider learn` opens interactive, lesson-based paths — each with concepts, real commands, a pro tip, and a challenge to try:

- **Terminal Basics** — navigation, files, pipes & redirection
- **Git & Version Control** — core workflow, branches, remotes, undo & recovery
- **Docker & Containers** — images, containers, ports/volumes/env, Compose
- **SSH & Remote Work** — basics, keys, copying files
- **System Monitoring** — watching processes, disk & memory

`spider guide` shows the full command reference for Linux, Windows (CMD + PowerShell), or macOS, organized by category.

---

## Files

```
cmd-helper/
├── main.py             — core logic, all command handlers
├── config.json         — your command dictionary + AI settings
├── cmd_reference.py    — command reference + learning-path content
├── setup.py            — one-time install (alias, AI shortcut, desktop icon)
└── create_shortcut.py  — create the desktop shortcut on its own
```

---

## Requirements

- Python 3.6+
- No external packages needed (uses only the standard library)
- An OpenRouter API key for AI features (free tier works)
