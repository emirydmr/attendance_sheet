#!/bin/zsh
# No automatic browser downloads; prepare Python packages only with opt-in.
set -eu
build_dir="${0:A:h}"
project_dir="${0:A:h:h:h}"
cd "$project_dir"
python_bin="$build_dir/.venv/bin/python"
mode="build"
downloads_ready=0
browser_profile=""
for argument in "$@"; do
  case "$argument" in
    --prepare) mode="prepare" ;;
    --check) mode="check" ;;
    --downloads-ready) downloads_ready=1 ;;
    --browser=*) browser_profile="${argument#--browser=}" ;;
    --help)
      print 'Usage: build_macos.command [--prepare --downloads-ready | --check] [--browser=/absolute/profile.json]'
      print 'Default: offline package build; no browser inspection. Optional profile smoke never downloads.'
      exit 0 ;;
    *) print -u2 "Unknown argument: $argument"; exit 1 ;;
  esac
done
if [[ "$mode" == prepare ]]; then
  if [[ "$downloads_ready" != 1 ]]; then
    print 'Preparation downloads Python packages including Selenium and PyInstaller, without a browser or Node.'
    print 'Run it yourself when ready: --prepare --downloads-ready. Nothing downloaded.'
    exit 0
  fi
  bootstrap_python="${PYTHON_BIN:-python3}"
  "$bootstrap_python" -c 'import sys, tkinter; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 with Tk"'
  if [[ ! -x "$python_bin" ]]; then
    "$bootstrap_python" -m venv "$build_dir/.venv"
  fi
  "$python_bin" -m pip install -r "$build_dir/requirements-build.txt"
  "$python_bin" -m pip check
  print 'Dependencies prepared. No browser downloaded.'
  exit 0
fi
if [[ ! -x "$python_bin" ]]; then
  print -u2 'Missing Mac build environment. First run --prepare --downloads-ready.'
  exit 1
fi
preflight=(--require-build)
if [[ -n "$browser_profile" ]]; then
  preflight+=(--browser "$browser_profile")
fi
if ! "$python_bin" "$project_dir/build/check_environment.py" "${preflight[@]}"; then
  print -u2 'Preflight failed. Nothing downloaded.'
  exit 1
fi
if [[ "$mode" == check ]]; then
  exit 0
fi
"$python_bin" -m unittest discover -s tests -p 'test_*.py'
"$python_bin" tests/check_gui.py
"$python_bin" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx \
  --additional-hooks-dir "$project_dir/build/hooks" --collect-all tkinterdnd2 \
  --exclude-module playwright --exclude-module pytest \
  --add-data "$project_dir/app/templates:templates" --add-data "$project_dir/app/assets:assets" \
  --icon "$project_dir/app/assets/icons/chu_red.png" \
  --specpath "$build_dir" --workpath "$build_dir/work" --distpath "$build_dir/dist" \
  --name AttendanceBook "$project_dir/app/main.py"
"$python_bin" "$project_dir/build/verify_package.py" "$build_dir/dist/AttendanceBook.app"
"$python_bin" "$project_dir/build/run_frozen_self_test.py" "$build_dir/dist/AttendanceBook.app/Contents/MacOS/AttendanceBook" --output "$build_dir/frozen-self-test.json"
archive="$build_dir/dist/AttendanceBook-macos-$(uname -m).zip"
ditto -c -k --sequesterRsrc --keepParent "$build_dir/dist/AttendanceBook.app" "$archive"
"$python_bin" "$project_dir/build/check_environment.py" --require-build --artifact "$archive" --report "$build_dir/build-report.json"
print "Package created: $archive (unsigned)."
