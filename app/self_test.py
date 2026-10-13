"""Offline frozen-runtime check: assets, Tk/DnD and Selenium Manager, no browser."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys


def run_self_test(output=None):
    """Write a machine-readable report and return a process exit status."""
    checks, errors = {}, []
    try:
        from document import resource_root, font_css
        root = resource_root()
        required = ('templates/attendance_blueprint.html', 'templates/layout.js',
                    'assets/fonts/AttendanceCJK.otf', 'assets/fonts/LICENSE.txt',
                    'assets/fonts/FONT_INFO.txt', 'assets/icons/chu_red.png', 'assets/icons/chu_red.ico')
        missing = [name for name in required if not (root / name).is_file()]
        if missing:
            raise ValueError('Missing packaged resources: ' + ', '.join(missing))
        font = root / 'assets/fonts/AttendanceCJK.otf'
        if hashlib.sha256(font.read_bytes()).hexdigest() != 'e8f396decc1f0963a016a989c3d8852e863d1350996f573860a80767c83a1cd3':
            raise ValueError('Packaged font differs from the verified source asset.')
        if 'data:font/otf;base64,' not in font_css():
            raise ValueError('Packaged font cannot be embedded in the document.')
        checks['assets_and_font'] = 'passed'
    except Exception as exc:
        errors.append(f'Assets: {type(exc).__name__}: {exc}')
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        manager = Path(SeleniumManager._get_binary())
        if not manager.is_file():
            raise ValueError('Packaged Selenium Manager is missing.')
        if getattr(sys, 'frozen', False) and Path(sys._MEIPASS).resolve() not in manager.resolve().parents:
            raise ValueError('Selenium Manager resolved outside the frozen package.')
        result = subprocess.run([str(manager), '--version'], capture_output=True, text=True,
                                timeout=15, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        if 'selenium-manager' not in result.stdout.lower():
            raise ValueError('Packaged Selenium Manager did not report its version.')
        checks['selenium_manager'] = result.stdout.strip()
    except Exception as exc:
        errors.append(f'Selenium Manager: {type(exc).__name__}: {exc}')
    tk_root = None
    try:
        from photo import create_root
        from branding import apply_icon
        tk_root = create_root()
        tk_root.withdraw()
        apply_icon(tk_root)
        tk_root.update_idletasks()
        checks['tk'] = str(tk_root.tk.call('info', 'patchlevel'))
        checks['tkdnd'] = str(tk_root.tk.call('package', 'present', 'tkdnd'))
        icon = tk_root._attendance_icon
        if (icon.width(), icon.height()) != (256, 256):
            raise ValueError('Packaged icon has incorrect dimensions.')
        checks['icon'] = 'passed'
    except Exception as exc:
        errors.append(f'Tk / drag-and-drop / icon: {type(exc).__name__}: {exc}')
    finally:
        if tk_root is not None:
            tk_root.destroy()
    report = {'ok': not errors, 'frozen': bool(getattr(sys, 'frozen', False)),
              'python': platform.python_version(), 'architecture': platform.machine(),
              'browser_launched': False, 'downloads': False, 'checks': checks, 'errors': errors}
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if output is not None:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(serialized, encoding='utf-8')
    if sys.stdout is not None:
        print(serialized)
    return int(bool(errors))
