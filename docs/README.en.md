# Lao Wang's Little Tugboat

An ultra-lightweight downloader built on aria2c. Windows-first, under 30 MB RAM, under 1 second startup, no Electron, no embedded browser engine.

## Features

- **Ultra-lightweight**: Python + CustomTkinter + aria2c sidecar
- **Multi-protocol**: HTTP / FTP / Magnet / BT / Metalink 4.0
- **Multi-file Metalink**: aggregated into a single card, marquee scrolls through all filenames
- **Task-level parameters**: `--countdown` auto-removes card on completion, `--global-countdown` overrides all
- **Dual hash verification**: aria2c built-in + independent Python re-check (md5 / sha-1 / sha-256 / sha-512)
- **Motrix-style UI**: card layout, top-right icon group, hover tooltips, rubber-band selection
- **Info hover overlay**: first-level directory aggregation, full expansion, scrollable, clipboard support
- **Single-instance IPC**: subsequent launches auto-forward to the main instance
- **CLI / HTTP API / callback port**: three integration paths for host programs
- **Theme switching**: midnight / cyberpunk / cyberpunk_v1, follows system DPI, centers on the work area

## Requirements

- Windows 10 / 11 (primary target)
- Python 3.9+
- [aria2c](https://github.com/aria2/aria2/releases) (download separately, place in project root)
- Python dependencies:
pip install customtkinter requests


## Quick Start

1. Clone:
git clone https://github.com/<your-username>/<repo>.git
cd <repo>

2. Download `aria2c.exe` to the project root ([download page](https://github.com/aria2/aria2/releases)).

3. Install dependencies:
pip install customtkinter requests


4. Launch:

python main.py

## Usage

### GUI mode

Launch without arguments. A configuration window pops up; fill in the URL and save path, then submit.

### CLI mode

python main.py "https://example.com/file.zip"
python main.py --countdown=5 "https://example.com/file.zip"
python main.py --title "Batch 1|Test" "magnet:?xt=urn:btih:..."

### Metalink mode

python main.py path\to\file.meta4
python main.py --metalink="<base64-encoded meta4 content>"

### More

Full CLI parameters, HTTP API, callback protocol, and IPC details: [docs/CLI.md](docs/CLI.md).

---