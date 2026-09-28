#!/bin/zsh
set -eu
project_dir="${0:A:h:h:h}"
python_bin="$project_dir/build/macos/.venv/bin/python"
legacy_environment=0
if [[ ! -x "$python_bin" ]]; then
  python_bin="$project_dir/.venv/bin/python"
  legacy_environment=1
fi
if [[ ! -x "$python_bin" ]]; then
  print "Development Python environment is missing. No downloads were started."
  exit 1
fi
cd "$project_dir"
# Reuse the already bundled Pillow for Mac development only; never install it.
bundled_packages="/Users/emirydmr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages"
if [[ "$legacy_environment" == 1 && -d "$bundled_packages/PIL" ]]; then
  export PYTHONPATH="$bundled_packages${PYTHONPATH:+:$PYTHONPATH}"
fi
exec "$python_bin" "$project_dir/app/main.py" --system-chrome "$@"
