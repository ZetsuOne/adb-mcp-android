English | [Русский](README_RU.md)

# adb-mcp-android

MCP bridge between Cursor / Claude Desktop (or any MCP client) and an Android phone or emulator over **ADB**.

The server talks to the official `adb` binary on your machine. It does **not** ship USB drivers or Android platform-tools — install those separately (drivers may live in another folder on your PC).

## Features

| Tool | What it does |
| --- | --- |
| `adb_version` | Resolved `adb` path + version string |
| `list_devices` | `adb devices -l` |
| `device_info` | Model, Android version, ABI, battery, screen size |
| `shell` | Run any `adb shell` command |
| `getprop` | One property or the full map |
| `install_apk` / `uninstall_app` | Install / remove packages |
| `push_file` / `pull_file` | Host ↔ device file copy |
| `screenshot` | PNG capture (optional save path + base64) |
| `logcat` | Recent dump, optional filter / clear |
| `input_tap` / `input_swipe` / `input_text` / `input_keyevent` | UI input |
| `start_activity` / `force_stop` / `list_packages` | App control |
| `connect` / `disconnect` | TCP/IP ADB |
| `reboot` | Normal / bootloader / recovery / sideload |
| `battery` / `screen_metrics` | Power + `wm size` / density |
| `port_forward` / `port_forward_remove` | Host → device forwards |
| `port_reverse` / `port_reverse_remove` | Device → host reverses |

Most tools accept an optional `serial`. If omitted, the server uses `ANDROID_SERIAL` / `ADB_SERIAL`, or ADB’s default single device.

## Prerequisites (not bundled)

1. **Android platform-tools** — this project expects `bin/platform-tools/adb` (or `adb.exe` on Windows). You can also put `adb` on `PATH`, or set `ADB_PATH` to another install.
2. **USB drivers** (Windows) — OEM or Google USB driver; keep them separately. This repo does not include driver packages.
3. On the phone: **Developer options → USB debugging** (and authorize the PC fingerprint when prompted).
4. Python **3.10+**.

Quick check:

```powershell
adb version
adb devices
```

You should see your device as `device` (not `unauthorized` / `offline`).

## Quick start with `uvx`

Requires [uv](https://docs.astral.sh/uv/).

```bash
uvx --from git+https://github.com/ZetsuOne/adb-mcp-android adb-mcp-android
```

### Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "adb-android": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ZetsuOne/adb-mcp-android", "adb-mcp-android"]
    }
  }
}
```

`adb` is taken from `bin/platform-tools/` automatically. Optional env:

```json
"env": {
  "ANDROID_SERIAL": "XXXXXXXX"
}
```

## Classic install (venv)

### Windows (PowerShell)

```powershell
git clone https://github.com/ZetsuOne/adb-mcp-android.git
cd adb-mcp-android
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Smoke-test:

```powershell
python client.py
```

Run the server (stdio; waits for an MCP client):

```powershell
python server.py
# or after `pip install -e .`:
adb-mcp-android
```

Local Cursor config:

```json
{
  "mcpServers": {
    "adb-android": {
      "command": "C:\\Projects\\adb-mcp-android\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Projects\\adb-mcp-android\\server.py"]
    }
  }
}
```

### Linux / macOS

```bash
git clone https://github.com/ZetsuOne/adb-mcp-android.git
cd adb-mcp-android
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python client.py
```

## Environment variables

| Variable | Meaning |
| --- | --- |
| `ADB_PATH` / `ADB_EXECUTABLE` | Override path to `adb` (default: `bin/platform-tools/adb[.exe]`, then `PATH`) |
| `ANDROID_SERIAL` / `ADB_SERIAL` | Default device serial when tools omit `serial` |

## Example responses

`list_devices`:

```json
{
  "ok": true,
  "count": 1,
  "devices": [
    {
      "serial": "RFCX123456",
      "state": "device",
      "model": "Pixel_7",
      "device": "panther",
      "product": "panther"
    }
  ]
}
```

`device_info` (truncated):

```json
{
  "ok": true,
  "device": {
    "manufacturer": "Google",
    "model": "Pixel 7",
    "android_version": "14",
    "sdk": "34",
    "wm_size": "Physical size: 1080x2400",
    "battery": { "level": 81, "status": 2 }
  }
}
```

## Project layout

| Path | Role |
| --- | --- |
| `server.py` | MCP server (stdio) and `adb-mcp-android` entry point |
| `adb_client.py` | ADB subprocess helper |
| `client.py` | Stdio smoke-test client |
| `pyproject.toml` | Packaging + console script |
| `requirements.txt` | Runtime deps for `pip install -r` |

## Safety notes

- `shell` can run arbitrary device commands — use only on devices you own/control.
- USB drivers and platform-tools are **external** dependencies; do not commit proprietary OEM driver blobs into this repo.
- Prefer a dedicated test device when experimenting with install / reboot / force-stop.

## License

MIT — see [LICENSE](LICENSE).
