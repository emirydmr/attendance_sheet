"""Offline Tk UI integration check; does not open the login browser."""
import sys
import time
import tempfile
from types import SimpleNamespace
from pathlib import Path
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from main import AttendanceApp
from test_photo import sample_photo
from photo import create_root

root = create_root()
root.withdraw()
app = AttendanceApp(root, demo=True)


def wait_done():
    deadline = time.monotonic() + 20
    while app.busy and time.monotonic() < deadline:
        root.update()
        time.sleep(.02)
    assert not app.busy, "UI worker timed out"


assert app.busy, 'Startup check must run asynchronously before other actions'
wait_done()
assert app.browser_state == 'available'
assert app.browser_status['text'].startswith('✓ ')
assert app.browser_version in app.browser_status['text']
assert 'check passed' in app.browser_status['text']
assert str(app.browser_status['foreground']) == '#167342'
assert 'Browser check passed' in app.status['text']
with patch('main.check_browser', side_effect=ValueError('Simulated missing browser')),      patch.object(app, 'locate_browser') as picker:
    app.submit('check_browser')
    wait_done()
    root.update_idletasks()
    picker.assert_called_once_with()
with patch('main.filedialog.askopenfilename', return_value=''):
    app.locate_browser()
    assert not app.busy
assert app.browser_state == 'unavailable'
assert app.browser_version == ''
assert str(app.browser_status['foreground']) == '#a52b28'
assert 'No automatic downloads' in app.browser_status['text']
app.language.set('中文')
app.translate()
assert '不会自动下载' in app.browser_status['text']
app.language.set('English')
app.translate()
app.submit('check_browser')
wait_done()
assert app.browser_state == 'available'
assert 'check_browser' not in app.errors
app.language.set('中文')
app.translate()
assert '检查成功' in app.browser_status['text']
assert app.browser_version in app.browser_status['text']
app.language.set('English')
app.translate()
assert root._attendance_icon.width() == 256
assert root._attendance_icon.height() == 256
assert len(app.help_controls) == 12
assert 'language' not in app.help_controls
assert len(app.field_entries) == 10
assert app.vars['last'].get() == '18'
assert app.omit_empty_weeks.get()
for index, code in enumerate(('11', '12', '13')):
    app.semester_dropdown.current(index)
    app.semester_dropdown.event_generate('<<ComboboxSelected>>')
    assert app.selection()[1] == int(code)
    english_label = app.semester_label.get()
    app.language.set('中文')
    app.translate()
    assert app.selection()[1] == int(code)
    assert app.semester_label.get() == ('第一学期', '第二学期', '短学期')[index]
    app.language.set('English')
    app.translate()
    assert app.semester_label.get() == english_label
app.vars['term'].set('11')
assert app.semester_label.get() == 'First semester'
app.set_busy(True)
assert str(app.semester_dropdown['state']) == 'disabled'
app.set_busy(False)
assert str(app.semester_dropdown['state']) == 'readonly'
help_window = app.show_field_help('term')
assert help_window.winfo_exists()
help_window.destroy()
app.show_help_tip('year', 20, 20)
assert app.tip.winfo_exists()
app.hide_tooltip()
assert app.tip is None
app.show_font_license()
licence_window = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
licence_text = next(w for w in licence_window.winfo_children() if isinstance(w, tk.Text))
assert 'SIL OPEN FONT LICENSE' in licence_text.get('1.0', 'end')
licence_window.destroy()


for key in ("identity", "names", "weeks"):
    app.retrieve(key)
    wait_done()
    assert app.states[key] == "success", (key, app.errors)
assert app.payload()["student_id"] == "DEMO001"
assert app.payload()['omit_empty_weeks'] is True
app.omit_empty_checkbox.invoke()
assert app.payload()['omit_empty_weeks'] is False
assert len(app.payload()['weeks']) == 18, 'Output filter must retain the complete scan'
assert all(state == 'success' for state in app.states.values())
app.language.set('中文')
app.translate()
assert app.omit_empty_checkbox['text'] == '省略无课周'
assert not app.omit_empty_weeks.get()
app.omit_empty_checkbox.invoke()
assert app.payload()['omit_empty_weeks'] is True
app.language.set('English')
app.translate()
app.submit('check_browser')
wait_done()
assert app.payload()['student_id'] == 'DEMO001', 'Checking browser must preserve student data'
app.language.set("中文")
app.translate()
assert app.badges["identity"]["text"] == "成功 · 点击查看"
assert all(state == 'success' for state in app.states.values())
app.semester_dropdown.current(1)
app.semester_dropdown.event_generate('<<ComboboxSelected>>')
assert app.selection()[1] == 12
assert all(state == 'missing' for state in app.states.values())
for key in ('identity', 'names', 'weeks'):
    app.retrieve(key)
    wait_done()
    assert app.states[key] == 'success', (key, app.errors)
assert app.payload()['term'] == 12
app.vars["last"].set("20")
assert app.states["weeks"] == "missing"
try:
    app.payload()
except ValueError:
    pass
else:
    raise AssertionError("Stale timetable export accepted")
app.retrieve("weeks")
wait_done()
assert len(app.payload()["weeks"]) == 20
assert "学号: DEMO001" in app.display_result("identity")
app.add_photo()
dialog = app.photo_dialog
assert dialog.window.winfo_exists()
assert dialog.drop_ready, "Native drop target should be registered"
with patch("photo.PhotoDialog.active", return_value=False), patch("photo.photo_from_clipboard") as read_clipboard:
    dialog.paste()
    read_clipboard.assert_not_called()
with patch("photo.PhotoDialog.active", return_value=True), patch("photo.photo_from_clipboard", return_value=sample_photo()) as read_clipboard:
    dialog.paste()
    read_clipboard.assert_called_once()
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / "portrait with spaces.png"
    source.write_bytes(sample_photo().png)
    drop_data = dialog.window.tk.call("list", str(source))
    dialog.pending = None
    dialog.drop(SimpleNamespace(data=drop_data))
    assert dialog.pending is not None, dialog.status["text"]
    assert dialog.pending.width == 120
dialog.commit()
assert app.photo.width == 120
app.add_photo()
dialog = app.photo_dialog
dialog.remove()
dialog.cancel()
assert app.photo is not None, "Cancel should preserve the existing photo"
assert app.payload()["photo"] is app.photo
with patch("main.filedialog.asksaveasfilename", return_value="") as save_dialog:
    app.export()
    assert save_dialog.call_args.kwargs["initialfile"] == "DEMO001_长安大学国际学生考勤册.pdf"
with patch("main.filedialog.asksaveasfilename", return_value="") as save_dialog:
    app.export("browser_print")
    assert save_dialog.call_args.kwargs["initialfile"] == "DEMO001_长安大学国际学生考勤册.html"
app.inspect("identity")
assert any(isinstance(w, tk.Toplevel) for w in root.winfo_children())
for child in root.winfo_children():
    if isinstance(child, tk.Toplevel):
        child.destroy()
app.submit("end")
wait_done()
assert not app.results and not app.data
assert app.photo is None, "Photo must not carry over to the next student"
app.close()
deadline = time.monotonic() + 5
while app.thread.is_alive() and time.monotonic() < deadline:
    root.update()
    time.sleep(.02)
assert not app.thread.is_alive()
print("GUI checks passed: retrieval, results, language switch, invalidation, session cleanup.")
