# Test map

Routine offline checks (no university login or driver downloads):

```sh
python -m unittest discover -s tests -p 'test_*.py'
python tests/check_gui.py
```

The `test_*.py` files cover application logic, document generation, browser
profiles, and the browser-settings interface. `check_gui.py` exercises the
Tkinter flow without opening a real browser.

Browser-dependent checks are separate and opt-in:

- `smoke_selenium.py` uses a local-only website fixture and the selected
  installed browser; CI runs it before packaging.
- `manual/check_layout.py` and `manual/check_omit_empty.py` inspect printed
  layout and week omission with a real browser.
- `manual/render_sample.py` and `manual/render_photo_sample.py` create
  fictitious sample PDFs for visual review.
- `manual/live_portal_smoke.py` is the only check that opens the university
  portal; it requires explicit flags and interactive confirmation, and CI
  never runs it.

`browser_fixture.py` is shared test support, not a standalone check. The
manual scripts are not part of the default test discovery or build process.
See the main README for the opt-in live check command and browser setup.
