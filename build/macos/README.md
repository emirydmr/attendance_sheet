# macOS development

From the project root, run `./build/macos/run_local.command` for live login, or
append `--demo --photo-popup` for fictitious data and the image-import popup.
The launcher prefers `build/macos/.venv`, falling back to the existing project
`.venv`. Both source and packaged app require installed Google Chrome for login
and PDF rendering. No browser is bundled or downloaded at launch.
See the root README for the prepared (not yet verified) macOS `.app` build recipe.
