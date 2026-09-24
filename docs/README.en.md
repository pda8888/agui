# Lao Wang's Little Tugboat

An ultra-lightweight downloader based on aria2c. Windows first, memory < 30 MB, startup < 1 second, no Electron, no browser engine.

## Features

- **Ultra-lightweight**: Python + CustomTkinter + aria2c sidecar
- **Multi-protocol**: HTTP / FTP / Magnet / BT / Metalink 4.0
- **Multi-file Metalink**: aggregated display in a single card, carousel shows all filenames in turn
- **Task-level parameters**: `--countdown` auto delete card after completion, `--global-countdown` global override
- **Dual hash verification**: aria2c built-in + Python second independent verification (md5 / sha-1 / sha-256 / sha-512)
- **Motrix-style UI**: card layout, icon group in top-right corner, hover tooltips, box selection for multi-select
- **info hover overlay**: first-level directory aggregation + full expansion + scrolling + clipboard
- **Single-instance IPC**: multiple launches are automatically forwarded to the main instance
- **Command line / HTTP API / callback port**: three external interfaces for easy integration into main programs
- **Multiple theme switching**: midnight / cyberpunk / cyberpunk_v1, follows system DPI, workspace centered

## Environment requirements

- Windows 10 / 11 (primary target)
- Python 3.9+
- [aria2c](https://github.com/aria2/aria2/releases) (user downloads manually and places it in the project root directory)
- Python dependencies:
pip install customtkinter requests

## Quick start

1. Clone the repository:
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

2. Download aria2c.exe to the project root directory ([download link](https://github.com/aria2/aria2/releases))

3. Install dependencies:
pip install customtkinter requests


4. Launch:
python main.py


## Usage

### GUI mode

Start without parameters, a configuration window pops up, fill in the URL and save path, then click submit.

### Command line mode
python main.py "https://example.com/file.zip"

python main.py --countdown=5 "https://example.com/file.zip"

python main.py --title "Batch1|Test" "magnet:?xt=urn:btih:..."


### Metalink mode

python main.py path\to\file.meta4

python main.py --metalink="<base64-encoded meta4 content>"

### More

For full command line parameters, HTTP API, callback protocol, and IPC mechanism description, see [docs/CLI.md](docs/CLI.md).

---
## Packaging

Two modes, switch using the environment variable `AGUI_SLIM`.

### Full Package (includes aria2c.exe)
Make sure `aria2c.exe` is in the project root (can be restored from cache with `copy %TEMP%aria2c.exe .`):
``` 
set AGUI_SLIM=
pyinstaller --clean --noconfirm agui.spec
```
The output `distagui.exe` is about 11.4 MB.

### Slim Package (doesn't include aria2c.exe, downloads on demand at runtime)
```
set AGUI_SLIM=1
pyinstaller --clean --noconfirm agui.spec
```
The output `distagui.exe` is about 9.6 MB. On the first run, if `%TEMP%aria2c.exe` doesn't exist, aria2 1.37.0 will automatically be downloaded and extracted from three proxies in order: gh-proxy.com / hk.gh-proxy.org / cdn.gh-proxy.com.

During the download, the status bar will show "Downloading aria2c.exe..." without blocking the window; once done, the sidecar will start automatically.

You can also use `-a` / `--aria2c-path <path>` to specify a local aria2c.exe.

> Note: In `set VAR=val & cmd`, any space before `&` will be included in the value (becomes `"val "`); please run `set` on a separate line.

## Project Structure
. - `main.py` ！ Entry point
- `config.py` ！ Constants and themes
- `arg_parser.py` ！ Command line parsing
- `rpc_client.py` ！ aria2 JSON-RPC wrapper
- `process_manager.py` ！ aria2c process and firewall
- `ipc_server.py` ！ Single-instance IPC
- `http_server.py` ！ HTTP API service (enabled with --http-port)
- `utils.py` ！ Utility functions
- `ui_config.py` ！ Settings interface
- `ui_download.py` ！ Main download monitor interface
- `info_overlay.py` ！ Task details overlay
- `ui_styles.py` ！ UI style factory
- `ui_help.py` ！ Help window
- `docs/CLI.md` ！ CLI / API documentation
- `LICENSE`
- `README.md`

## Keyboard and Mouse
- **Click card**: Select
- **Ctrl + Click**: Toggle multi-selection
- **Drag**: Box select
- **Hover over icon**: Show tooltip
- **Hover over ?**: Show task details overlay
- **Top bar icons**: Only affect selected tasks (inactive if none selected)

## Known Limitations
- **Windows First**: Some features (Job Object, Firewall, `os.startfile`) rely on the Windows API; not tested on Linux/macOS.
- **`--query` / `--kill` depend on the main instance**: You need to start a main instance first, then query from another terminal.
- **The countdown parameter in the HTTP API is not effective yet**: Please use the command-line method. See [docs/CLI.md] for details.
- Checked by the kernel, independently recalculated by Python for double safety.

## License
[MIT](LICENSE)

## Thanks
- [aria2](https://github.com/aria2/aria2): download kernel
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter): dark theme UI
- [Motrix](https://github.com/agalwood/motrix): visual reference for card layout in V1.8

## Disclaimer
This project is only a graphical interface wrapper for aria2c. Users should comply with local laws and regulations and must not use it to download pirated, adult, or other illegal content. The project author is not responsible for the actions of the users.