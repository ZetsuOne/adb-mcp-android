"""MCP bridge: control an Android device over ADB from Cursor / Claude / any MCP client."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from adb_client import AdbClient, AdbError, png_to_base64, resolve_adb

logger = logging.getLogger(__name__)
mcp = MCPServer("adb-android")


def _client(serial: str | None = None) -> AdbClient:
    return AdbClient(serial=serial)


def _err(exc: Exception) -> dict[str, Any]:
    return {"ok": False, "error": str(exc)}


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


@mcp.tool()
def adb_version() -> dict[str, Any]:
    """Return the resolved ADB binary path and `adb version` output."""
    try:
        path = resolve_adb()
        client = AdbClient(adb_path=path)
        # version is global
        import subprocess

        completed = subprocess.run(
            [path, "version"],
            capture_output=True,
            timeout=15,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return _ok(adb_path=path, version=(completed.stdout or completed.stderr or "").strip())
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def list_devices() -> dict[str, Any]:
    """List connected Android devices/emulators (`adb devices -l`)."""
    try:
        devices = _client().devices()
        return _ok(count=len(devices), devices=devices)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def device_info(serial: str | None = None) -> dict[str, Any]:
    """Hardware/software summary for a device (model, Android version, battery, screen)."""
    try:
        return _ok(device=_client(serial).device_summary())
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def shell(command: str, serial: str | None = None, timeout_sec: float = 60.0) -> dict[str, Any]:
    """Run a shell command on the device (`adb shell …`)."""
    try:
        if not command or not command.strip():
            raise AdbError("command must not be empty")
        output = _client(serial).shell(command, timeout=timeout_sec)
        return _ok(output=output)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def getprop(name: str | None = None, serial: str | None = None) -> dict[str, Any]:
    """Read one Android system property, or all properties if name is omitted."""
    try:
        value = _client(serial).getprop(name)
        if name:
            return _ok(name=name, value=value)
        return _ok(count=len(value) if isinstance(value, dict) else 0, properties=value)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def install_apk(
    apk_path: str,
    serial: str | None = None,
    replace: bool = True,
    grant_permissions: bool = False,
) -> dict[str, Any]:
    """Install an APK from the host filesystem onto the device."""
    try:
        output = _client(serial).install(
            apk_path, replace=replace, grant_permissions=grant_permissions
        )
        return _ok(output=output, apk_path=str(Path(apk_path).expanduser().resolve()))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def uninstall_app(
    package: str,
    serial: str | None = None,
    keep_data: bool = False,
) -> dict[str, Any]:
    """Uninstall an app by package name."""
    try:
        output = _client(serial).uninstall(package, keep_data=keep_data)
        return _ok(output=output, package=package)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def push_file(local_path: str, remote_path: str, serial: str | None = None) -> dict[str, Any]:
    """Copy a file or directory from the host to the device."""
    try:
        output = _client(serial).push(local_path, remote_path)
        return _ok(output=output, local_path=local_path, remote_path=remote_path)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def pull_file(remote_path: str, local_path: str, serial: str | None = None) -> dict[str, Any]:
    """Copy a file or directory from the device to the host."""
    try:
        output = _client(serial).pull(remote_path, local_path)
        return _ok(output=output, remote_path=remote_path, local_path=local_path)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def screenshot(
    serial: str | None = None,
    save_path: str | None = None,
    include_base64: bool = True,
) -> dict[str, Any]:
    """Capture the current screen as PNG. Optionally save to disk and/or return base64."""
    try:
        png = _client(serial).screenshot_png()
        saved = None
        if save_path:
            path = Path(save_path).expanduser().resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            saved = str(path)
        payload: dict[str, Any] = {
            "bytes": len(png),
            "saved_path": saved,
        }
        if include_base64:
            payload["png_base64"] = png_to_base64(png)
        return _ok(**payload)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def logcat(
    lines: int = 200,
    clear: bool = False,
    filter_spec: str | None = None,
    serial: str | None = None,
) -> dict[str, Any]:
    """Dump recent logcat lines. Optional filter_spec e.g. 'ActivityManager:I *:S'."""
    try:
        text = _client(serial).logcat(lines=lines, clear=clear, filter_spec=filter_spec)
        return _ok(lines_requested=lines, log=text)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def input_tap(x: int, y: int, serial: str | None = None) -> dict[str, Any]:
    """Tap screen coordinates (pixels)."""
    try:
        _client(serial).input_tap(x, y)
        return _ok(x=x, y=y)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def input_swipe(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
    serial: str | None = None,
) -> dict[str, Any]:
    """Swipe from (x1,y1) to (x2,y2) over duration_ms."""
    try:
        _client(serial).input_swipe(x1, y1, x2, y2, duration_ms)
        return _ok(x1=x1, y1=y1, x2=x2, y2=y2, duration_ms=duration_ms)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def input_text(text: str, serial: str | None = None) -> dict[str, Any]:
    """Type text into the focused field (best-effort escaping for ADB input text)."""
    try:
        _client(serial).input_text(text)
        return _ok(length=len(text))
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def input_keyevent(keycode: str, serial: str | None = None) -> dict[str, Any]:
    """Send a keyevent (name or code), e.g. KEYCODE_HOME, KEYCODE_BACK, 3, 4."""
    try:
        _client(serial).input_keyevent(keycode)
        return _ok(keycode=keycode)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def start_activity(
    component: str,
    extra_args: str = "",
    serial: str | None = None,
) -> dict[str, Any]:
    """Start an activity by component, e.g. com.example/.MainActivity."""
    try:
        output = _client(serial).start_activity(component, extra_args=extra_args)
        return _ok(output=output, component=component)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def force_stop(package: str, serial: str | None = None) -> dict[str, Any]:
    """Force-stop an application by package name."""
    try:
        output = _client(serial).force_stop(package)
        return _ok(output=output, package=package)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def list_packages(
    third_party_only: bool = False,
    filter_text: str | None = None,
    serial: str | None = None,
) -> dict[str, Any]:
    """List installed packages, optionally third-party only or filtered."""
    try:
        packages = _client(serial).list_packages(
            third_party_only=third_party_only, filter_text=filter_text
        )
        return _ok(count=len(packages), packages=packages)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def connect(host_port: str) -> dict[str, Any]:
    """Connect to a device over TCP/IP, e.g. 192.168.1.10:5555."""
    try:
        output = _client().connect(host_port)
        return _ok(output=output, host_port=host_port)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def disconnect(host_port: str | None = None) -> dict[str, Any]:
    """Disconnect a TCP/IP device, or all if host_port is omitted."""
    try:
        output = _client().disconnect(host_port)
        return _ok(output=output, host_port=host_port)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def reboot(
    mode: Literal["", "bootloader", "recovery", "sideload"] | None = None,
    serial: str | None = None,
) -> dict[str, Any]:
    """Reboot the device. Optional mode: bootloader, recovery, sideload."""
    try:
        use_mode = mode or None
        if use_mode == "":
            use_mode = None
        output = _client(serial).reboot(use_mode)
        return _ok(output=output, mode=use_mode)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def battery(serial: str | None = None) -> dict[str, Any]:
    """Return parsed `dumpsys battery` fields (level, status, temperature, …)."""
    try:
        return _ok(battery=_client(serial).battery())
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def screen_metrics(serial: str | None = None) -> dict[str, Any]:
    """Return `wm size` and `wm density` for the device."""
    try:
        client = _client(serial)
        return _ok(wm_size=client.wm_size(), wm_density=client.wm_density())
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def port_forward(
    local: str,
    remote: str,
    serial: str | None = None,
) -> dict[str, Any]:
    """Forward a host port to a device port, e.g. local=tcp:8080 remote=tcp:8080."""
    try:
        output = _client(serial).forward(local, remote)
        return _ok(output=output, local=local, remote=remote)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def port_forward_remove(local: str | None = None, serial: str | None = None) -> dict[str, Any]:
    """Remove one port forward, or all if local is omitted."""
    try:
        output = _client(serial).forward_remove(local)
        return _ok(output=output, local=local)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def port_reverse(
    remote: str,
    local: str,
    serial: str | None = None,
) -> dict[str, Any]:
    """Reverse-forward a device port to a host port."""
    try:
        output = _client(serial).reverse(remote, local)
        return _ok(output=output, remote=remote, local=local)
    except Exception as exc:
        return _err(exc)


@mcp.tool()
def port_reverse_remove(remote: str | None = None, serial: str | None = None) -> dict[str, Any]:
    """Remove one reverse forward, or all if remote is omitted."""
    try:
        output = _client(serial).reverse_remove(remote)
        return _ok(output=output, remote=remote)
    except Exception as exc:
        return _err(exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
