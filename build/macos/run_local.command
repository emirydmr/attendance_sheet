#!/bin/zsh
set -eu
project_dir="${0:A:h:h:h}"
python_bin="$project_dir/build/macos/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  python_bin="$project_dir/.venv/bin/python"
fi
if [[ ! -x "$python_bin" ]]; then
  print "Development Python environment is missing. No downloads were started."
  exit 1
fi
cd "$project_dir"
exec "$python_bin" "$project_dir/app/main.py" "$@"
