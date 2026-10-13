"""Explicit installed-browser profiles; driver downloads are always opt-in.

Reading preferences and detecting installations never starts a browser.
Student browser data belongs in caller-owned temporary directories.
"""
from __future__ import annotations

import ctypes
from functools import wraps
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import tempfile
import threading
import tomllib
import uuid
from pathlib import Path

BROWSER_NAMES = {
    "chrome": "Google Chrome", "edge": "Microsoft Edge", "firefox": "Mozilla Firefox",
    "safari": "Safari", "chromium": "Chromium", "360e": "360 Extreme (experimental)",
    "custom": "Custom browser (experimental)",
}
DRIVER_NAMES = {"chromedriver": "ChromeDriver", "msedgedriver": "EdgeDriver",
                "geckodriver": "GeckoDriver", "safaridriver": "SafariDriver (built-in)"}
_DEFAULT_DRIVER = {"chrome": "chromedriver", "edge": "msedgedriver",
                   "firefox": "geckodriver", "safari": "safaridriver",
                   "chromium": "chromedriver", "360e": "chromedriver", "custom": "chromedriver"}
_LOCK = threading.RLock()
_VERSION = re.compile(r"\b(\d+\.\d+(?:\.\d+){0,2})\b")


def _public_api(function):
    """Keep filesystem/subprocess details out of user-facing exceptions."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except ValueError:
            raise
        except Exception:
            raise ValueError("Browser configuration operation failed; check the selected files and permissions / 浏览器配置操作失败，请检查所选文件与权限。") from None
    return wrapped


def storage_root() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "AttendanceBook"


def settings_path() -> Path:
    return storage_root() / "browser_profiles.json"


def default_driver_kind(browser: str) -> str:
    try:
        return _DEFAULT_DRIVER[browser]
    except (KeyError, TypeError):
        raise ValueError("Choose a browser first / 请先选择浏览器。") from None


def _normalise(profile, *, new_id=False) -> dict:
    if not isinstance(profile, dict):
        raise ValueError("Choose a browser profile first / 请先选择浏览器配置。")
    p = dict(profile)
    browser = p.get("browser")
    default = default_driver_kind(browser)
    for key in ("id", "name", "executable", "driver_path"):
        value = p.get(key, "")
        if value is None:
            value = ""
        if not isinstance(value, (str, os.PathLike)):
            raise ValueError("Invalid browser profile field / 浏览器配置字段无效。")
        p[key] = str(value).strip()
    if new_id and not p["id"]:
        p["id"] = uuid.uuid4().hex
    if not p["name"]:
        raise ValueError("Enter a profile name / 请输入配置名称。")
    if not p["executable"]:
        raise ValueError("Select an installed browser executable / 请选择已安装的浏览器路径。")
    p["driver_kind"] = p.get("driver_kind") or default
    p["driver_mode"] = p.get("driver_mode") or "auto"
    if p["driver_mode"] not in ("auto", "manual"):
        raise ValueError("Invalid driver mode / 驱动模式无效。")
    kind = p["driver_kind"]
    allowed = {default} if browser != "custom" else {"chromedriver", "msedgedriver", "geckodriver"}
    if not isinstance(kind, str) or kind not in allowed:
        raise ValueError("Driver kind is incompatible with this browser / 驱动类型与浏览器不兼容。")
    return p


def _read() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "profiles": [], "active_id": None}
    except (OSError, ValueError, UnicodeError):
        raise ValueError("Cannot read browser settings; preserve and repair the settings file / 无法读取浏览器设置，请保留并修复配置文件。") from None
    try:
        if not isinstance(data, dict) or data.get("version", 1) != 1 or not isinstance(data.get("profiles"), list):
            raise ValueError
        profiles = [_normalise(p) for p in data["profiles"]]
        ids = [p["id"] for p in profiles]
        if not all(ids) or len(ids) != len(set(ids)):
            raise ValueError
        if data.get("active_id") is not None and data["active_id"] not in ids:
            raise ValueError
        data["profiles"] = profiles
    except (ValueError, TypeError, KeyError):
        raise ValueError("Browser settings are invalid; preserve and repair the settings file / 浏览器配置无效，请保留并修复配置文件。") from None
    return data


def _write(data):
    temporary = None
    try:
        dest = settings_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".browser-profiles-", suffix=".tmp", dir=dest.parent)
        temporary = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, dest)
    except (OSError, TypeError, ValueError):
        raise ValueError("Cannot save browser settings / 无法保存浏览器设置。") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_profiles() -> list[dict]:
    with _LOCK:
        return [dict(p) for p in _read()["profiles"]]


def get_active_profile() -> dict | None:
    with _LOCK:
        data = _read()
        return next((dict(p) for p in data["profiles"] if p["id"] == data.get("active_id")), None)


def save_profile(profile, activate=False) -> dict:
    p = _normalise(profile, new_id=True)
    with _LOCK:
        data = _read()
        data["profiles"] = [p if old["id"] == p["id"] else old for old in data["profiles"]]
        if not any(old["id"] == p["id"] for old in data["profiles"]):
            data["profiles"].append(p)
        if activate:
            data["active_id"] = p["id"]
        _write(data)
    return dict(p)


def set_active_profile(id) -> dict:
    with _LOCK:
        data = _read()
        selected = next((p for p in data["profiles"] if p["id"] == id), None)
        if selected is None:
            raise ValueError("Unknown browser profile / 浏览器配置不存在。")
        data["active_id"] = id
        _write(data)
        return dict(selected)


def delete_profile(id):
    with _LOCK:
        data = _read()
        if not any(p["id"] == id for p in data["profiles"]):
            raise ValueError("Unknown browser profile / 浏览器配置不存在。")
        data["profiles"] = [p for p in data["profiles"] if p["id"] != id]
        if data.get("active_id") == id:
            data["active_id"] = None
        _write(data)


@_public_api
def browser_executable(value) -> Path:
    if not value or not isinstance(value, (str, os.PathLike)):
        raise ValueError("Select an installed browser executable / 请选择浏览器路径。")
    path = Path(value).expanduser()
    if platform.system() == "Darwin" and path.suffix.lower() == ".app" and path.is_dir():
        try:
            info = plistlib.loads((path / "Contents" / "Info.plist").read_bytes())
            name = info["CFBundleExecutable"]
            if not isinstance(name, str) or name in ("", ".", "..") or Path(name).name != name:
                raise ValueError
            path = path / "Contents" / "MacOS" / name
        except (OSError, ValueError, KeyError, TypeError, plistlib.InvalidFileException):
            raise ValueError("Invalid browser application bundle / 浏览器应用程序无效。") from None
    if not path.is_file():
        raise ValueError("Selected browser executable is missing / 所选浏览器路径不存在。")
    if platform.system() == "Windows" and path.suffix.lower() != ".exe":
        raise ValueError("Choose a Windows executable (.exe) / 请选择 .exe 浏览器文件。")
    if platform.system() != "Windows" and not os.access(path, os.X_OK):
        raise ValueError("Selected browser file is not executable / 所选浏览器文件不可执行。")
    return path.resolve()


def _run(args, *, timeout=8, env=None):
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace",
              "timeout": timeout, "check": False}
    if env is not None:
        kwargs["env"] = env
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return subprocess.run([str(arg) for arg in args], **kwargs)


def _windows_version(path):
    """Read PE file metadata without executing the browser."""
    try:
        version = ctypes.windll.version
        size = version.GetFileVersionInfoSizeW(str(path), None)
        if not size:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(str(path), 0, size, buffer):
            return None
        pointer, length = ctypes.c_void_p(), ctypes.c_uint()
        if not version.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return None
        fixed = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
        if length.value < 52 or fixed[0] != 0xFEEF04BD:
            return None
        return ".".join(str(n) for n in (fixed[2] >> 16, fixed[2] & 0xFFFF, fixed[3] >> 16, fixed[3] & 0xFFFF))
    except (AttributeError, OSError, ValueError):
        return None


def _browser_version(path, browser):
    if platform.system() == "Darwin":
        for parent in path.parents:
            if parent.suffix.lower() == ".app":
                try:
                    info = plistlib.loads((parent / "Contents" / "Info.plist").read_bytes())
                    match = _VERSION.search(str(info.get("CFBundleShortVersionString", "")))
                    return match.group(1) if match else None
                except (OSError, ValueError, plistlib.InvalidFileException):
                    return None
        return None
    if platform.system() == "Windows":
        return _windows_version(path)
    try:
        result = _run([path, "--version"])
        match = _VERSION.search(result.stdout) if result.returncode == 0 else None
        return match.group(1) if match else None
    except (OSError, subprocess.SubprocessError):
        return None


def _installation_candidates():
    system = platform.system()
    if system == "Darwin":
        bundles = {"chrome": "Google Chrome.app", "edge": "Microsoft Edge.app", "firefox": "Firefox.app",
                   "safari": "Safari.app", "chromium": "Chromium.app", "360e": "360Chrome.app"}
        for base in (Path("/Applications"), Path.home() / "Applications", Path("/System/Applications")):
            for browser, bundle in bundles.items():
                yield browser, base / bundle
    elif system == "Windows":
        relative = {"chrome": "Google/Chrome/Application/chrome.exe", "edge": "Microsoft/Edge/Application/msedge.exe",
                    "firefox": "Mozilla Firefox/firefox.exe", "chromium": "Chromium/Application/chrome.exe",
                    "360e": "360/360Chrome/Chrome/Application/360chrome.exe"}
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                for browser, rel in relative.items():
                    yield browser, Path(base) / rel
                for rel in ("360/360ChromeX/Chrome/Application/360ChromeX.exe", "360/360se6/Application/360se.exe"):
                    yield "360e", Path(base) / rel
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                    for browser, exe in (("chrome", "chrome.exe"), ("edge", "msedge.exe"), ("firefox", "firefox.exe"),
                                         ("360e", "360chrome.exe"), ("360e", "360ChromeX.exe")):
                        try:
                            key = "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\" + exe
                            with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                                yield browser, Path(os.path.expandvars(winreg.QueryValue(handle, None)).strip('"'))
                        except OSError:
                            pass
        except ImportError:
            pass
    else:
        commands = {"chrome": ("google-chrome", "google-chrome-stable"), "edge": ("microsoft-edge", "microsoft-edge-stable"),
                    "firefox": ("firefox",), "chromium": ("chromium", "chromium-browser")}
        for browser, names in commands.items():
            for name in names:
                path = shutil.which(name)
                if path:
                    yield browser, Path(path)


@_public_api
def detect_browsers() -> list[dict]:
    results, seen = [], set()
    for browser, candidate in _installation_candidates():
        try:
            executable = browser_executable(candidate)
        except (ValueError, OSError):
            continue
        if str(executable) in seen:
            continue
        seen.add(str(executable))
        results.append({"browser": browser, "name": BROWSER_NAMES[browser], "executable": str(executable),
                        "driver_kind": default_driver_kind(browser), "driver_mode": "auto", "driver_path": "",
                        "browser_version": _browser_version(executable, browser)})
    return results


def _driver_details(path, kind):
    path = Path(path).expanduser()
    if not path.is_file() or (platform.system() != "Windows" and not os.access(path, os.X_OK)):
        raise ValueError("Selected driver is missing or not executable / 所选驱动不存在或不可执行。")
    try:
        result = _run([path, "--version"])
        output = result.stdout + "\n" + result.stderr
        names = {"chromedriver": r"ChromeDriver", "msedgedriver": r"(?:MSEdgeDriver|Microsoft Edge WebDriver)",
                 "geckodriver": r"geckodriver", "safaridriver": r"(?:safaridriver|Safari WebDriver)"}
        match = re.search(names[kind] + r"\s+(\d+\.\d+(?:\.\d+){0,2})", output, re.I)
        if result.returncode != 0 or not match:
            raise ValueError
        return match.group(1)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise ValueError("Driver identity/version could not be verified; choose the matching driver / 无法验证驱动类型或版本，请选择匹配的驱动。") from None


def _version_tuple(version):
    return tuple(int(part) for part in str(version).split("."))


def _check_compatibility(kind, browser_version, driver_version):
    if not browser_version:
        return
    browser = _version_tuple(browser_version)
    driver = _version_tuple(driver_version)
    if kind in ("chromedriver", "msedgedriver"):
        count = 3 if kind == "msedgedriver" else 1
        if browser[:count] != driver[:count]:
            raise ValueError("Driver version does not match the selected browser / 驱动版本与所选浏览器不匹配。")
    elif kind == "geckodriver":
        # https://firefox-source-docs.mozilla.org/testing/geckodriver/Support.html
        minimum = 115 if driver >= (0, 34) else 102 if driver >= (0, 32) else 91 if driver >= (0, 31) else 78
        maximum = None if driver >= (0, 34) else 120 if driver >= (0, 31) else 90
        if driver < (0, 30) or browser[0] < minimum or (maximum is not None and browser[0] > maximum):
            raise ValueError("GeckoDriver does not support this Firefox version / GeckoDriver 不支持此 Firefox 版本。")


@_public_api
def driver_library() -> list[dict]:
    """Read-only inventory of installed driver versions and their provenance."""
    rows = []
    seen = set()
    roots = ((storage_root() / "drivers", "library"), (storage_root() / "selenium", "cache"),
             (Path.home() / ".cache" / "selenium", "selenium-cache"))
    for root, source in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            kind = path.name.lower().removesuffix(".exe")
            if kind not in DRIVER_NAMES or not path.is_file() or str(path.resolve()) in seen:
                continue
            seen.add(str(path.resolve()))
            version = next((p.name for p in path.parents if re.fullmatch(r"\d+\.\d+(?:\.\d+){0,2}", p.name)), "")
            rows.append({"kind": kind, "name": DRIVER_NAMES[kind], "path": str(path.resolve()),
                         "version": version, "source": source, "installed": True})
    if platform.system() == "Darwin" and Path("/usr/bin/safaridriver").is_file():
        rows.append({"kind": "safaridriver", "name": DRIVER_NAMES["safaridriver"], "path": "/usr/bin/safaridriver",
                     "version": "built-in", "source": "system", "installed": True})
    return rows


@_public_api
def delete_managed_driver(path) -> None:
    """Remove one version from AttendanceBook's cache, never a shared/system driver."""
    candidate = Path(path).expanduser()
    root = storage_root().resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise ValueError("Only AttendanceBook-managed drivers can be deleted / 只能删除本程序管理的驱动。") from None
    parts = relative.parts
    imported = len(parts) == 4 and parts[0] == "drivers"
    cached = len(parts) == 5 and parts[0] == "selenium"
    if not (imported or cached):
        raise ValueError("Only individual managed driver versions can be deleted / 只能删除本程序管理的单个驱动版本。")
    kind = parts[1]
    version = parts[2] if imported else parts[3]
    filename = parts[-1]
    expected = kind + (".exe" if platform.system() == "Windows" else "")
    if (kind not in DRIVER_NAMES or kind == "safaridriver"
            or not _VERSION.fullmatch(version) or filename.lower() != expected):
        raise ValueError("Invalid managed driver path / 驱动路径无效。")
    if any(part.is_symlink() for part in (root, *candidate.parents, candidate)):
        raise ValueError("Linked driver paths cannot be deleted / 不能删除符号链接驱动路径。")
    if not candidate.is_file() or candidate.resolve() != candidate:
        raise ValueError("The selected driver no longer exists / 所选驱动已不存在。")
    with _LOCK:
        profiles = _read()["profiles"]
        if any(p.get("driver_path") and Path(p["driver_path"]).expanduser().resolve() == candidate
               for p in profiles):
            raise ValueError("A saved profile uses this driver; change that profile first / 已保存配置正在使用此驱动，请先更改配置。")
        # Delete only the selected executable; metadata or sibling files remain.
        candidate.unlink()
        try:
            candidate.parent.rmdir()
        except OSError:
            pass


@_public_api
def import_driver(path, driver_kind) -> str:
    if driver_kind not in DRIVER_NAMES or driver_kind == "safaridriver":
        raise ValueError("Safari uses its built-in driver; select another driver kind / Safari 使用内置驱动。")
    source = Path(path).expanduser().resolve()
    version = _driver_details(source, driver_kind)
    destination = storage_root() / "drivers" / driver_kind / version / (driver_kind + (".exe" if platform.system() == "Windows" else ""))
    if source == destination.resolve():
        return str(destination)
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".driver-", dir=destination.parent)
        os.close(fd)
        temporary = Path(name)
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
        return str(destination)
    except OSError:
        raise ValueError("Could not import this driver / 无法导入此驱动。") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _manager(profile, browser_version, allow_download):
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        binary = SeleniumManager._get_binary()
        browser = {"chromedriver": "chrome", "msedgedriver": "edge", "geckodriver": "firefox"}[profile["driver_kind"]]
        cache = storage_root() / "selenium"
        cache.mkdir(parents=True, exist_ok=True)
        # Manager loads configuration before applying CLI options, and some
        # flags (force-browser-download/clear-cache) cannot be negated on CLI.
        # Accept connection settings but never version, path or download policy
        # overrides from either configuration file it may read.
        connection_keys = {"proxy", "timeout", "driver-mirror-url", "chromedriver-mirror-url",
                           "msedgedriver-mirror-url", "geckodriver-mirror-url"}
        for config in (Path.home() / ".cache" / "selenium" / "se-config.toml", cache / "se-config.toml"):
            if config.is_file():
                values = tomllib.loads(config.read_text(encoding="utf-8"))
                if set(values) - connection_keys:
                    raise ValueError
        args = [binary, "--browser", browser, "--browser-path", profile["executable"],
                "--browser-version", browser_version, "--avoid-browser-download", "--skip-browser-in-path",
                "--skip-driver-in-path", "--avoid-stats", "--cache-path", cache,
                "--timeout", "45", "--language-binding", "python", "--output", "json"]
        if not allow_download:
            args.append("--offline")
        env = {key: val for key, val in os.environ.items() if not key.startswith("SE_")}
        result = _run(args, timeout=55, env=env)
        data = json.loads(result.stdout)["result"]
        if result.returncode or data.get("code", 0) or not data.get("driver_path"):
            raise ValueError
        returned_browser = data.get("browser_path")
        if returned_browser and Path(returned_browser).resolve() != Path(profile["executable"]).resolve():
            raise ValueError
        return str(Path(data["driver_path"]).expanduser().resolve())
    except (ImportError, OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise ValueError("Could not obtain a matching driver for the selected executable; import one manually / 无法获取与所选浏览器匹配的驱动，请手动导入。") from None
    except Exception:
        raise ValueError("Selenium Manager is unavailable; import a matching driver manually / Selenium Manager 不可用，请手动导入匹配驱动。") from None


@_public_api
def resolve_profile(profile, allow_download=False) -> dict:
    p = _normalise(profile)
    p["executable"] = str(browser_executable(p["executable"]))
    version = _browser_version(Path(p["executable"]), p["browser"])
    # Marketing versions of 360/custom products need not match their engines.
    if p["browser"] in ("360e", "custom"):
        engine = p.get("engine_version", "")
        version = engine if isinstance(engine, str) and _VERSION.fullmatch(engine) else None
    p["browser_version"] = version
    kind = p["driver_kind"]
    if kind == "safaridriver":
        if platform.system() != "Darwin":
            raise ValueError("Safari is available only on macOS / Safari 仅支持 macOS。")
        expected = Path("/Applications/Safari.app/Contents/MacOS/Safari").resolve()
        if Path(p["executable"]) != expected:
            raise ValueError("Built-in SafariDriver requires the installed system Safari / 内置 SafariDriver 需要系统 Safari。")
        driver = Path(p["driver_path"]).expanduser() if p["driver_mode"] == "manual" and p["driver_path"] else Path("/usr/bin/safaridriver")
        if driver.resolve() != Path("/usr/bin/safaridriver").resolve() or not driver.is_file():
            raise ValueError("Use the built-in SafariDriver / 请使用内置 SafariDriver。")
        return {**p, "driver_path": str(driver), "driver_version": version}
    if p["driver_mode"] == "manual":
        if not p["driver_path"]:
            raise ValueError("Select a manual driver path / 请选择手动驱动路径。")
        path = str(Path(p["driver_path"]).expanduser().resolve())
        driver_version = _driver_details(path, kind)
        _check_compatibility(kind, version, driver_version)
        return {**p, "driver_path": path, "driver_version": driver_version}
    if not version:
        raise ValueError("Cannot determine this browser's engine version; choose a matching manual driver (360/custom is experimental) / 无法确定浏览器内核版本，请手动选择匹配驱动。")
    candidates = []
    if p["driver_path"]:
        candidates.append(p["driver_path"])
    rows = [row for row in driver_library() if row["kind"] == kind and row.get("path")]
    rows.sort(key=lambda row: _version_tuple(row["version"]) if re.fullmatch(r"\d+(?:\.\d+)+", row.get("version", "")) else (), reverse=True)
    candidates.extend(row["path"] for row in rows)
    for path in dict.fromkeys(candidates):
        try:
            driver_version = _driver_details(path, kind)
            _check_compatibility(kind, version, driver_version)
            return {**p, "driver_path": str(Path(path).resolve()), "driver_version": driver_version}
        except ValueError:
            continue
    if not allow_download:
        raise ValueError("Matching driver is missing; use Download matching driver or import one / 缺少匹配驱动，请下载或手动导入。")
    path = _manager(p, version, True)
    driver_version = _driver_details(path, kind)
    _check_compatibility(kind, version, driver_version)
    return {**p, "driver_path": path, "driver_version": driver_version}


def launch_browser(profile, headless=False, profile_dir=None):
    """Launch exactly the resolved browser, without implicit downloads."""
    p = resolve_profile(profile, allow_download=False)
    kind = p["driver_kind"]
    if kind == "safaridriver" and headless:
        raise ValueError("Safari does not support headless mode / Safari 不支持无头模式。")
    try:
        from selenium import webdriver
        from selenium.common.exceptions import SessionNotCreatedException
        if kind == "safaridriver":
            from selenium.webdriver.safari.options import Options
            from selenium.webdriver.safari.service import Service
            options = Options()
            constructor = webdriver.Safari
        else:
            if kind == "geckodriver":
                from selenium.webdriver.firefox.options import Options
                from selenium.webdriver.firefox.service import Service
                constructor = webdriver.Firefox
            elif kind == "msedgedriver":
                from selenium.webdriver.edge.options import Options
                from selenium.webdriver.edge.service import Service
                constructor = webdriver.Edge
            else:
                from selenium.webdriver.chrome.options import Options
                from selenium.webdriver.chrome.service import Service
                constructor = webdriver.Chrome
            options = Options()
            options.binary_location = p["executable"]
            if headless:
                options.add_argument("-headless" if kind == "geckodriver" else "--headless=new")
            if profile_dir is not None:
                directory = Path(profile_dir).expanduser().resolve()
                if directory == storage_root().resolve() or storage_root().resolve() in directory.parents:
                    raise ValueError("Student browser data requires a separate temporary directory / 学生浏览器数据需要独立临时目录。")
                directory.mkdir(parents=True, exist_ok=True)
                if kind == "geckodriver":
                    options.add_argument("-profile")
                    options.add_argument(str(directory))
                else:
                    options.add_argument("--user-data-dir=" + str(directory))
        options.page_load_strategy = "eager"
        service = Service(executable_path=p["driver_path"], log_output=subprocess.DEVNULL)
        # env_path() otherwise overrides even an explicitly supplied Service.
        service.DRIVER_PATH_ENV_KEY = None
        service.path = p["driver_path"]
        driver = constructor(service=service, options=options)
        try:
            driver.set_script_timeout(30)
        except Exception:
            driver.quit()
            raise
        return driver
    except ImportError:
        raise ValueError("Selenium 4 is required / 需要安装 Selenium 4。") from None
    except SessionNotCreatedException as exc:
        if kind == "safaridriver" and "allow remote automation" in str(exc).lower():
            raise ValueError(
                "Safari requires remote automation. Enable Safari → Settings → Developer → "
                "Allow remote automation, then retry / Safari 需要远程自动化。请在 Safari → 设置 → "
                "开发者 中启用‘允许远程自动化’，然后重试。"
            ) from None
        raise ValueError("Could not launch the selected browser. Check its driver and automation permissions / 无法启动所选浏览器，请检查驱动与自动化权限。") from None
    except Exception:
        raise ValueError("Could not launch the selected browser. Check its driver and automation permissions / 无法启动所选浏览器，请检查驱动与自动化权限。") from None
