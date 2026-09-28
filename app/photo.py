"""Explicit, popup-only image import. No clipboard polling or URL downloads."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import warnings

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 25_000_000
FORMATS = {"PNG", "JPEG", "WEBP", "BMP", "TIFF", "GIF"}
FILE_TYPES = [("Images / 图片", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif")]


@dataclass(frozen=True)
class StudentPhoto:
    png: bytes
    width: int
    height: int

    @property
    def data_url(self):
        return "data:image/png;base64," + base64.b64encode(self.png).decode("ascii")


def normalize_photo(source):
    from PIL import Image, ImageOps
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            if isinstance(source, Image.Image):
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("Image is too large / 图片尺寸过大。")
                image = source.copy()
            else:
                raw = bytes(source)
                if len(raw) > MAX_FILE_BYTES:
                    raise ValueError("Image exceeds 20 MB / 图片超过20 MB。")
                with Image.open(BytesIO(raw)) as original:
                    if original.format not in FORMATS:
                        raise ValueError("Unsupported image format / 不支持的图片格式。")
                    if original.width * original.height > MAX_PIXELS:
                        raise ValueError("Image is too large / 图片尺寸过大。")
                    original.seek(0)  # Animated images use the first frame.
                    image = ImageOps.exif_transpose(original).convert("RGBA")
            image = ImageOps.exif_transpose(image).convert("RGBA")
            image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            # White background; preserve proportions, never crop or stretch faces.
            flattened = Image.new("RGB", image.size, "white")
            flattened.paste(image, mask=image.getchannel("A"))
            output = BytesIO()
            flattened.save(output, format="PNG")  # Fresh image strips EXIF/GPS metadata.
            return StudentPhoto(output.getvalue(), flattened.width, flattened.height)
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise ValueError("Image is too large / 图片尺寸过大。") from exc
        except (OSError, SyntaxError) as exc:
            raise ValueError("Not a supported image / 无法读取图片。") from exc


def photo_from_file(path):
    file = Path(path)
    if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Select an image file under 20 MB / 请选择小于20 MB的图片文件。")
    return normalize_photo(file.read_bytes())


def photo_from_clipboard():
    from PIL import Image, ImageGrab
    content = ImageGrab.grabclipboard()
    if isinstance(content, Image.Image):
        return normalize_photo(content)
    if isinstance(content, list) and len(content) == 1:
        return photo_from_file(content[0])
    raise ValueError("Clipboard has no image. In Chrome choose Copy image, not Copy image address. / 剪贴板中没有图片。请在Chrome中选择复制图片，而不是复制图片地址。")


def create_root():
    import tkinter as tk
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        return tk.Tk()
    return TkinterDnD.Tk()


class PhotoDialog:
    """Photo replacement is committed only by Use photo; Cancel keeps old photo."""
    def __init__(self, parent, current, on_commit, chinese=False):
        import tkinter as tk
        from tkinter import ttk
        self.parent, self.current, self.pending = parent, current, current
        self.on_commit, self.chinese = on_commit, chinese
        self.window = tk.Toplevel(parent)
        self.window.title(self.t("Add student photo", "添加学生照片"))
        self.window.geometry("530x560")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        body = ttk.Frame(self.window, padding=20)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=self.t("Drop, paste, or select a photo", "拖入、粘贴或选择照片"), font=("TkDefaultFont", 16, "bold")).pack(pady=(0, 12))
        self.target = tk.Canvas(body, width=470, height=270, background="#f5f8fb", highlightthickness=1, highlightbackground="#c2ccd6")
        self.target.pack(fill="x")
        self.hint = ttk.Label(body, wraplength=460)
        self.hint.pack(pady=8)
        self.drop_ready = False
        try:
            from tkinterdnd2 import DND_FILES
            self.target.tk.call("package", "present", "tkdnd")
            self.target.drop_target_register(DND_FILES)
            self.target.dnd_bind("<<Drop>>", self.drop)
            self.drop_ready = True
        except (ImportError, tk.TclError, AttributeError):
            pass
        self.hint.configure(text=self.t("Drop one image file here. Ctrl+V / ⌘V pastes while this popup is active.", "拖入一张图片。本窗口处于前台时，Ctrl+V / ⌘V 可粘贴图片。") if self.drop_ready else
            self.t("Drag-and-drop is unavailable until tkinterdnd2 is installed. File selection and paste still work.", "尚未安装拖放组件，暂时不能拖入图片。仍可选择文件或粘贴图片。"))
        row = ttk.Frame(body)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text=self.t("Choose file…", "选择文件…"), command=self.choose).pack(side="left")
        ttk.Button(row, text=self.t("Paste image", "粘贴图片"), command=self.paste).pack(side="left", padx=10)
        ttk.Button(row, text=self.t("Remove", "移除"), command=self.remove).pack(side="right")
        self.status = ttk.Label(body, wraplength=460, foreground="#555")
        self.status.pack(anchor="w", pady=10)
        bottom = ttk.Frame(body)
        bottom.pack(fill="x", pady=8)
        ttk.Button(bottom, text=self.t("Cancel", "取消"), command=self.cancel).pack(side="right")
        ttk.Button(bottom, text=self.t("Use photo", "使用照片"), command=self.commit).pack(side="right", padx=10)
        # Only this toplevel gets paste bindings. No global hotkeys/clipboard watcher.
        self.window.bind("<Control-v>", self.paste)
        self.window.bind("<Command-v>", self.paste)
        self.window.bind("<<Paste>>", self.paste)
        self.window.bind("<Escape>", lambda _: self.cancel())
        self.render()
        self.window.grab_set()
        self.window.focus_set()

    def t(self, english, chinese):
        return chinese if self.chinese else english

    def active(self):
        focused = self.window.focus_displayof()
        return focused is not None and focused.winfo_toplevel() == self.window

    def render(self):
        self.target.delete("all")
        if self.pending:
            from PIL import Image, ImageTk
            image = Image.open(BytesIO(self.pending.png))
            image.thumbnail((200, 235), Image.Resampling.LANCZOS)
            self.preview = ImageTk.PhotoImage(image, master=self.window)
            self.target.create_image(235, 130, image=self.preview)
            self.status.configure(text=f"{self.pending.width} × {self.pending.height} px · PNG")
        else:
            # Vector drop symbol, independent of emoji fonts.
            self.target.create_rectangle(200, 95, 270, 158, outline="#66849c", width=2, dash=(5, 3))
            self.target.create_line(235, 55, 235, 120, arrow="last", fill="#66849c", width=3)
            self.target.create_text(235, 195, text=self.t("Drop image here", "将图片拖到这里"), fill="#50677a", font=("TkDefaultFont", 13))
            self.status.configure(text=self.t("No photo selected", "尚未选择照片"))

    def accept(self, photo):
        self.pending = photo
        self.render()

    def fail(self, exc):
        self.status.configure(text=str(exc) if isinstance(exc, ValueError) else self.t("Unable to read image or clipboard", "无法读取图片或剪贴板"))

    def choose(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self.window, title=self.t("Select student photo", "选择学生照片"), filetypes=FILE_TYPES)
        if path:
            try:
                self.accept(photo_from_file(path))
            except Exception as exc:
                self.fail(exc)

    def paste(self, event=None):
        if not self.active():
            return "break"
        try:
            self.accept(photo_from_clipboard())
        except Exception as exc:
            self.fail(exc)
        return "break"

    def drop(self, event):
        try:
            paths = self.window.tk.splitlist(event.data)
            if len(paths) != 1:
                raise ValueError("Drop exactly one image / 请只拖入一张图片。")
            self.accept(photo_from_file(paths[0]))
        except Exception as exc:
            self.fail(exc)
        return "copy"

    def remove(self):
        self.pending = None
        self.render()

    def commit(self):
        self.on_commit(self.pending)
        self.cancel()

    def cancel(self):
        self.window.grab_release()
        self.window.destroy()
