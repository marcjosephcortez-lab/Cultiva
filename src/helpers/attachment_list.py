

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import config
import db
import theme
from helpers import attachments

try:
    from PIL import Image, ImageTk
except ImportError:  
    Image = ImageTk = None

THUMB = 56          
_thumb_cache = {}   


def _load_thumbnail_image(path):

    if Image is None:
        return None
    try:
        key = (str(path), Path(path).stat().st_mtime_ns)
    except OSError:
        return None
    if key in _thumb_cache:
        return _thumb_cache[key]
    try:
        with Image.open(path) as picture:
            picture.draft("RGB", (THUMB * 2, THUMB * 2))  
            picture.thumbnail((THUMB, THUMB))
            small = picture.convert("RGBA")                
    except Exception:  
        small = None
    if len(_thumb_cache) > 200:
        _thumb_cache.clear()
    _thumb_cache[key] = small
    return small


class AttachmentList(ttk.Frame):


    def __init__(self, parent, owner_kind, editable=False, height=140):
        super().__init__(parent)
        self.owner_kind = owner_kind        
        self.editable = editable
        self._existing = []                 
        self._pending = []                  
        self._removed = set()               
        self._images = []                   
        self._error = ""
        self._build(height)
        self.render()

    def _build(self, height):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 4))
        self.heading = ttk.Label(top, text="Attachments", style="Header.TLabel")
        self.heading.pack(side="left")
        if self.editable:
            ttk.Button(top, text="Add file...", style="Soft.TButton",
                       command=self.choose_files).pack(side="right")
            ttk.Label(
                self, style="Muted.TLabel",
                text="Pictures and documents, up to %d MB each. Files are copied "
                     "when you press Save." % config.MAX_UPLOAD_MB,
            ).pack(anchor="w", pady=(0, 4))

        box = ttk.Frame(self)
        box.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(box, height=height, background=theme.colors()["bg"],
                                highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(box, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._window, width=e.width))
        self._bind_wheel(self.canvas)
        self._bind_wheel(self.inner)

    def _bind_wheel(self, widget):

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(sequence, self._on_wheel, add="+")

    def _bind_wheel_tree(self, widget):
        self._bind_wheel(widget)
        for child in widget.winfo_children():
            self._bind_wheel_tree(child)

    def _on_wheel(self, event):
        if event.num == 4:        
            step = -1
        elif event.num == 5:      
            step = 1
        else:                     
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def load(self, owner_id):

        self._pending = []
        self._removed = set()
        self._error = ""
        self._existing = []
        if owner_id is not None:
            try:
                self._existing = attachments.list_attachments(self.owner_kind, owner_id)
            except db.DBError as exc:
                self._error = "Could not load the files: " + str(exc)
        self.render()

    def count(self):
        return len(self._items())

    def has_changes(self):
        return bool(self._pending or self._removed)

    def _items(self):

        items = []
        for row in self._existing:
            if row["id"] in self._removed:
                continue
            items.append({
                "id": row["id"], "name": row["original_name"], "size": row["size_bytes"],
                "path": attachments.stored_path(row["stored_name"]), "pending": None,
            })
        for entry in self._pending:
            items.append({
                "id": None, "name": entry["path"].name, "size": entry["size"],
                "path": entry["path"], "pending": entry,
            })
        return items

    def render(self):

        for child in self.inner.winfo_children():
            child.destroy()
        self._images = []

        items = self._items()
        self.heading.configure(
            text="Attachments (%d)" % len(items) if items else "Attachments")

        if self._error or not items:
            if self._error:
                text, style = self._error, "Error.TLabel"
            elif self.editable:
                text, style = "No files yet. Use 'Add file...' to attach one.", "Muted.TLabel"
            else:
                text, style = "No files attached.", "Muted.TLabel"
            ttk.Label(self.inner, text=text, style=style, padding=4,
                      wraplength=420, justify="left").pack(anchor="w")
        for item in items:
            self._build_row(item)
        self._bind_wheel_tree(self.inner)

    def _build_row(self, item):
        colors = theme.colors()
        row = ttk.Frame(self.inner, style="Card.TFrame", padding=4)
        row.pack(fill="x", padx=1, pady=2)

        self._thumbnail(row, item).pack(side="left", padx=(0, 8))

        text = ttk.Frame(row, style="Card.TFrame")
        text.pack(side="left", fill="x", expand=True)
        name = item["name"] if len(item["name"]) <= 38 else item["name"][:35] + "..."
        ttk.Label(text, text=name, style="Card.TLabel").pack(anchor="w")
        detail = attachments.format_size(item["size"])
        if item["pending"] is not None:
            detail += "  -  will be attached when you save"
        ttk.Label(text, text=detail, style="Card.TLabel",
                  foreground=colors["muted"]).pack(anchor="w")

        buttons = ttk.Frame(row, style="Card.TFrame")
        buttons.pack(side="right")
        ttk.Button(buttons, text="Open", style="Soft.TButton",
                   command=lambda i=item: self.open_item(i)).pack(side="left", padx=2)
        if self.editable:
            ttk.Button(buttons, text="Remove", style="Soft.TButton",
                       command=lambda i=item: self.remove_item(i)).pack(side="left", padx=2)

    def _thumbnail(self, parent, item):

        colors = theme.colors()
        square = tk.Canvas(parent, width=THUMB, height=THUMB, background=colors["tab_bg"],
                           highlightthickness=1, highlightbackground=colors["border"])
        extension = Path(item["name"]).suffix.lower()
        small = None
        if extension in attachments.IMAGE_EXTENSIONS:
            small = _load_thumbnail_image(item["path"])
        if small is not None and ImageTk is not None:
            photo = ImageTk.PhotoImage(small)
            self._images.append(photo)
            square.create_image(THUMB // 2, THUMB // 2, image=photo)
        else:
            label = extension.lstrip(".").upper()[:4] or "FILE"
            square.create_text(THUMB // 2, THUMB // 2, text=label, fill=colors["fg"],
                               font=(theme.font_family(), 10, "bold"))
        return square

    def choose_files(self):

        pictures = tuple("*" + e for e in attachments.IMAGE_EXTENSIONS)
        documents = tuple("*" + e for e in attachments.DOCUMENT_EXTENSIONS)
        picked = filedialog.askopenfilenames(
            parent=self.winfo_toplevel(), title="Choose files to attach",
            filetypes=[("Pictures and documents", pictures + documents),
                       ("Pictures", pictures), ("Documents", documents)])
        if isinstance(picked, str):  
            picked = self.tk.splitlist(picked)
        if picked:
            self.add_files(picked)

    def add_files(self, paths):

        problems = []
        known = {str(entry["path"]) for entry in self._pending}
        for raw in paths:
            path = Path(raw)
            if str(path) in known:
                continue  
            try:
                size = attachments.validate_file(path)
            except attachments.AttachmentError as exc:
                problems.append(str(exc))
                continue
            self._pending.append({"path": path, "size": size})
            known.add(str(path))
        self.render()
        if problems:
            messagebox.showwarning("Some files were not added", "\n\n".join(problems),
                                   parent=self.winfo_toplevel())

    def remove_item(self, item):

        if item["pending"] is not None:
            self._pending = [p for p in self._pending if p is not item["pending"]]
        else:
            self._removed.add(item["id"])
        self.render()

    def open_item(self, item):
        try:
            attachments.open_file(item["path"])
        except attachments.AttachmentError as exc:
            messagebox.showerror("Cannot open the file", str(exc),
                                 parent=self.winfo_toplevel())

    def apply(self, owner_id):

        problems = []
        for attachment_id in sorted(self._removed):
            try:
                attachments.delete_attachment(attachment_id)
            except db.DBError as exc:
                problems.append("Could not remove a file: %s" % exc)
        for entry in self._pending:
            try:
                attachments.add_attachment(self.owner_kind, owner_id, entry["path"])
            except (attachments.AttachmentError, db.DBError) as exc:
                problems.append(str(exc))
        return problems
