

import tkinter as tk
from tkinter import messagebox, ttk

import db
import theme
import translations
from helpers import attachments, dialogs
from helpers.attachment_list import AttachmentList
from ui.entry_editor import open_editor

tr = translations.tr
SEARCH_DELAY_MS = 300   


class RecordTab(ttk.Frame):
    KIND = ""          
    NOUN = ""          
    NOUN_PLURAL = ""   

    def __init__(self, parent, app=None):
        super().__init__(parent, padding=10)
        self.app = app
        self._rows = {}            
        self._search_job = None    
        self._build()
        self.refresh()

        self.root = ttk.Frame.winfo_toplevel(self)
        self.auto_refresh()

    def heading_text(self):
        return self.NOUN_PLURAL.title()

    def build_header_extra(self, header):
        pass

    def columns(self):

        raise NotImplementedError

    def row_values(self, row):
        raise NotImplementedError

    def meta_text(self, row):
        return ""

    def load_rows(self, search):
        raise NotImplementedError

    def after_refresh(self):
        pass

    @staticmethod
    def links_text(row):

        parts = []
        if row.get("plot_name"):
            parts.append("%s: %s" % (tr("plot"), row["plot_name"]))
        if row.get("crop_name"):
            parts.append("%s: %s" % (tr("crop"), row["crop_name"]))
        return " | ".join(parts)

    def _build(self):
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=self.heading_text(), style="Title.TLabel").pack(side="left")
        self.build_header_extra(header)

        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        self.new_button = ttk.Button(toolbar, text="New " + self.NOUN, style="Accent.TButton",
                                     command=self.new_record)
        self.edit_button = ttk.Button(toolbar, text="Edit", command=self.edit_selected)
        self.delete_button = ttk.Button(toolbar, text="Delete", style="Danger.TButton",
                                        command=self.delete_selected)
        for button in (self.new_button, self.edit_button, self.delete_button):
            button.pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Clear", style="Soft.TButton",
                   command=self.clear_search).pack(side="right")
        self.search_var = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.search_var, width=28).pack(side="right", padx=(0, 6))
        ttk.Label(toolbar, text="Search:").pack(side="right", padx=(0, 6))
        self.search_var.trace_add("write", self._on_search_typed)

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

        left = ttk.Frame(panes)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        columns = self.columns()
        self.tree = ttk.Treeview(left, columns=[c[0] for c in columns], show="headings",
                                 selectmode="browse", height=14)
        for key, heading, width, anchor in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "title"))
        self.tree.tag_configure("alt", background=theme.colors()["row_alt"])
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.status_var = tk.StringVar()
        ttk.Label(left, textvariable=self.status_var, style="Muted.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        panes.add(left, weight=3)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        self.detail_title = ttk.Label(right, text="", style="Header.TLabel",
                                      wraplength=380, justify="left")
        self.detail_title.pack(anchor="w")
        self.detail_meta = ttk.Label(right, text="", style="Muted.TLabel",
                                     wraplength=380, justify="left")
        self.detail_meta.pack(anchor="w", pady=(2, 6))
        right.bind("<Configure>", self._on_detail_resize)

        text_box = ttk.Frame(right)
        text_box.pack(fill="both", expand=True)
        self.detail_text = tk.Text(text_box, height=8, wrap="word", state="disabled")
        theme.style_text(self.detail_text)
        text_scroll = ttk.Scrollbar(text_box, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=text_scroll.set)
        text_scroll.pack(side="right", fill="y")
        self.detail_text.pack(side="left", fill="both", expand=True)

        self.files = AttachmentList(right, self.KIND, editable=False, height=120)
        self.files.pack(fill="x", pady=(8, 0))
        panes.add(right, weight=2)

        self.tree.bind("<<TreeviewSelect>>", lambda event: self._on_select())
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", lambda event: self.edit_selected())
        self.tree.bind("<Delete>", lambda event: self.delete_selected())

    def _on_detail_resize(self, event):
        wrap = max(event.width - 30, 150)
        self.detail_title.configure(wraplength=wrap)
        self.detail_meta.configure(wraplength=wrap)

    def selected_id(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def selected_row(self):
        return self._rows.get(self.selected_id())

    def refresh(self, select_id=None):

        if not self.winfo_exists():
            return
        self._search_job = None
        keep = select_id or self.selected_id()
        search = self.search_var.get().strip()
        try:
            rows = self.load_rows(search)
        except db.DBError as exc:
            messagebox.showerror("Database problem", str(exc), parent=self.winfo_toplevel())
            return

        self._rows = {row["id"]: row for row in rows}
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(rows):
            self.tree.insert("", "end", iid=str(row["id"]), values=self.row_values(row),
                             tags=("alt",) if index % 2 else ())

        if rows:
            self.status_var.set("%d %s" % (len(rows), self.NOUN if len(rows) == 1 else self.NOUN_PLURAL))
        elif search:
            self.status_var.set("Nothing matches your search.")
        else:
            self.status_var.set("No %s yet. Click 'New %s' to add one." % (self.NOUN_PLURAL, self.NOUN))

        if keep in self._rows:
            self.tree.selection_set(str(keep))
            self.tree.see(str(keep))
        self._on_select()
        self.after_refresh()

    def _on_select(self):
        row = self.selected_row()
        self._show_detail(row)
        state = "!disabled" if row else "disabled"
        self.edit_button.state([state])
        self.delete_button.state([state])

    def _show_detail(self, row):
        if row is None:
            self.detail_title.configure(text="Nothing selected")
            self.detail_meta.configure(text="Pick one from the list to read it here.")
            self._set_detail_text("")
            self.files.load(None)
            return
        self.detail_title.configure(text=row["title"])
        self.detail_meta.configure(text=self.meta_text(row))
        self._set_detail_text(row["body"] or "(no text)")
        self.files.load(row["id"])

    def _set_detail_text(self, text):
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")   

    def _cancel_search_job(self):
        if self._search_job is not None:
            try:
                self.after_cancel(self._search_job)
            except tk.TclError:
                pass
            self._search_job = None

    def _on_search_typed(self, *_):
        self._cancel_search_job()
        self._search_job = self.after(SEARCH_DELAY_MS, self.refresh)

    def clear_search(self):
        self.search_var.set("")
        self._cancel_search_job()
        self.refresh()

    def destroy(self):
        self._cancel_search_job()   
        super().destroy()

    def new_record(self):
        open_editor(self, self.KIND, None, self._after_save)

    def edit_selected(self):
        row = self.selected_row()
        if row:
            open_editor(self, self.KIND, row, self._after_save)

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell":
            self.edit_selected()

    def _after_save(self, record_id):
        if not self.winfo_exists():
            return
        self.refresh(select_id=record_id)
        if record_id not in self._rows and self.search_var.get().strip():
            self.clear_search()                  
            self.refresh(select_id=record_id)

    def delete_selected(self):
        row = self.selected_row()
        if row is None:
            return
        label = row["title"]
        if row.get("files"):
            label += " (and its %d attached file%s)" % (row["files"], "" if row["files"] == 1 else "s")
        deleted = dialogs.delete_record(
            self.winfo_toplevel(), self.NOUN, label,
            delete_func=lambda: attachments.delete_owner(self.KIND, row["id"]))
        if deleted:
            self.refresh()

    def auto_refresh(self):
        self.refresh()
        self.root.after(5000, self.auto_refresh)
