"""Run a GUI executable synchronously and require a fresh frozen self-test report."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(artifact, output):
    artifact, output = artifact.resolve(), output.resolve()
    if not artifact.is_file():
        raise ValueError('Frozen executable is missing: ' + str(artifact))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.frozen-check-', dir=output.parent) as directory:
        staging = Path(directory) / 'self-test.json'
        subprocess.run([str(artifact), '--self-test', str(staging)],
                       timeout=60, check=True)
        report = json.loads(staging.read_text(encoding='utf-8'))
        if (report.get('ok') is not True or report.get('frozen') is not True
                or report.get('browser_launched') is not False or report.get('downloads') is not False
                or report.get('errors') != []):
            raise ValueError('Frozen self-test report failed validation: ' + str(report))
        os.replace(staging, output)
    print('Frozen Tk, drag-and-drop, font, icon and Selenium Manager passed: ' + str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.artifact, args.output)


if __name__ == '__main__':
    main()
