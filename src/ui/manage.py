

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

import db
import translations
from helpers import dialogs
from helpers import validation as v
from helpers.forms import Field, ask_form
from helpers.widgets import InlineMessage, ScrollableTree, SearchBox

tr = translations.tr

STATUS_OPTIONS = [("growing", "Growing"), ("harvested", "Harvested"), ("failed", "Failed")]
ALL_STATUSES = "All statuses"


def short(text, limit=60):

    if not text:
        return ""
    one_line = " ".join(str(text).split())
    return one_line if len(one_line) <= limit else one_line[:limit - 3] + "..."


def days_left_text(status, expected, today=None):

    if status != "growing" or expected is None:
        return "-"
    days = (expected - (today or date.today())).days
    if days > 1:
        return "%d days" % days
    if days == 1:
        return "1 day"
    if days == 0:
        return "Today"
    return "%d days late" % -days


class CrudPanel(ttk.Frame):


    kind = "plot"
    plural = "plots"
    delete_sql = ""
    duplicate_field = "name"

    def __init__(self, parent, app):
        super().__init__(parent, padding=10)
        self.app = app
        self.rows = {}  
        self.noun = tr(self.kind)
        self._build()

    def title(self):

        return tr(self.plural)

    def columns(self):
        raise NotImplementedError

    def fetch_rows(self, search):
        raise NotImplementedError

    def row_values(self, row):
        raise NotImplementedError

    def display_name(self, row):
        return str(row.get("name", ""))

    def fields(self, row):
        raise NotImplementedError

    def initial_values(self, row):
        return {}

    def insert(self, values):
        raise NotImplementedError

    def update(self, row_id, values):
        raise NotImplementedError

    def check_rules(self, values):
        pass

    def build_filters(self, toolbar):
        pass

    def in_use_hint(self):
        return ""

    def delete_warning(self, row):
        return ""

    def duplicate_message(self, values):
        return 'A %s named "%s" already exists.' % (self.noun.lower(), values.get("name", ""))

    def _build(self):
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))
        self.search = SearchBox(toolbar, on_change=self.refresh)
        self.search.pack(side="left")
        self.build_filters(toolbar)

        buttons = ttk.Frame(toolbar)
        buttons.pack(side="right")
        self.add_button = ttk.Button(buttons, text="Add " + self.noun.lower(),
                                     style="Accent.TButton", command=self.add)
        self.edit_button = ttk.Button(buttons, text="Edit", command=self.edit)
        self.delete_button = ttk.Button(buttons, text="Delete", style="Danger.TButton",
                                        command=self.delete)
        for button in (self.add_button, self.edit_button, self.delete_button):
            button.pack(side="left", padx=(6, 0))

        setup = self.columns()
        self.table = ScrollableTree(
            self, columns=[key for key, _, _, _ in setup], height=14,
            headings={key: heading for key, heading, _, _ in setup},
            widths={key: width for key, _, width, _ in setup},
            anchors={key: anchor for key, _, _, anchor in setup})
        self.table.pack(fill="both", expand=True)
        self.table.bind_select(self._update_buttons)
        self.table.bind_activate(self.edit)                       
        self.table.tree.bind("<Delete>", lambda event: self.delete())
        self.table.tree.bind("<Insert>", lambda event: self.add())

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self.count_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.count_label.pack(side="left")
        self.message = InlineMessage(bottom, wraplength=600)
        self.message.pack(side="right")
        self._update_buttons()

    def refresh(self):

        selected = self.table.selected_iid()
        search = self.search.get()
        try:
            rows = self.fetch_rows(search)
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return
        self.rows = {row["id"]: row for row in rows}
        self.table.clear()
        for row in rows:
            self.table.add(self.row_values(row), iid=row["id"])
        if selected:
            self.table.select(selected)
        self._update_buttons()
        word = tr(self.kind) if len(rows) == 1 else tr(self.plural)
        found = "%d %s" % (len(rows), word.lower())
        self.count_label.configure(text=found + (" found" if search else ""))

    def _selected_row(self):
        iid = self.table.selected_iid()
        return self.rows.get(int(iid)) if iid else None

    def _update_buttons(self):
        state = "!disabled" if self._selected_row() else "disabled"
        self.edit_button.state([state])
        self.delete_button.state([state])

    def _save(self, row, values):

        try:
            if row is None:
                return self.insert(values)
            self.update(row["id"], values)
            return row["id"]
        except db.DBDuplicateError:
            raise v.ValidationError(self.duplicate_message(values),
                                    field=self.duplicate_field) from None

    def _open_form(self, row):

        try:
            form_fields = self.fields(row)
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return None
        if form_fields is None:  
            return None
        saved = {}

        def save(values):
            saved["id"] = self._save(row, values)

        title = ("Add " if row is None else "Edit ") + self.noun.lower()
        values = self.initial_values(row)
        result = ask_form(self, title, form_fields, values=values, save=save,
                          validate=self.check_rules)
        return saved.get("id") if result else None

    def add(self):
        new_id = self._open_form(None)
        if new_id is not None:
            self.refresh()
            self.table.select(new_id)
            self.message.ok("%s added." % self.noun)

    def edit(self):
        row = self._selected_row()
        if row is None:
            self.message.error("Select a row first.")
            return
        row_id = self._open_form(row)
        if row_id is not None:
            self.refresh()
            self.table.select(row_id)
            self.message.ok("%s saved." % self.noun)

    def delete(self):
        row = self._selected_row()
        if row is None:
            self.message.error("Select a row first.")
            return
        try:
            warning = self.delete_warning(row)
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return
        deleted = dialogs.delete_record(
            self, self.noun.lower(), self.display_name(row),
            delete_func=lambda: db.execute(self.delete_sql, (row["id"],)),
            in_use_hint=self.in_use_hint(), warning=warning)
        if deleted:
            self.refresh()
            self.message.ok("%s deleted." % self.noun)


class PlotsPanel(CrudPanel):
    kind, plural = "plot", "plots"
    delete_sql = "DELETE FROM plots WHERE id = %s"

    def columns(self):
        return [("name", tr("plot") + " name", 220, "w"),
                ("area", "Area", 110, "w"),
                ("plantings", tr("plantings"), 90, "e"),
                ("notes", "Notes", 380, "w")]

    def fetch_rows(self, search):
        like = db.like_pattern(search)
        return db.query(
            "SELECT p.id, p.name, p.area, p.notes, COUNT(pl.id) AS plantings "
            "FROM plots p LEFT JOIN plantings pl ON pl.plot_id = p.id "
            "WHERE p.name LIKE %s OR p.area LIKE %s OR p.notes LIKE %s "
            "GROUP BY p.id, p.name, p.area, p.notes ORDER BY p.name",
            (like, like, like))

    def row_values(self, row):
        return (row["name"], row["area"] or "", row["plantings"], short(row["notes"]))

    def fields(self, row):
        return [
            Field("name", tr("plot") + " name", required=True, max_length=100),
            Field("area", "Area", max_length=50, hint="For example 2 sq m or 1.5 ha"),
            Field("notes", "Notes", kind="multiline"),
        ]

    def initial_values(self, row):
        return dict(row) if row else {}

    def insert(self, values):
        return db.execute("INSERT INTO plots (name, area, notes) VALUES (%s, %s, %s)",
                          (values["name"], values["area"], values["notes"]))

    def update(self, row_id, values):
        db.execute("UPDATE plots SET name = %s, area = %s, notes = %s WHERE id = %s",
                   (values["name"], values["area"], values["notes"], row_id))

    def in_use_hint(self):
        return "Delete or move its %s first." % tr("plantings").lower()

    def delete_warning(self, row):
        return ("Tasks, shifts, notes and journal entries linked to it will stay, "
                "but lose the link.")


class CropsPanel(CrudPanel):
    kind, plural = "crop", "crops"
    delete_sql = "DELETE FROM crops WHERE id = %s"

    def columns(self):
        return [("name", tr("crop") + " name", 200, "w"),
                ("color", "Color", 90, "w"),
                ("days_to_harvest", tr("days_to_harvest"), 120, "e"),
                ("plantings", tr("plantings"), 90, "e"),
                ("notes", "Notes", 330, "w")]

    def fetch_rows(self, search):
        like = db.like_pattern(search)
        return db.query(
            "SELECT c.id, c.name, c.color, c.days_to_harvest, c.notes, "
            "COUNT(pl.id) AS plantings "
            "FROM crops c LEFT JOIN plantings pl ON pl.crop_id = c.id "
            "WHERE c.name LIKE %s OR c.notes LIKE %s "
            "GROUP BY c.id, c.name, c.color, c.days_to_harvest, c.notes ORDER BY c.name",
            (like, like))

    def row_values(self, row):
        return (row["name"], row["color"], row["days_to_harvest"], row["plantings"],
                short(row["notes"]))

    def fields(self, row):
        return [
            Field("name", tr("crop") + " name", required=True, max_length=100),
            Field("color", "Color", kind="color", required=True,
                  hint="Used on the Calendar and Timetable"),
            Field("days_to_harvest", tr("days_to_harvest"), kind="int", required=True,
                  minimum=1, maximum=1000, width=10),
            Field("notes", "Notes", kind="multiline"),
        ]

    def initial_values(self, row):
        return dict(row) if row else {"color": "#4C9F50", "days_to_harvest": 90}

    def insert(self, values):
        return db.execute(
            "INSERT INTO crops (name, color, days_to_harvest, notes) VALUES (%s, %s, %s, %s)",
            (values["name"], values["color"], values["days_to_harvest"], values["notes"]))

    def update(self, row_id, values):
        db.execute(
            "UPDATE crops SET name = %s, color = %s, days_to_harvest = %s, notes = %s "
            "WHERE id = %s",
            (values["name"], values["color"], values["days_to_harvest"], values["notes"], row_id))

    def in_use_hint(self):
        return "Delete or move its %s first." % tr("plantings").lower()

    def delete_warning(self, row):
        return "Notes and journal entries linked to it will stay, but lose the link."


class WorkersPanel(CrudPanel):
    kind, plural = "worker", "workers"
    delete_sql = "DELETE FROM workers WHERE id = %s"

    def columns(self):
        cols = [("name", tr("worker") + " name", 200, "w"),
                ("role", "Role", 200, "w"),
                ("phone", "Phone", 140, "w")]
        if translations.feature("pay"):          
            cols.append(("daily_rate", tr("daily_rate"), 110, "e"))
        cols.append(("active", "Active", 70, "center"))
        return cols

    def fetch_rows(self, search):
        like = db.like_pattern(search)
        return db.query(
            "SELECT id, name, role, phone, daily_rate, active FROM workers "
            "WHERE name LIKE %s OR role LIKE %s OR phone LIKE %s ORDER BY name",
            (like, like, like))

    def row_values(self, row):
        cells = [row["name"], row["role"] or "", row["phone"] or ""]
        if translations.feature("pay"):
            cells.append(v.format_money(row["daily_rate"]))
        cells.append("Yes" if row["active"] else "No")
        return tuple(cells)

    def fields(self, row):
        form = [
            Field("name", tr("worker") + " name", required=True, max_length=100),
            Field("role", "Role", max_length=100),
            Field("phone", "Phone", max_length=30),
        ]
        if translations.feature("pay"):
            form.append(Field("daily_rate", tr("daily_rate"), kind="decimal", required=True,
                              minimum=0, maximum=1000000, width=14,
                              hint="Pesos per day, for example 550.00"))
        form.append(Field("active", "Active", kind="check",
                          hint="Untick to keep the history but hide from new schedules"))
        return form

    def initial_values(self, row):
        if row:
            return {**row, "daily_rate": str(row["daily_rate"]), "active": bool(row["active"])}
        return {"daily_rate": "0", "active": True}

    def insert(self, values):
        return db.execute(
            "INSERT INTO workers (name, role, phone, daily_rate, active) "
            "VALUES (%s, %s, %s, %s, %s)",
            (values["name"], values["role"], values["phone"],
             values.get("daily_rate", 0), 1 if values["active"] else 0))

    def update(self, row_id, values):
        if "daily_rate" in values:
            db.execute(
                "UPDATE workers SET name = %s, role = %s, phone = %s, daily_rate = %s, "
                "active = %s WHERE id = %s",
                (values["name"], values["role"], values["phone"], values["daily_rate"],
                 1 if values["active"] else 0, row_id))
        else:  
            db.execute(
                "UPDATE workers SET name = %s, role = %s, phone = %s, active = %s WHERE id = %s",
                (values["name"], values["role"], values["phone"],
                 1 if values["active"] else 0, row_id))

    def delete_warning(self, row):

        counts = db.query_one(
            "SELECT (SELECT COUNT(*) FROM shifts WHERE worker_id = %s) AS shifts, "
            "(SELECT COUNT(*) FROM attendance WHERE worker_id = %s) AS attendance",
            (row["id"], row["id"]))
        parts = []
        if counts["shifts"]:
            parts.append("%d %s" % (counts["shifts"], tr("shifts").lower()))
        if counts["attendance"]:
            parts.append("%d attendance record(s)" % counts["attendance"])
        text = "Tasks assigned to them will stay, but lose the assignment."
        if parts:
            text = ("This will also delete their " + " and ".join(parts) + ". " + text +
                    "\nTip: edit and untick Active to keep the history instead.")
        return text


class PlantingsPanel(CrudPanel):
    kind, plural = "planting", "plantings"
    delete_sql = "DELETE FROM plantings WHERE id = %s"

    def columns(self):
        return [("plot", tr("plot"), 150, "w"),
                ("crop", tr("crop"), 150, "w"),
                ("plant_date", "Planted", 100, "w"),
                ("expected_harvest", "Expected " + tr("harvest").lower(), 130, "w"),
                ("days_left", "Days left", 100, "w"),
                ("status", "Status", 90, "w"),
                ("notes", "Notes", 260, "w")]

    def build_filters(self, toolbar):

        ttk.Label(toolbar, text="Status:").pack(side="left", padx=(16, 6))
        self.status_var = tk.StringVar(value=ALL_STATUSES)
        combo = ttk.Combobox(toolbar, textvariable=self.status_var, state="readonly", width=14,
                             values=[ALL_STATUSES] + [label for _, label in STATUS_OPTIONS])
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda event: self.refresh())

    def _status_filter(self):

        chosen = self.status_var.get()
        for value, label in STATUS_OPTIONS:
            if label == chosen:
                return value
        return None

    def fetch_rows(self, search):
        like = db.like_pattern(search)
        sql = ("SELECT pl.id, pl.plot_id, pl.crop_id, pl.plant_date, pl.expected_harvest, "
               "pl.status, pl.notes, p.name AS plot_name, c.name AS crop_name "
               "FROM plantings pl JOIN plots p ON p.id = pl.plot_id "
               "JOIN crops c ON c.id = pl.crop_id "
               "WHERE (p.name LIKE %s OR c.name LIKE %s OR pl.notes LIKE %s)")
        params = [like, like, like]
        status = self._status_filter()
        if status:
            sql += " AND pl.status = %s"
            params.append(status)
        sql += " ORDER BY pl.plant_date DESC, pl.id DESC"
        return db.query(sql, tuple(params))

    def row_values(self, row):
        return (row["plot_name"], row["crop_name"],
                v.date_to_text(row["plant_date"]), v.date_to_text(row["expected_harvest"]),
                days_left_text(row["status"], row["expected_harvest"]),
                row["status"].title(), short(row["notes"], 50))

    def display_name(self, row):
        return "%s in %s" % (row["crop_name"], row["plot_name"])

    def fields(self, row):
        plots = [(r["id"], r["name"]) for r in db.query("SELECT id, name FROM plots ORDER BY name")]
        crops = [(r["id"], r["name"]) for r in db.query("SELECT id, name FROM crops ORDER BY name")]
        if not plots:
            if dialogs.ask_yes_no(
                    self,
                    "Add at least one plot first. Do you want to add one right now?",
                    title="No plots yet"):
                manage_tab = self.app.tab_widgets.get("manage")
                open_add_plot = getattr(manage_tab, "open_add_plot", None)
                if open_add_plot is None:
                    dialogs.show_error(self, "The plot form could not be opened.")
                else:
                    open_add_plot()
            return None
        if not crops:
            dialogs.show_info(
                self, "Add at least one %s first, then come back to add a planting."
                % tr("crop").lower(), title="Nothing to choose yet")
            return None
        return [
            Field("plot_id", tr("plot"), kind="combo", required=True, options=plots),
            Field("crop_id", tr("crop"), kind="combo", required=True, options=crops),
            Field("plant_date", "Planting date", kind="date", required=True),
            Field("expected_harvest", "Expected " + tr("harvest").lower(), kind="date",
                  hint="Leave empty to calculate it from the %s's days to harvest."
                       % tr("crop").lower()),
            Field("status", "Status", kind="combo", required=True, options=STATUS_OPTIONS),
            Field("notes", "Notes", kind="multiline"),
        ]

    def initial_values(self, row):
        if row:
            return dict(row)
        return {"plant_date": date.today(), "status": "growing"}

    def check_rules(self, values):
        v.check_harvest_after_planting(values["plant_date"], values["expected_harvest"])

    def _expected_harvest(self, values):

        if values["expected_harvest"] is not None:
            return values["expected_harvest"]
        crop = db.query_one("SELECT days_to_harvest FROM crops WHERE id = %s", (values["crop_id"],))
        return values["plant_date"] + timedelta(days=crop["days_to_harvest"])

    def insert(self, values):
        return db.execute(
            "INSERT INTO plantings (plot_id, crop_id, plant_date, expected_harvest, status, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (values["plot_id"], values["crop_id"], values["plant_date"],
             self._expected_harvest(values), values["status"], values["notes"]))

    def update(self, row_id, values):
        db.execute(
            "UPDATE plantings SET plot_id = %s, crop_id = %s, plant_date = %s, "
            "expected_harvest = %s, status = %s, notes = %s WHERE id = %s",
            (values["plot_id"], values["crop_id"], values["plant_date"],
             self._expected_harvest(values), values["status"], values["notes"], row_id))

    def delete_warning(self, row):
        return "Tasks linked to this planting will stay, but lose the link."


class ManageTab(ttk.Frame):


    def __init__(self, parent, app):
        super().__init__(parent, padding=(0, 4, 0, 0))
        self.app = app
        self.notebook = ttk.Notebook(self, style="Sub.TNotebook")
        self.notebook.pack(fill="both", expand=True)
        self.panels = []
        for panel_class in (PlantingsPanel, CropsPanel, PlotsPanel, WorkersPanel):
            panel = panel_class(self.notebook, app)
            self.notebook.add(panel, text=panel.title())
            self.panels.append(panel)
        self.notebook.bind("<<NotebookTabChanged>>", lambda event: self.refresh())

        self.root = ttk.Frame.winfo_toplevel(self)
        self.auto_refresh()

    def _current_panel(self):
        path = self.notebook.select()
        if not path:
            return None
        widget = self.nametowidget(path)
        return widget if widget in self.panels else None

    def open_add_plot(self):
        for panel in self.panels:
            if isinstance(panel, PlotsPanel):
                panel.add()
                return
        dialogs.show_error(self, "The plot form could not be opened.")

    def refresh(self):

        panel = self._current_panel()
        if panel is not None:
            panel.refresh()

    def auto_refresh(self):
        self.refresh()
        self.root.after(5000, self.auto_refresh)
