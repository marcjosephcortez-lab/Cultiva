

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

import db
import theme
import translations
from helpers import dialogs
from helpers import validation as v
from helpers.widgets import DateField, InlineMessage, ScrollableTree, SearchBox
from ui.task_form import PRIORITY_OPTIONS, open_task_form

tr = translations.tr

GROUPS = [("overdue", "Overdue"), ("today", "Today"), ("tomorrow", "Tomorrow"),
          ("later", "Later"), ("earlier", "Earlier (done)")]

STATUS_FILTERS = [("All tasks", None), ("Open", 0), ("Done", 1)]
GROUP_PREFIX = "group:"
DONE_MARK = "\u2713"  


def group_for(due, done, today=None):

    today = today or date.today()
    if due < today:
        return "earlier" if done else "overdue"
    if due == today:
        return "today"
    if due == today + timedelta(days=1):
        return "tomorrow"
    return "later"


def group_rows(rows, today=None):

    today = today or date.today()
    buckets = {key: [] for key, _ in GROUPS}
    for row in rows:
        buckets[group_for(row["due_date"], row["done"], today)].append(row)
    return [(key, title, buckets[key]) for key, title in GROUPS if buckets[key]]


def due_text(due, done, today=None):

    today = today or date.today()
    text = due.strftime("%a %d %b %Y")
    if not done and due < today:
        days = (today - due).days
        text += " (%d day%s late)" % (days, "" if days == 1 else "s")
    return text


def row_tag(row, today=None):

    today = today or date.today()
    if row["done"]:
        return "done"
    if row["due_date"] < today:
        return "overdue"
    if row["priority"] == "high":
        return "high"
    return ""


def _is_true(value):

    return str(value).lower() in ("1", "true", "yes")


class AgendaTab(ttk.Frame):


    def __init__(self, parent, app):
        super().__init__(parent, padding=(0, 8, 0, 0))
        self.app = app
        self.rows = {}        
        self.plot_ids = {}    
        self.all_plots_label = "All " + tr("plots").lower()
        self._build()
        self.root = ttk.Frame.winfo_toplevel(self)
        self.auto_refresh()

    def _build(self):
        self._build_quick_add()
        self._build_filters()
        self._build_table()
        self._build_bottom()

    def _build_quick_add(self):
        box = ttk.LabelFrame(self, text="Quick add", padding=(10, 6))
        box.pack(fill="x", pady=(0, 8))
        row = ttk.Frame(box)
        row.pack(fill="x")

        ttk.Label(row, text="Title").pack(side="left", padx=(0, 6))
        self.quick_title = ttk.Entry(row, width=36)
        self.quick_title.pack(side="left", padx=(0, 12))
        ttk.Label(row, text="Due").pack(side="left", padx=(0, 6))
        self.quick_due = DateField(row)
        self.quick_due.pack(side="left", padx=(0, 12))
        ttk.Label(row, text="Priority").pack(side="left", padx=(0, 6))
        self.quick_priority = ttk.Combobox(row, state="readonly", width=9,
                                           values=[label for _, label in PRIORITY_OPTIONS])
        self.quick_priority.set("Medium")
        self.quick_priority.pack(side="left", padx=(0, 12))
        ttk.Button(row, text="Add", style="Accent.TButton",
                   command=self.quick_add).pack(side="left")

        self.quick_message = InlineMessage(box, wraplength=700)
        self.quick_message.pack(anchor="w")
        self.quick_title.bind("<Return>", self.quick_add)                  
        self.quick_title.bind("<Escape>", lambda event: self.quick_title.delete(0, "end"))

    def _build_filters(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))

        ttk.Label(bar, text="Status:").pack(side="left", padx=(0, 6))
        self.status_var = tk.StringVar(value=STATUS_FILTERS[0][0])
        status = ttk.Combobox(bar, textvariable=self.status_var, state="readonly", width=10,
                              values=[label for label, _ in STATUS_FILTERS])
        status.pack(side="left", padx=(0, 14))
        status.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        ttk.Label(bar, text=tr("plot") + ":").pack(side="left", padx=(0, 6))
        self.plot_var = tk.StringVar(value=self.all_plots_label)
        self.plot_combo = ttk.Combobox(bar, textvariable=self.plot_var, state="readonly",
                                       width=18, values=[self.all_plots_label])
        self.plot_combo.pack(side="left", padx=(0, 14))
        self.plot_combo.bind("<<ComboboxSelected>>", lambda event: self.refresh())

        self.search = SearchBox(bar, on_change=self.refresh, width=20)
        self.search.pack(side="left")

        buttons = ttk.Frame(bar)
        buttons.pack(side="right")
        self.new_button = ttk.Button(buttons, text="New task...", style="Accent.TButton",
                                     command=self.add)
        self.edit_button = ttk.Button(buttons, text="Edit", command=self.edit)
        self.done_button = ttk.Button(buttons, text="Mark done", command=self.toggle_done)
        self.delete_button = ttk.Button(buttons, text="Delete", style="Danger.TButton",
                                        command=self.delete)
        for button in (self.new_button, self.edit_button, self.done_button, self.delete_button):
            button.pack(side="left", padx=(6, 0))

    def _build_table(self):
        columns = ("done", "due", "priority", "plot", "crop", "worker")
        self.table = ScrollableTree(
            self, columns=columns, height=14, show="tree headings", sortable=False,
            headings={"done": "Done", "due": "Due", "priority": "Priority",
                      "plot": tr("plot"), "crop": tr("crop"), "worker": tr("worker")},
            widths={"done": 55, "due": 200, "priority": 80, "plot": 130,
                    "crop": 110, "worker": 130},
            anchors={"done": "center"})
        self.table.pack(fill="both", expand=True)
        tree = self.table.tree
        tree.heading("#0", text="Task", anchor="w")
        tree.column("#0", width=340, minwidth=200, stretch=True)
        for column in columns:  
            tree.column(column, stretch=False)

        c, family = theme.colors(), theme.font_family()
        bold = (family, 10, "bold")
        tree.tag_configure("group", background=c["tab_bg"], font=bold)
        tree.tag_configure("group_overdue", background=c["tab_bg"],
                           foreground=c["danger"], font=bold)
        tree.tag_configure("done", foreground=c["muted"], font=(family, 10, "overstrike"))
        tree.tag_configure("overdue", foreground=c["danger"])
        tree.tag_configure("high", foreground=c["warn"], font=bold)

        self.table.bind_select(self._update_buttons)
        self.table.bind_activate(self.edit)                       
        tree.bind("<Button-1>", self._on_click, add="+")           
        tree.bind("<space>", self._on_space)
        tree.bind("<Delete>", lambda event: self.delete())
        tree.bind("<Insert>", lambda event: self.add())

    def _build_bottom(self):
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", pady=(6, 0))
        self.count_label = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.count_label.pack(side="left")
        self.message = InlineMessage(bottom, wraplength=560)
        self.message.pack(side="right")
        ttk.Label(self, style="Muted.TLabel",
                  text="Tip: click the Done column or press Space to tick a task. "
                       "Double-click a task to edit it.").pack(anchor="w")
        self._update_buttons()

    def _status_filter(self):

        chosen = self.status_var.get()
        for label, value in STATUS_FILTERS:
            if label == chosen:
                return value
        return None

    def _plot_filter(self):

        return self.plot_ids.get(self.plot_var.get())

    def _filters_active(self):
        return bool(self.search.get()) or self._status_filter() is not None \
            or self._plot_filter() is not None

    def _load_plot_filter(self):

        plots = db.query("SELECT id, name FROM plots ORDER BY name")
        self.plot_ids = {p["name"]: p["id"] for p in plots}
        self.plot_combo.configure(values=[self.all_plots_label] + [p["name"] for p in plots])
        if self.plot_var.get() not in self.plot_ids:
            self.plot_var.set(self.all_plots_label)

    def fetch_rows(self, search):

        like = db.like_pattern(search)
        sql = ("SELECT t.id, t.title, t.due_date, t.priority, t.done, t.notes, "
               "t.plot_id, t.planting_id, t.worker_id, "
               "p.name AS plot_name, w.name AS worker_name, c.name AS crop_name "
               "FROM tasks t "
               "LEFT JOIN plots p ON p.id = t.plot_id "
               "LEFT JOIN workers w ON w.id = t.worker_id "
               "LEFT JOIN plantings pl ON pl.id = t.planting_id "
               "LEFT JOIN crops c ON c.id = pl.crop_id "
               "WHERE (t.title LIKE %s OR t.notes LIKE %s OR p.name LIKE %s "
               "OR w.name LIKE %s OR c.name LIKE %s)")
        params = [like] * 5
        status = self._status_filter()
        if status is not None:
            sql += " AND t.done = %s"
            params.append(status)
        plot_id = self._plot_filter()
        if plot_id is not None:
            sql += " AND t.plot_id = %s"
            params.append(plot_id)
        sql += (" ORDER BY t.done, t.due_date, "
                "CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, t.title")
        return db.query(sql, tuple(params))

    def refresh(self):

        tree = self.table.tree
        selected = self.table.selected_iid()
        was_open = {iid: _is_true(tree.item(iid, "open")) for iid in tree.get_children("")}
        try:
            self._load_plot_filter()
            rows = self.fetch_rows(self.search.get())
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return

        today = date.today()
        self.rows = {row["id"]: row for row in rows}
        self.table.clear()
        for key, title, group in group_rows(rows, today):
            group_iid = GROUP_PREFIX + key
            tree.insert("", "end", iid=group_iid, text="%s  (%d)" % (title, len(group)),
                        open=was_open.get(group_iid, True),
                        tags=("group_overdue" if key == "overdue" else "group",))
            for row in group:
                self.table.add(self._row_values(row, today), iid=row["id"], parent=group_iid,
                               text=row["title"], tags=(row_tag(row, today),))
        if selected and tree.exists(selected):
            self.table.select(selected)

        open_count = sum(1 for row in rows if not row["done"])
        text = "%d task%s, %d open" % (len(rows), "" if len(rows) == 1 else "s", open_count)
        self.count_label.configure(text=text + (" (filtered)" if self._filters_active() else ""))
        self._update_buttons()

    def _row_values(self, row, today):

        return (DONE_MARK if row["done"] else "",
                due_text(row["due_date"], row["done"], today),
                row["priority"].title(),
                row["plot_name"] or "", row["crop_name"] or "", row["worker_name"] or "")

    def _selected_task(self):

        iid = self.table.selected_iid()
        if not iid or iid.startswith(GROUP_PREFIX):
            return None
        return self.rows.get(int(iid))

    def _update_buttons(self):
        row = self._selected_task()
        state = "!disabled" if row else "disabled"
        for button in (self.edit_button, self.done_button, self.delete_button):
            button.state([state])
        self.done_button.configure(text="Mark not done" if row and row["done"] else "Mark done")

    def _show_task(self, task_id):

        if self.table.tree.exists(str(task_id)):
            self.table.select(task_id)
            return True
        return False

    def _on_click(self, event):

        tree = self.table.tree
        if tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#1":   
            return
        iid = tree.identify_row(event.y)
        if iid and not iid.startswith(GROUP_PREFIX):
            tree.selection_set(iid)
            self.toggle_done()

    def _on_space(self, event):
        self.toggle_done()
        return "break"

    def quick_add(self, event=None):

        self.quick_message.clear()
        try:
            title = v.clean_text(self.quick_title.get(), "The task title", required=True,
                                 max_length=200)
        except v.ValidationError as exc:
            self.quick_message.error(exc.message)
            self.quick_title.focus_set()
            return "break"
        try:
            due = v.parse_date(self.quick_due.get(), "The due date")
        except v.ValidationError as exc:
            self.quick_message.error(exc.message)
            self.quick_due.focus_set()
            return "break"
        priority = next((value for value, label in PRIORITY_OPTIONS
                         if label == self.quick_priority.get()), "medium")

        plot_id = self._plot_filter()
        if self._status_filter() == 1:
            self.status_var.set(STATUS_FILTERS[0][0])
        try:
            new_id = db.execute(
                "INSERT INTO tasks (title, due_date, priority, plot_id) VALUES (%s, %s, %s, %s)",
                (title, due, priority, plot_id))
        except db.DBError as exc:
            self.quick_message.error(str(exc))
            return "break"

        self.quick_title.delete(0, "end")
        self.refresh()
        if self._show_task(new_id):
            self.message.ok("Task added.")
        else:
            self.message.ok("Task added, but your search or filters hide it.", seconds=8)
        self.quick_title.focus_set()
        return "break"

    def add(self):

        defaults = {}
        if self._plot_filter() is not None:
            defaults["plot_id"] = self._plot_filter()
        task_id = open_task_form(self, defaults=defaults)
        if task_id is not None:
            self.refresh()
            self.message.ok("Task added." if self._show_task(task_id)
                            else "Task added, but your search or filters hide it.")

    def edit(self):
        row = self._selected_task()
        if row is None:
            return  
        task_id = open_task_form(self, task=row)
        if task_id is not None:
            self.refresh()
            self.message.ok("Task saved." if self._show_task(task_id)
                            else "Task saved, but your search or filters hide it.")

    def toggle_done(self):

        row = self._selected_task()
        if row is None:
            self.message.error("Select a task first.")
            return
        new_state = 0 if row["done"] else 1
        try:
            db.execute("UPDATE tasks SET done = %s WHERE id = %s", (new_state, row["id"]))
        except db.DBError as exc:
            dialogs.show_db_error(self, exc)
            return
        self.refresh()
        self._show_task(row["id"])
        self.message.ok("Marked done." if new_state else "Marked not done.")

    def delete(self):
        row = self._selected_task()
        if row is None:
            self.message.error("Select a task first.")
            return
        deleted = dialogs.delete_record(
            self, "task", row["title"],
            delete_func=lambda: db.execute("DELETE FROM tasks WHERE id = %s", (row["id"],)))
        if deleted:
            self.refresh()
            self.message.ok("Task deleted.")

    def auto_refresh(self):
        self.refresh()
        self.root.after(5000, self.auto_refresh)
