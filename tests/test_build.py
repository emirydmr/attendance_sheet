from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
from check_environment import ROOT, audit, pinned_requirements
from export_source import source_files


class BuildTests(unittest.TestCase):
    def test_source_handoff_excludes_private_and_generated_files(self):
        paths = [p.relative_to(ROOT) for p in source_files()]
        self.assertTrue(paths)
        for path in paths:
            self.assertFalse(set(path.parts) & {'poc', 'work', '.venv', '__pycache__', 'dist'})
            self.assertNotEqual(path.suffix, '.docx')
        self.assertIn(Path('build/windows/build_windows.ps1'), paths)
        self.assertIn(Path('app/assets/fonts/AttendanceCJK.otf'), paths)
        self.assertIn(Path('.gitignore'), paths)
        self.assertIn(Path('.gitattributes'), paths)
        self.assertIn(Path('build/hooks/hook-playwright.sync_api.py'), paths)

    def test_runtime_pins_cover_external_imports(self):
        self.assertEqual(set(pinned_requirements(ROOT / 'requirements.txt')),
                         {'playwright', 'beautifulsoup4', 'Pillow', 'tkinterdnd2'})

    def test_builder_pin_is_exact(self):
        self.assertEqual(pinned_requirements(ROOT / 'build/requirements-build.txt'),
                         {'pyinstaller': '6.22.3'})

    def test_local_assets_and_versions_pass(self):
        errors, versions, hashes = audit()
        self.assertEqual(errors, [])
        self.assertEqual(len(versions), 4)
        self.assertEqual(len(hashes), 8)

    def test_wrong_dependency_rejected(self):
        with patch('check_environment.metadata.version', return_value='0.0.0'):
            errors, _, _ = audit()
        self.assertEqual(len(errors), 4)

    def test_missing_assets_rejected(self):
        with patch('check_environment.Path.is_file', return_value=False):
            errors, _, _ = audit()
        self.assertEqual(len(errors), 8)

    def test_requirements_comments_and_nested_include(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'requirements.txt'
            path.write_text('# note\n-r elsewhere.txt\nthing==1.2\n')
            self.assertEqual(pinned_requirements(path), {'thing': '1.2'})


if __name__ == '__main__':
    unittest.main()
