"""Create a portable source handoff; exclude sessions, student records and venvs."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_APP_SUFFIXES = {'.py', '.html', '.js', '.svg', '.png', '.ico', '.otf', '.txt', '.md'}
BUILD_FILES = (
    'requirements-build.txt', 'check_environment.py', 'generate_icons.py',
    'export_source.py', 'macos/build_macos.command', 'macos/run_local.command',
    'macos/requirements-build.txt', 'macos/README.md',
    'windows/build_windows.ps1', 'windows/requirements-build.txt', 'windows/README.md',
    'hooks/hook-playwright.sync_api.py',
)


def source_files():
    files = [ROOT / 'README.md', ROOT / 'requirements.txt',
             ROOT / '.gitignore', ROOT / '.gitattributes']
    files += [p for p in (ROOT / 'app').rglob('*') if p.is_file()
              and p.suffix in ALLOWED_APP_SUFFIXES and '__pycache__' not in p.parts]
    files += [ROOT / 'build' / relative for relative in BUILD_FILES]
    files += list((ROOT / 'tests').glob('*.py'))
    return sorted(files)


def main():
    destination = ROOT / 'build/source/AttendanceBook-source.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in source_files():
            archive.write(path, 'AttendanceBook/' + path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Source archive verification failed')
    print(destination)
    print('Source only: no original DOCX, PoC reports, real-student exports, credentials or virtual environments.')


if __name__ == '__main__':
    main()
