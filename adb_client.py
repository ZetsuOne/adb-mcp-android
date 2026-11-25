"""Thin ADB subprocess wrapper used by the MCP server."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AdbError(RuntimeError):
    """Raised when an ADB invocation fails or ADB is missing."""


@dataclass
class AdbResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def text(self) -> str:
        out = self.stdout.strip()
        err = self.stderr.strip()
        if out and err:
            return f"{out}\n{err}"
        return out or err


def _bundled_adb() -> Path | None:
    """Prefer `bin/platform-tools/adb[.exe]` next to this project."""
    root = Path(__file__).resolve().parent
    for name in ("adb.exe", "adb"):
        candidate = root / "bin" / "platform-tools" / name
        if candidate.is_file():
            return candidate
    return None


def resolve_adb() -> str:
    """Resolve the `adb` executable: env → bundled bin/platform-tools → PATH."""
    for key in ("ADB_PATH", "ADB_EXECUTABLE"):
        candidate = os.environ.get(key)
        if candidate:
            path = Path(candidate).expanduser()
            if path.is_file():
                return str(path)
            raise AdbError(f"{key} is set but not a file: {candidate}")
    bundled = _bundled_adb()
    if bundled is not None:
        return str(bundled)
    found = shutil.which("adb")
    if found:
        return found
    raise AdbError(
        "adb not found. Place platform-tools under bin/platform-tools/, "
        "ensure `adb` is on PATH, or set ADB_PATH to the full path of adb.exe / adb."
    )


class AdbClient:
    def __init__(self, serial: str | None = None, adb_path: str | None = None) -> None:
        self.adb_path = adb_path or resolve_adb()
        env_serial = os.environ.get("ANDROID_SERIAL") or os.environ.get("ADB_SERIAL")
        self.serial = serial or env_serial

    def _base_cmd(self) -> list[str]:
        cmd = [self.adb_path]
        if self.serial:
            cmd.extend(["-s", self.serial])
        return cmd

    def run(
        self,
        args: list[str],
        *,
        timeout: float = 60.0,
        check: bool = True,
        input_data: bytes | None = None,
        binary_stdout: bool = False,
    ) -> AdbResult:
        cmd = self._base_cmd() + args
        try:
            completed = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AdbError(f"Failed to launch adb at {self.adb_path}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB timed out after {timeout}s: {' '.join(cmd)}") from exc

        stderr = completed.stderr.decode("utf-8", errors="replace")
        if binary_stdout:
            if check and completed.returncode != 0:
                raise AdbError(stderr.strip() or f"ADB failed ({completed.returncode}): {' '.join(cmd)}")
            result = AdbResult(stdout="", stderr=stderr, returncode=completed.returncode)
            setattr(result, "raw_stdout", completed.stdout or b"")
            return result

        stdout = completed.stdout.decode("utf-8", errors="replace")
        result = AdbResult(stdout=stdout, stderr=stderr, returncode=completed.returncode)
        if check and not result.ok:
            message = stderr.strip() or stdout.strip() or f"ADB failed ({completed.returncode})"
            raise AdbError(message)
        return result

    def devices(self) -> list[dict[str, str]]:
        # devices -l does not need -s
        cmd = [self.adb_path, "devices", "-l"]
        completed = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise AdbError(completed.stderr.strip() or "adb devices failed")
        lines = [ln.strip() for ln in completed.stdout.splitlines() if ln.strip()]
        # Skip header "List of devices attached"
        entries: list[dict[str, str]] = []
        for line in lines:
            if line.lower().startswith("list of devices"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            meta: dict[str, str] = {"serial": serial, "state": state}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    meta[key] = value
            entries.append(meta)
        return entries

    def shell(self, command: str, *, timeout: float = 60.0) -> str:
        result = self.run(["shell", command], timeout=timeout)
        return result.text()

    def getprop(self, name: str | None = None) -> str | dict[str, str]:
        if name:
            return self.shell(f"getprop {name}").strip()
        raw = self.shell("getprop")
        props: dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not (line.startswith("[") and "]: [" in line and line.endswith("]")):
                continue
            key_part, value_part = line.split("]: [", 1)
            key = key_part[1:]
            value = value_part[:-1]
            props[key] = value
        return props

    def install(self, apk_path: str, *, replace: bool = True, grant_permissions: bool = False) -> str:
        path = Path(apk_path).expanduser().resolve()
        if not path.is_file():
            raise AdbError(f"APK not found: {path}")
        args = ["install"]
        if replace:
            args.append("-r")
        if grant_permissions:
            args.append("-g")
        args.append(str(path))
        return self.run(args, timeout=300).text()

    def uninstall(self, package: str, *, keep_data: bool = False) -> str:
        args = ["uninstall"]
        if keep_data:
            args.append("-k")
        args.append(package)
        return self.run(args, timeout=120).text()

    def push(self, local: str, remote: str) -> str:
        src = Path(local).expanduser().resolve()
        if not src.exists():
            raise AdbError(f"Local path not found: {src}")
        return self.run(["push", str(src), remote], timeout=300).text()

    def pull(self, remote: str, local: str) -> str:
        dest = Path(local).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        return self.run(["pull", remote, str(dest)], timeout=300).text()

    def screenshot_png(self) -> bytes:
        # Prefer exec-out screencap for binary stream without host temp on device.
        result = self.run(
            ["exec-out", "screencap", "-p"],
            timeout=60,
            binary_stdout=True,
        )
        raw: bytes = getattr(result, "raw_stdout")
        if not raw or not raw.startswith(b"\x89PNG"):
            # Fallback: device file + pull
            remote = "/sdcard/adb-mcp-screenshot.png"
            self.shell(f"screencap -p {remote}")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                self.pull(remote, tmp_path)
                self.shell(f"rm -f {remote}")
                raw = Path(tmp_path).read_bytes()
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        return raw

    def logcat(
        self,
        *,
        lines: int = 200,
        clear: bool = False,
        filter_spec: str | None = None,
        timeout: float = 30.0,
    ) -> str:
        if clear:
            self.run(["logcat", "-c"], timeout=15, check=False)
        args = ["logcat", "-d", "-t", str(max(1, min(lines, 5000)))]
        if filter_spec:
            args.extend(filter_spec.split())
        return self.run(args, timeout=timeout, check=False).text()

    def input_tap(self, x: int, y: int) -> str:
        return self.shell(f"input tap {int(x)} {int(y)}")

    def input_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
        return self.shell(
            f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}"
        )

    def input_text(self, text: str) -> str:
        # Escape spaces for `input text`; other specials are best effort.
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        return self.shell(f"input text '{escaped}'")

    def input_keyevent(self, keycode: str | int) -> str:
        return self.shell(f"input keyevent {keycode}")

    def start_activity(self, component: str, *, extra_args: str = "") -> str:
        cmd = f"am start -n {component}"
        if extra_args:
            cmd = f"{cmd} {extra_args}"
        return self.shell(cmd)

    def force_stop(self, package: str) -> str:
        return self.shell(f"am force-stop {package}")

    def list_packages(self, *, third_party_only: bool = False, filter_text: str | None = None) -> list[str]:
        args = "pm list packages"
        if third_party_only:
            args += " -3"
        if filter_text:
            args += f" {filter_text}"
        raw = self.shell(args)
        packages: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                packages.append(line[len("package:") :])
        return packages

    def connect(self, host_port: str) -> str:
        # connect is global — no -s
        completed = subprocess.run(
            [self.adb_path, "connect", host_port],
            capture_output=True,
            timeout=30,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        text = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode != 0:
            raise AdbError(text or "adb connect failed")
        return text

    def disconnect(self, host_port: str | None = None) -> str:
        args = [self.adb_path, "disconnect"]
        if host_port:
            args.append(host_port)
        completed = subprocess.run(
            args,
            capture_output=True,
            timeout=30,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        return (completed.stdout or completed.stderr or "").strip()

    def reboot(self, mode: str | None = None) -> str:
        args = ["reboot"]
        if mode:
            args.append(mode)
        return self.run(args, timeout=30, check=False).text()

    def battery(self) -> dict[str, Any]:
        raw = self.shell("dumpsys battery")
        info: dict[str, Any] = {}
        for line in raw.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
                info[key] = int(value)
            elif value.lower() in {"true", "false"}:
                info[key] = value.lower() == "true"
            else:
                info[key] = value
        return info

    def wm_size(self) -> str:
        return self.shell("wm size").strip()

    def wm_density(self) -> str:
        return self.shell("wm density").strip()

    def forward(self, local: str, remote: str) -> str:
        return self.run(["forward", local, remote]).text()

    def forward_remove(self, local: str | None = None) -> str:
        if local:
            return self.run(["forward", "--remove", local], check=False).text()
        return self.run(["forward", "--remove-all"], check=False).text()

    def reverse(self, remote: str, local: str) -> str:
        return self.run(["reverse", remote, local]).text()

    def reverse_remove(self, remote: str | None = None) -> str:
        if remote:
            return self.run(["reverse", "--remove", remote], check=False).text()
        return self.run(["reverse", "--remove-all"], check=False).text()

    def device_summary(self) -> dict[str, Any]:
        keys = [
            "ro.product.manufacturer",
            "ro.product.model",
            "ro.product.device",
            "ro.build.version.release",
            "ro.build.version.sdk",
            "ro.build.display.id",
            "ro.serialno",
            "ro.product.cpu.abi",
        ]
        props = {k: str(self.getprop(k)).strip() for k in keys}
        try:
            battery = self.battery()
        except AdbError:
            battery = {}
        try:
            size = self.wm_size()
        except AdbError:
            size = ""
        try:
            density = self.wm_density()
        except AdbError:
            density = ""
        return {
            "serial": self.serial,
            "manufacturer": props.get("ro.product.manufacturer"),
            "model": props.get("ro.product.model"),
            "device": props.get("ro.product.device"),
            "android_version": props.get("ro.build.version.release"),
            "sdk": props.get("ro.build.version.sdk"),
            "build_id": props.get("ro.build.display.id"),
            "cpu_abi": props.get("ro.product.cpu.abi"),
            "ro_serialno": props.get("ro.serialno"),
            "wm_size": size,
            "wm_density": density,
            "battery": battery,
        }


def png_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
