
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

import db
import theme
import translations
from helpers import dialogs
from helpers.widgets import ScrollableTree, SearchBox
from helpers import universal_import
from helpers.files import open_with_system, load_thumbnail
from ui.import_wizard import ImportWizard

tr = translations.tr

_ALL = "All categories"


def _categories():
    return [
        ("plot", tr("plots")),
        ("crop", tr("crops")),
        ("worker", tr("workers")),
        ("planting", tr("plantings")),
        ("task", "Tasks"),
        ("shift", tr("shifts")),
        ("attendance", "Attendance"),
        ("journal", "Journal entries"),
        ("note", "Notes"),
        ("attachment", "Attachments"),
        ("resource", "Imported resources"),
    ]


def _query_specs():
    return {
        "plot": (
            "SELECT p.id, p.name, CONCAT_WS(' | ', p.area, p.notes) AS details "
            "FROM plots p",
            ("p.name", "p.area", "p.notes"),
            "p.name"),
        "crop": (
            "SELECT c.id, c.name, CONCAT_WS(' | ', "
            "CONCAT(c.days_to_harvest, ' days to harvest'), c.notes) AS details "
            "FROM crops c",
            ("c.name", "c.notes", "CAST(c.days_to_harvest AS CHAR)"),
            "c.name"),
        "worker": (
            "SELECT w.id, w.name, CONCAT_WS(' | ', w.role, w.phone, "
            "IF(w.active, 'Active', 'Inactive')%s) AS details "
            "FROM workers w" % (", CAST(w.daily_rate AS CHAR)" if translations.feature("pay") else ""),
            ("w.name", "w.role", "w.phone") +
            (("CAST(w.daily_rate AS CHAR)",) if translations.feature("pay") else ()),
            "w.name"),
        "planting": (
            "SELECT pl.id, CONCAT(c.name, ' in ', p.name) AS name, "
            "CONCAT_WS(' | ', pl.status, CONCAT('Planted ', pl.plant_date), "
            "CONCAT('Expected harvest ', pl.expected_harvest), pl.notes) AS details "
            "FROM plantings pl JOIN plots p ON p.id = pl.plot_id "
            "JOIN crops c ON c.id = pl.crop_id",
            ("p.name", "c.name", "pl.status", "pl.notes",
             "CAST(pl.plant_date AS CHAR)", "CAST(pl.expected_harvest AS CHAR)"),
            "pl.plant_date DESC, pl.id DESC"),
        "task": (
            "SELECT t.id, t.title AS name, CONCAT_WS(' | ', "
            "CONCAT('Due ', t.due_date), t.priority, "
            "IF(t.done, 'Done', 'Open'), p.name, c.name, w.name, t.notes) AS details "
            "FROM tasks t LEFT JOIN plots p ON p.id = t.plot_id "
            "LEFT JOIN plantings pl ON pl.id = t.planting_id "
            "LEFT JOIN crops c ON c.id = pl.crop_id "
            "LEFT JOIN workers w ON w.id = t.worker_id",
            ("t.title", "t.notes", "t.priority", "p.name", "c.name", "w.name",
             "CAST(t.due_date AS CHAR)"),
            "t.due_date DESC, t.id DESC"),
        "shift": (
            "SELECT s.id, s.title AS name, CONCAT_WS(' | ', "
            "ELT(s.weekday + 1, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', "
            "'Friday', 'Saturday', 'Sunday'), s.start_time, s.end_time, w.name, "
            "p.name, s.notes) AS details "
            "FROM shifts s LEFT JOIN workers w ON w.id = s.worker_id "
            "LEFT JOIN plots p ON p.id = s.plot_id",
            ("s.title", "s.notes", "w.name", "p.name"),
            "s.weekday, s.start_time, s.id"),
        "attendance": (
            "SELECT a.id, w.name AS name, CONCAT_WS(' | ', "
            "DATE_FORMAT(a.att_date, '%a %d %b %Y'), a.status, a.time_in, "
            "a.time_out, a.remarks) AS details "
            "FROM attendance a JOIN workers w ON w.id = a.worker_id",
            ("w.name", "a.status", "a.remarks", "CAST(a.att_date AS CHAR)"),
            "a.att_date DESC, a.id DESC"),
        "journal": (
            "SELECT j.id, j.title AS name, CONCAT_WS(' | ', "
            "DATE_FORMAT(j.entry_date, '%a %d %b %Y'), j.mood_weather, "
            "p.name, c.name, j.body) AS details "
            "FROM journal_entries j LEFT JOIN plots p ON p.id = j.plot_id "
            "LEFT JOIN crops c ON c.id = j.crop_id",
            ("j.title", "j.body", "j.mood_weather", "p.name", "c.name",
             "CAST(j.entry_date AS CHAR)"),
            "j.entry_date DESC, j.id DESC"),
        "note": (
            "SELECT n.id, n.title AS name, CONCAT_WS(' | ', p.name, c.name, n.body) AS details "
            "FROM notes n LEFT JOIN plots p ON p.id = n.plot_id "
            "LEFT JOIN crops c ON c.id = n.crop_id",
            ("n.title", "n.body", "p.name", "c.name"),
            "n.title"),
        "resource": (
            "SELECT r.id, r.original_name AS name, CONCAT_WS(' | ', r.category, r.extension, "
            "CONCAT(r.size_bytes, ' bytes'), r.mime_type, DATE_FORMAT(r.created_at, '%a %d %b %Y')) AS details "
            "FROM resources r",
            ("r.original_name", "r.category", "r.extension", "r.mime_type"),
            "r.created_at DESC, r.id DESC"),
        "attachment": (
            "SELECT a.id, a.original_name AS name, CONCAT_WS(' | ', a.mime_type, "
            "CONCAT(a.size_bytes, ' bytes'), "
            "COALESCE(n.title, j.title), DATE_FORMAT(a.created_at, '%a %d %b %Y')) AS details "
            "FROM attachments a LEFT JOIN notes n ON n.id = a.note_id "
            "LEFT JOIN journal_entries j ON j.id = a.journal_id",
            ("a.original_name", "a.mime_type", "n.title", "j.title",
             "CAST(a.created_at AS CHAR)"),
            "a.original_name"),
    }


class LibraryTab(ttk.Frame):

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.rows = {}
        self.categories = _categories()
        self._build()

    def _build(self):
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text=tr("tab_library"), style="LibraryTitle.TLabel").pack(side="left")
        ttk.Label(header, text="Browse and search records across your farm or garden.",
                  style="Muted.TLabel").pack(side="left", padx=(12, 0))

        # Keep filters and actions on separate rows.  A single crowded toolbar
        # caused the rightmost Library actions (including Delete) to disappear
        # on smaller Windows displays and at the application's minimum width.
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))

        filter_row = ttk.Frame(toolbar)
        filter_row.pack(fill="x", pady=(0, 6))
        self.search = SearchBox(filter_row, label="Search:", on_change=self.refresh, width=28)
        self.search.pack(side="left")
        ttk.Label(filter_row, text="Category:").pack(side="left", padx=(16, 6))
        self.category_var = tk.StringVar(value=_ALL)
        self.category_filter = ttk.Combobox(
            filter_row, textvariable=self.category_var, state="readonly", width=18,
            values=[_ALL] + [label for _, label in self.categories])
        self.category_filter.pack(side="left")
        self.category_filter.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        action_row = ttk.Frame(toolbar)
        action_row.pack(fill="x")
        ttk.Button(action_row, text="Delete selected", style="Danger.TButton",
                   command=self._delete_selected).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="Open selected", command=self._open_selected).pack(side="left", padx=(0, 8))
        ttk.Button(action_row, text="⇧ Export .cultiva", command=self._export_cultiva).pack(side="right", padx=(8, 0))
        ttk.Button(action_row, text="＋ Import files", command=self._open_import).pack(side="right")

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)
        self.table = ScrollableTree(
            left, columns=("category", "name", "details"), height=16,
            headings={"category": "Category", "name": "Name", "details": "Summary"},
            widths={"category": 130, "name": 220, "details": 400})
        self.table.grid(row=0, column=0, sticky="nsew")
        self.count_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.count_var, style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(5, 0))
        panes.add(left, weight=3)

        right = ttk.Frame(panes, padding=(10, 0, 0, 0))
        ttk.Label(right, text="Record details", style="Header.TLabel").pack(anchor="w")
        self.resource_preview = ttk.Label(right)
        self.resource_preview.pack(anchor="w", pady=(6, 2))
        self._preview_image = None
        self.detail_text = tk.Text(right, wrap="word", state="disabled", height=12)
        theme.style_text(self.detail_text)
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.detail_text.pack(side="left", fill="both", expand=True, pady=(6, 0))
        panes.add(right, weight=2)
        self.table.bind_select(self._show_details)

    def refresh(self):
        selected = self.table.selected_iid()
        search = self.search.get()
        chosen_label = self.category_var.get()
        chosen_key = next((key for key, label in self.categories if label == chosen_label), None)
        like = db.like_pattern(search)
        specs = _query_specs()
        records = []
        try:
            for key, label in self.categories:
                if chosen_key is not None and key != chosen_key:
                    continue
                sql, search_fields, order_by = specs[key]
                params = None
                if search:
                    sql += " WHERE (" + " OR ".join(field + " LIKE %s" for field in search_fields) + ")"
                    params = (like,) * len(search_fields)
                sql += " ORDER BY " + order_by
                for row in db.query(sql, params):
                    records.append({
                        "iid": "%s:%s" % (key, row["id"]),
                        "category": label,
                        "name": row["name"],
                        "details": row["details"] or "",
                    })
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return

        records.sort(key=lambda row: (row["category"].casefold(), str(row["name"]).casefold()))
        self.rows = {row["iid"]: row for row in records}
        self.table.clear()
        for row in records:
            self.table.add((row["category"], row["name"], row["details"]), iid=row["iid"])
        if selected in self.rows:
            self.table.select(selected)
        else:
            self._show_details()
        self.count_var.set("%d record%s" % (len(records), "" if len(records) == 1 else "s"))

    def _open_import(self):
        ImportWizard(self, on_complete=self.refresh)

    def _export_cultiva(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Cultiva portable package",
            defaultextension=".cultiva", initialfile="cultiva_export.cultiva",
            filetypes=[("Cultiva portable package", "*.cultiva")])
        if not path:
            return
        try:
            manifest = universal_import.export_cultiva_package(path)
            counts = "\n".join("%s: %s" % (name, count) for name, count in manifest["module_counts"].items())
            messagebox.showinfo("Export complete",
                "Created portable Cultiva package.\n\nRecords: %d\n\n%s\n\nThis file can be imported by another compatible Cultiva installation." %
                (manifest["record_count"], counts), parent=self)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)

    def _delete_selected(self):
        """Delete a Library file only after checking its links and confirming."""
        iid = self.table.selected_iid()
        if not iid:
            dialogs.show_info(self, "Select a Library item first.")
            return
        kind, _, raw_id = iid.partition(":")
        if kind not in ("resource", "attachment"):
            dialogs.show_info(
                self,
                "This item is a farm/garden record, not a stored Library file. "
                "Delete it from its module so linked records can be checked safely.")
            return
        try:
            item_id = int(raw_id)
            if kind == "resource":
                item = db.query_one("SELECT * FROM resources WHERE id = %s", (item_id,))
                if not item:
                    dialogs.show_error(self, "This Library file no longer exists.")
                    self.refresh()
                    return
                usage = universal_import.resource_usage(item_id)
                if usage:
                    used_by = "\n".join(
                        "• %s record #%s" % (link["module_key"], link["record_id"])
                        for link in usage)
                    dialogs.show_error(
                        self,
                        "This file is still linked to records and cannot be deleted. "
                        "Remove its links from those records first.\n\nUsed by:\n" + used_by)
                    return
                if not messagebox.askyesno(
                        "Delete Library file",
                        "Permanently delete '%s'?\n\nThis also removes the stored file from disk."
                        % item["original_name"], parent=self, icon="warning"):
                    return
                stored_name = item["stored_name"]
                with db.transaction():
                    db.execute("DELETE FROM resources WHERE id = %s", (item_id,))
                from helpers.files import delete_stored_file
                delete_stored_file(stored_name)
            else:
                item = db.query_one("SELECT * FROM attachments WHERE id = %s", (item_id,))
                if not item:
                    dialogs.show_error(self, "This attachment no longer exists.")
                    self.refresh()
                    return
                if not messagebox.askyesno(
                        "Delete attachment",
                        "Permanently delete '%s'?\n\nThe attachment will be removed from its note or journal entry."
                        % item["original_name"], parent=self, icon="warning"):
                    return
                stored_name = item["stored_name"]
                with db.transaction():
                    db.execute("DELETE FROM attachments WHERE id = %s", (item_id,))
                from helpers.files import delete_stored_file
                delete_stored_file(stored_name)
            self.refresh()
            dialogs.show_info(self, "Library file deleted.")
        except Exception as exc:
            dialogs.show_error(self, "Could not delete this Library item:\n%s" % exc)

    def _open_selected(self):
        iid = self.table.selected_iid()
        if not iid or not iid.startswith("resource:"):
            dialogs.show_info(self, "Select an imported resource first.")
            return
        try:
            resource_id = int(iid.split(":", 1)[1])
            resource = db.query_one("SELECT * FROM resources WHERE id = %s", (resource_id,))
            if not resource:
                dialogs.show_error(self, "That resource is no longer available.")
                return
            open_with_system(universal_import.resource_path(resource))
        except Exception as exc:
            dialogs.show_error(self, "Could not open this resource:\n%s" % exc)

    def _show_details(self):
        iid = self.table.selected_iid()
        row = self.rows.get(iid) if iid else None
        text = ""
        self._preview_image = None
        self.resource_preview.configure(image="", text="")
        if row:
            text = "%s\n\n%s\n\n%s" % (row["name"], row["category"], row["details"])
            if iid and iid.startswith("resource:"):
                try:
                    resource_id = int(iid.split(":", 1)[1])
                    resource = db.query_one("SELECT * FROM resources WHERE id = %s", (resource_id,))
                    if resource:
                        if resource["category"] == "Image":
                            self._preview_image = load_thumbnail(
                                universal_import.resource_path(resource), (180, 120))
                            if self._preview_image:
                                self.resource_preview.configure(image=self._preview_image)
                        usage = universal_import.resource_usage(resource_id)
                        used_by = ["%s #%s" % (item["module_key"], item["record_id"]) for item in usage]
                        text += "\n\nUsed by: " + (", ".join(used_by) if used_by else "Not linked to a record yet")
                except Exception as exc:
                    text += "\n\nResource detail unavailable: %s" % exc
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
        self.detail_text.configure(state="disabled")
