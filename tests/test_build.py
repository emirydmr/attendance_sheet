from contextlib import redirect_stdout
import builtins
from io import StringIO
import json
import platform
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
from check_environment import ROOT, audit, main, pinned_requirements
from export_source import source_files
from verify_package import ASSETS, MODULES, verify_names


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.pins = pinned_requirements(ROOT / 'requirements.txt')
        self.versions = patch('check_environment.metadata.version',
                              side_effect=lambda name: self.pins[name])
        self.versions.start()
        self.addCleanup(self.versions.stop)
        baseline = patch('check_environment.sys.version_info', (3, 12, 0))
        baseline.start()
        self.addCleanup(baseline.stop)

    def test_source_handoff_excludes_private_and_generated_files(self):
        files = source_files()
        paths = [p.relative_to(ROOT) for p in files]
        self.assertTrue(paths)
        for path in paths:
            self.assertFalse(set(path.parts) & {'poc', 'work', '.venv', '__pycache__', 'dist', 'selenium-cache'})
            self.assertNotEqual(path.suffix, '.docx')
        for relative in ('build/windows/build_windows.ps1', 'app/assets/fonts/AttendanceCJK.otf',
                         '.gitignore', '.gitattributes', '.github/workflows/build-release.yml',
                         'build/hooks/hook-selenium.py', 'app/browser_settings.py',
                         'app/self_test.py', 'build/run_frozen_self_test.py',
                         'tests/smoke_selenium.py', 'build/prepare_ci_browser.py', 'build/verify_package.py'):
            self.assertIn(Path(relative), paths)
        self.assertNotIn(Path('build/hooks/hook-playwright.sync_api.py'), paths)
        self.assertTrue(all(p.is_file() for p in files), 'Every exported source must exist')

    def test_runtime_pins_cover_external_imports(self):
        self.assertEqual(set(self.pins), {'selenium', 'beautifulsoup4', 'Pillow', 'tkinterdnd2'})
        self.assertEqual(self.pins['selenium'], '4.51.0')

    def test_builder_pin_is_exact(self):
        self.assertEqual(pinned_requirements(ROOT / 'build/requirements-build.txt'),
                         {'pyinstaller': '6.22.3'})

    def test_selenium_hook_collects_only_target_manager_and_notices(self):
        import runpy
        from types import ModuleType
        # A Mac build's venv path contains /macos/ for *every* platform binary.
        # Selection must inspect the package-relative destination, not this path.
        hooks = ModuleType('PyInstaller.utils.hooks')
        managers = ['macos', 'windows', 'linux-arm64', 'linux-x86_64']
        hooks.collect_data_files = lambda _: [
            ('/project/build/macos/.venv/selenium/' + target + '/selenium-manager',
             'selenium/webdriver/common/' + target) for target in managers
        ] + [('/wheel/selenium-manager-THIRD-PARTY-NOTICES.txt', 'selenium/webdriver/common')]
        hooks.collect_submodules = lambda _: ['selenium.webdriver']
        with patch.dict(sys.modules, {'PyInstaller.utils.hooks': hooks}), \
             patch.object(platform, 'system', return_value='Darwin'):
            result = runpy.run_path(str(ROOT / 'build/hooks/hook-selenium.py'))
        self.assertEqual(len(result['binaries']), 1)
        self.assertTrue(result['binaries'][0][1].endswith('/macos'))
        self.assertTrue(any('THIRD-PARTY-NOTICES' in source for source, _ in result['datas']))

    def test_local_assets_and_versions_pass(self):
        errors, versions, hashes = audit()
        self.assertEqual(errors, [])
        self.assertEqual(versions, self.pins)
        self.assertEqual(len(hashes), 8)
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))

    def test_wrong_dependency_rejected(self):
        with patch('check_environment.metadata.version', return_value='0.0.0'):
            errors, _, _ = audit()
        self.assertEqual(len(errors), len(self.pins))
        self.assertTrue(all('expected' in error for error in errors))

    def test_missing_dependency_rejected(self):
        import importlib.metadata
        with patch('check_environment.metadata.version', side_effect=importlib.metadata.PackageNotFoundError):
            errors, _, _ = audit()
        self.assertEqual(len(errors), len(self.pins))
        self.assertTrue(all('missing' in error for error in errors))

    def test_missing_assets_rejected(self):
        with patch('check_environment.Path.is_file', return_value=False):
            errors, _, _ = audit()
        self.assertEqual(len(errors), 8)
        self.assertTrue(all('Missing asset:' in error for error in errors))

    def test_wrong_python_rejected(self):
        with patch('check_environment.sys.version_info', (3, 13, 0)):
            errors, _, _ = audit()
        self.assertTrue(any('Python 3.12' in error for error in errors))

    def test_requirements_comments_and_nested_include(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'requirements.txt'
            path.write_text('# note\n-r elsewhere.txt\nthing==1.2\n')
            self.assertEqual(pinned_requirements(path), {'thing': '1.2'})

    def test_static_preflight_does_not_import_browser_or_app(self):
        original = builtins.__import__
        forbidden = {'browser_config', 'browser_settings', 'selenium', 'document', 'photo', 'main'}
        def offline_import(name, *args, **kwargs):
            if name.split('.')[0] in forbidden:
                raise AssertionError('Static preflight inspected application/browser: ' + name)
            return original(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'preflight.json'
            with patch('builtins.__import__', side_effect=offline_import), redirect_stdout(StringIO()):
                self.assertFalse(main(['--report', str(report)]))
            details = json.loads(report.read_text(encoding='utf-8'))
            self.assertFalse(details['browser_checked'])
            self.assertEqual(details['errors'], [])

    def test_missing_artifact_fails(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(StringIO()):
            self.assertTrue(main(['--artifact', str(Path(directory) / 'missing.exe')]))

    def test_valid_package_assets_and_modules(self):
        names = list(ASSETS) + list(MODULES) + ['selenium/webdriver/common/windows/selenium-manager.exe']
        self.assertEqual(verify_names(names), [])
        self.assertEqual(verify_names(['Contents/Resources/' + n for n in ASSETS] +
                                      list(MODULES) + ['Contents/Frameworks/selenium/webdriver/common/macos/selenium-manager']), [])

    def test_incomplete_package_and_forbidden_runtime_fail(self):
        names = list(ASSETS) + list(MODULES) + ['selenium/webdriver/common/macos/selenium-manager']
        for forbidden in ('playwright/driver/node', 'node.exe', 'chrome.exe',
                          '.local-browsers/chromium/chrome', 'chromedriver.exe'):
            self.assertTrue(any('Unexpected bundled' in error for error in verify_names(names + [forbidden])))
        self.assertTrue(any('Manager is missing' in error for error in verify_names(list(ASSETS) + list(MODULES))))
        self.assertTrue(any('Missing bundled asset' in error for error in verify_names(list(MODULES))))


if __name__ == '__main__':
    unittest.main()
