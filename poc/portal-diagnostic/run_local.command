#!/bin/zsh
# Local development launcher; it never installs packages or downloads a browser.
task_project_dir="${0:A:h}"
task_python="$task_project_dir/../.venv/bin/python"
if [[ ! -x "$task_python" ]]; then
    task_python='/Users/emirydmr/Documents/Codex/2026-09-28/wir-x20/work/portal-venv/bin/python'
fi
if [[ ! -x "$task_python" ]]; then
    print 'Python dependencies are not available. Set up the development environment first.'
    exit 1
fi
cd "$task_project_dir" || exit 1
exec "$task_python" app.py --system-chrome --report session_report.json
