"""Native Tk window branding from bundled assets; SVG stays the source."""
import tkinter as tk

from document import resource_root


def apply_icon(root):
    icon = tk.PhotoImage(master=root, file=str(resource_root() / 'assets' / 'icons' / 'chu_red.png'))
    root.iconphoto(True, icon)
    # Tk needs a live Python reference; True also sets the default for dialogs.
    root._attendance_icon = icon
    return icon
