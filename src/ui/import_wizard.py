"""Tkinter workflow for importing files into Cultiva's Library and data modules."""
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import db
from helpers import universal_import as importer


class ImportWizard(tk.Toplevel):
    def __init__(self, parent, on_complete=None):
        super().__init__(parent)
        self.title("Import resources")
        self.geometry("980x680")
        self.minsize(820, 560)
        self.transient(parent)
        self.grab_set()
        self.on_complete = on_complete
        self.path = None
        self.headers = []
        self.records = []
        self.mapping_vars = {}
        self.valid_rows = []
        self.issues = []
        self.duplicate_rows = []
        self.resource = None
        self._build()

    def _build(self):
        # Keep the action footer fixed while allowing the complete form to scroll.
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        scroll_area = ttk.Frame(outer)
        scroll_area.grid(row=0, column=0, sticky="nsew")
        scroll_area.rowconfigure(0, weight=1)
        scroll_area.columnconfigure(0, weight=1)

        self.content_canvas = tk.Canvas(scroll_area, highlightthickness=0, borderwidth=0)
        self.content_canvas.grid(row=0, column=0, sticky="nsew")
        self.content_scrollbar = ttk.Scrollbar(
            scroll_area, orient="vertical", command=self.content_canvas.yview
        )
        self.content_scrollbar.grid(row=0, column=1, sticky="ns")
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)

        content = ttk.Frame(self.content_canvas, padding=(6, 4, 6, 12))
        self.content_window = self.content_canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )
        content.bind("<Configure>", self._update_scroll_region)
        self.content_canvas.bind("<Configure>", self._resize_content)
        self.content_canvas.bind("<Enter>", self._bind_mousewheel)
        self.content_canvas.bind("<Leave>", self._unbind_mousewheel)

        ttk.Label(content, text="Universal Import", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(content, text="Add files to the shared Library, or import spreadsheet rows into Cultiva records.",
                  foreground="#68756d", wraplength=900).pack(anchor="w", pady=(2, 12))

        file_row = ttk.Frame(content)
        file_row.pack(fill="x", pady=(0, 10))
        self.file_var = tk.StringVar(value="No file selected")
        ttk.Entry(file_row, textvariable=self.file_var, state="readonly").pack(side="left", fill="x", expand=True)
        ttk.Button(file_row, text="Choose file…", command=self._choose_file).pack(side="left", padx=(8, 0))

        self.info_var = tk.StringVar(value="Supported: .cultiva packages, CSV, XLSX, XLS, PDF, DOCX, images, audio, video and other safe files.")
        ttk.Label(content, textvariable=self.info_var, wraplength=900).pack(anchor="w", pady=(0, 10))

        self.data_frame = ttk.LabelFrame(content, text="Spreadsheet import", padding=10)
        self.data_frame.pack(fill="both", expand=True)
        top = ttk.Frame(self.data_frame)
        top.pack(fill="x")
        ttk.Label(top, text="Destination module:").pack(side="left")
        self.destination_var = tk.StringVar()
        self.destination = ttk.Combobox(top, textvariable=self.destination_var, state="readonly",
                                        values=list(importer.DESTINATIONS), width=20)
        self.destination.pack(side="left", padx=8)
        self.destination.bind("<<ComboboxSelected>>", lambda e: self._mapping_changed())
        ttk.Label(top, text="Map spreadsheet columns to Cultiva fields below.").pack(side="left", padx=8)

        self.mapping_frame = ttk.Frame(self.data_frame)
        self.mapping_frame.pack(fill="x", pady=8)
        preview_frame = ttk.Frame(self.data_frame)
        preview_frame.pack(fill="both", expand=True)
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.preview = ttk.Treeview(preview_frame, show="headings", height=9)
        self.preview.grid(row=0, column=0, sticky="nsew")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview.yview)
        preview_scroll.grid(row=0, column=1, sticky="ns")
        self.preview.configure(yscrollcommand=preview_scroll.set)
        self.summary_var = tk.StringVar(value="Select a spreadsheet to see its preview and validation.")
        ttk.Label(self.data_frame, textvariable=self.summary_var, wraplength=880).pack(anchor="w", pady=(8, 0))

        # This footer stays visible regardless of the amount of content above.
        footer = ttk.Frame(outer)
        footer.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=150)
        self.progress.pack(side="left")
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="right")
        self.import_button = ttk.Button(footer, text="Import to Library", command=self._import, state="disabled")
        self.import_button.pack(side="right", padx=8)

    def _update_scroll_region(self, _event=None):
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _resize_content(self, event):
        self.content_canvas.itemconfigure(self.content_window, width=event.width)

    def _bind_mousewheel(self, _event=None):
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<Button-4>", self._on_mousewheel_linux)
        self.bind_all("<Button-5>", self._on_mousewheel_linux)

    def _unbind_mousewheel(self, _event=None):
        self.unbind_all("<MouseWheel>")
        self.unbind_all("<Button-4>")
        self.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.delta:
            self.content_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_mousewheel_linux(self, event):
        self.content_canvas.yview_scroll(-1 if event.num == 4 else 1, "units")

    def _choose_file(self):
        path = filedialog.askopenfilename(parent=self, title="Choose a file")
        if not path:
            return
        try:
            p, ext, size = importer._file_info(path)
            self.path = str(p)
            self.file_var.set(p.name)
            self.info_var.set("%s · %s · %s bytes" % (p.name, importer.file_category(p.name), size))
            self.import_button.configure(state="normal", text="Import to Library")
            self.data_frame.pack(fill="both", expand=True)
            self.headers, self.records = [], []
            self._clear_mapping()
            self.preview.delete(*self.preview.get_children())
            if ext == importer.CULTIVA_EXTENSION:
                manifest, self.headers, self.records = importer.read_cultiva_package(path)
                counts = manifest.get("module_counts", {})
                count_text = ", ".join("%s: %s" % (name, count) for name, count in counts.items())
                self.destination_var.set("")
                self._clear_mapping()
                self.preview.delete(*self.preview.get_children())
                self.preview["columns"] = ("record_type", "title", "name", "date")
                for col in self.preview["columns"]:
                    self.preview.heading(col, text=col.replace("_", " ").title())
                    self.preview.column(col, width=150, stretch=True)
                for record in self.records[:12]:
                    self.preview.insert("", "end", values=(record.get("record_type", ""), record.get("title", ""), record.get("name", ""), record.get("due_date") or record.get("plant_date") or record.get("entry_date") or record.get("att_date") or ""))
                self.summary_var.set("Cultiva package v%s · %s records · %s" % (manifest.get("package_version"), manifest.get("record_count"), count_text or "No records"))
                self.import_button.configure(text="Validate and Import Package")
                self.info_var.set("Verified package structure: %s" % p.name)
            elif ext in importer.SPREADSHEET_EXTENSIONS:
                self.headers, self.records = importer.parse_spreadsheet(path)
                detected = importer.suggest_destination(self.headers)
                self.destination_var.set(detected or "")
                self._mapping_changed()
                self.import_button.configure(text="Validate and Import")
                self.info_var.set("%s · %s · %d data rows" %
                                  (p.name, importer.file_category(p.name), len(self.records)))
            else:
                self.destination_var.set("")
                self.summary_var.set("This file will be preserved in the centralized Library. No data rows will be inserted.")
                self.info_var.set("%s · %s · %s bytes" % (p.name, importer.file_category(p.name), size))
        except Exception as exc:
            messagebox.showerror("Cannot read file", str(exc), parent=self)
            self.path = None
            self.import_button.configure(state="disabled")

    def _clear_mapping(self):
        for child in self.mapping_frame.winfo_children():
            child.destroy()
        self.mapping_vars = {}

    def _mapping_changed(self):
        self._clear_mapping()
        dest = self.destination_var.get()
        if not dest or not self.headers:
            return
        suggested = importer.suggest_mapping(self.headers, dest)
        for row, (field, meta) in enumerate(importer.DESTINATIONS[dest]["columns"].items()):
            ttk.Label(self.mapping_frame, text=field.replace("_", " ").title() +
                      (" *" if meta["required"] else "")).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
            var = tk.StringVar(value=suggested.get(field, ""))
            self.mapping_vars[field] = var
            combo = ttk.Combobox(self.mapping_frame, textvariable=var, state="readonly",
                                 values=[""] + self.headers, width=28)
            combo.grid(row=row, column=1, sticky="w", pady=2)
            combo.bind("<<ComboboxSelected>>", lambda e: self._show_preview())
        self._show_preview()

    def _show_preview(self):
        if not self.headers:
            return
        dest = self.destination_var.get()
        self.preview.delete(*self.preview.get_children())
        selected_headers = [self.mapping_vars.get(k, tk.StringVar(value="")).get()
                            for k in importer.DESTINATIONS[dest]["columns"]]
        selected_headers = [h for h in selected_headers if h]
        shown = selected_headers[:6] or self.headers[:6]
        self.preview["columns"] = shown
        for h in shown:
            self.preview.heading(h, text=h)
            self.preview.column(h, width=135, stretch=True)
        for record in self.records[:8]:
            self.preview.insert("", "end", values=[str(record.get(h, ""))[:120] for h in shown])
        try:
            valid, issues = importer.validate_rows(self.headers, self.records, dest,
                                                    {k: v.get() for k, v in self.mapping_vars.items()})
            self.valid_rows, self.issues = valid, issues
            self.duplicate_rows = importer.detect_duplicates(dest, valid) if valid else []
            issue_text = "; ".join("row %d: %s" % (item["row"], ", ".join(item["errors"]))
                                   for item in issues[:5])
            if len(issues) > 5:
                issue_text += "; and %d more invalid rows" % (len(issues) - 5)
            self.summary_var.set("Preview: %d rows · %d valid · %d duplicate · %d invalid. %s" %
                                 (len(self.records), len(valid), len(self.duplicate_rows), len(issues),
                                  ("Issues: " + issue_text) if issue_text else "No validation errors."))

        except Exception as exc:
            self.summary_var.set("Mapping needs attention: %s" % exc)

    def _import(self):
        if not self.path:
            return
        try:
            self.progress.start(10)
            self.import_button.configure(state="disabled")
            created = True
            if Path(self.path).suffix.lower() == importer.CULTIVA_EXTENSION:
                manifest, _headers, _records = importer.read_cultiva_package(self.path)
                counts = manifest.get("module_counts", {})
                summary = "\n".join("%s: %s" % (name, count) for name, count in counts.items() if count)
                if not messagebox.askyesno("Confirm Cultiva package import",
                    "Package contains %s records.\n\n%s\n\nExisting records will be preserved; matching records will be skipped.\n\nImport this package?" % (manifest.get("record_count"), summary), parent=self):
                    self.import_button.configure(state="normal")
                    return
                result = importer.import_cultiva_package(self.path)
                added_total = sum(result["added"].values())
                duplicate_total = sum(result["duplicates"].values())
                detail = "\n".join("%s: %d added, %d skipped" % (name, result["added"][name], result["duplicates"][name]) for name in importer.CULTIVA_IMPORT_ORDER)
                messagebox.showinfo("Cultiva package imported", "Added: %d\nDuplicates skipped: %d\n\n%s" % (added_total, duplicate_total, detail), parent=self)
                if self.on_complete:
                    self.on_complete()
                self.destroy()
                return
            if self.headers:
                dest = self.destination_var.get()
                if not dest:
                    raise ValueError("Choose a destination module before importing spreadsheet data.")
                mapping = {k: v.get() for k, v in self.mapping_vars.items()}
                valid, issues = importer.validate_rows(self.headers, self.records, dest, mapping)
                self.valid_rows, self.issues = valid, issues
                if not valid:
                    raise ValueError("No valid rows are ready to import. Review the mapping and validation summary.")
                if not messagebox.askyesno(
                    "Confirm import",
                    "File: %s\nDestination: %s\nValid rows: %d\nInvalid rows: %d\n\n"
                    "Existing records will be preserved. Duplicate rows will be skipped. Continue?" %
                    (os.path.basename(self.path), dest, len(valid), len(issues)), parent=self):
                    self.import_button.configure(state="normal")
                    return
                resource, created = importer.store_resource(self.path)
                self.resource = resource
                added, duplicates = importer.import_records(dest, valid)
                message = ("Resource saved to Library.\n\nDestination: %s\nAdded: %d\nDuplicates skipped: %d\n"
                           "Invalid rows: %d\n\nInvalid rows: %s" %
                           (dest, added, len(duplicates), len(issues),
                            ", ".join(str(x["row"]) for x in issues[:30]) or "None"))
                messagebox.showinfo("Import complete", message, parent=self)
            else:
                messagebox.showinfo("Import complete",
                                    "Saved '%s' to the centralized Library.%s" %
                                    (resource["original_name"], "\nAn identical file already existed; no duplicate copy was created." if not created else ""),
                                    parent=self)
            if self.on_complete:
                self.on_complete()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Import failed", str(exc), parent=self)
            self.import_button.configure(state="normal")
        finally:
            self.progress.stop()
