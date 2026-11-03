

import calendar
import re
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

try:
    import db
except ImportError:          
    db = None


def run_select(sql, params=()):
    if db is None or not hasattr(db, "query"):
        raise RuntimeError("Database helper is unavailable; mode-safe query execution is required.")
    return db.query(sql, params)


def run_change(sql, params=()):
    if db is None or not hasattr(db, "execute"):
        raise RuntimeError("Database helper is unavailable; mode-safe write execution is required.")
    return db.execute(sql, params)



try:
    import settings
except ImportError:
    settings = None


def get_mode():

    if settings is not None:
        for name in ("get_mode", "get_current_mode"):
            if hasattr(settings, name):
                return str(getattr(settings, name)()).lower()
        if hasattr(settings, "MODE"):
            return str(settings.MODE).lower()
    return "farm"



SQL_PLANTED = """
    SELECT pl.id, pl.plant_date AS day, c.name AS crop_name, c.color,
           p.name AS plot_name
    FROM plantings pl
    JOIN crops c ON c.id = pl.crop_id
    JOIN plots p ON p.id = pl.plot_id
    WHERE pl.plant_date BETWEEN %s AND %s
    ORDER BY pl.plant_date, c.name
"""

SQL_HARVESTS = """
    SELECT pl.id, pl.expected_harvest AS day, c.name AS crop_name, c.color,
           p.name AS plot_name
    FROM plantings pl
    JOIN crops c ON c.id = pl.crop_id
    JOIN plots p ON p.id = pl.plot_id
    WHERE pl.status <> 'failed'
      AND pl.expected_harvest BETWEEN %s AND %s
    ORDER BY pl.expected_harvest, c.name
"""

SQL_TASKS = """
    SELECT t.id, t.title, t.due_date AS day, t.done, c.color,
           p.name AS plot_name
    FROM tasks t
    LEFT JOIN plots p ON p.id = t.plot_id
    LEFT JOIN plantings pl ON pl.id = t.planting_id
    LEFT JOIN crops c ON c.id = pl.crop_id
    WHERE t.due_date BETWEEN %s AND %s
    ORDER BY t.done, t.id
"""

SQL_PLOTS = "SELECT id, name FROM plots ORDER BY name"
SQL_CROPS = "SELECT id, name, days_to_harvest FROM crops ORDER BY name"
SQL_GROWING_PLANTINGS = """
    SELECT pl.id, pl.plot_id, pl.plant_date, c.name AS crop_name,
           p.name AS plot_name
    FROM plantings pl
    JOIN crops c ON c.id = pl.crop_id
    JOIN plots p ON p.id = pl.plot_id
    WHERE pl.status = 'growing'
    ORDER BY pl.plant_date DESC
    LIMIT 100
"""

SQL_INSERT_TASK = """
    INSERT INTO tasks (title, due_date, plot_id, planting_id)
    VALUES (%s, %s, %s, %s)
"""

SQL_INSERT_PLANTING = """
    INSERT INTO plantings (plot_id, crop_id, plant_date, expected_harvest)
    VALUES (%s, %s, %s, %s)
"""

SQL_TOGGLE_DONE = "UPDATE tasks SET done = IF(done = 1, 0, 1) WHERE id = %s"

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NO_CROP_COLOR = "#8a8a8a"       
HEADER_HEIGHT = 24              
MARKER_SIZE = 10                
MARKER_STEP = 14                


def to_date(value):

    if isinstance(value, datetime):
        return value.date()
    return value


def safe_color(value):

    if value and re.fullmatch(r"#[0-9a-fA-F]{6}", str(value)):
        return str(value)
    return NO_CROP_COLOR


def parse_date(text):

    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def draw_marker(cv, kind, x, y, size, color, done=False):

    s = size
    if kind == "plant":
        cv.create_polygon(x + s / 2, y, x + s, y + s, x, y + s,
                          fill=color, outline=color)
    elif kind == "harvest":
        cv.create_polygon(x + s / 2, y, x + s, y + s / 2,
                          x + s / 2, y + s, x, y + s / 2,
                          fill=color, outline=color)
    else:  
        if done:   
            cv.create_oval(x + 1, y + 1, x + s - 1, y + s - 1,
                           outline=color, fill="", width=2)
        else:
            cv.create_oval(x, y, x + s, y + s, fill=color, outline=color)


class CalendarTab(ttk.Frame):


    def __init__(self, parent, app=None):
        super().__init__(parent, padding=10)
        self.app = app
        self.today = date.today()
        self.year = self.today.year
        self.month = self.today.month
        self.selected = self.today
        self.weeks = []          
        self.events = {}         
        self.row_events = {}

        self.root = ttk.Frame.winfo_toplevel(self)

        # Build the widgets and calendar date range before the first refresh.
        # auto_refresh() calls refresh(), which needs both self.weeks and
        # self.title_label to exist.
        self._build_ui()
        self._set_month(self.year, self.month)
        self.auto_refresh()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        nav = ttk.Frame(self)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        nav.columnconfigure(2, weight=1)
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._move_month(-1)).grid(row=0, column=0)
        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._move_month(1)).grid(row=0, column=1, padx=(4, 0))
        self.title_label = ttk.Label(nav, text="",
                                     font=("TkDefaultFont", 13, "bold"))
        self.title_label.grid(row=0, column=2, sticky="w", padx=10)
        ttk.Button(nav, text="Today", command=self._go_today).grid(row=0, column=3)

        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2, minsize=300)
        body.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(body, bg="white", height=330,
                                highlightthickness=1,
                                highlightbackground="#bbbbbb")
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.canvas.bind("<Configure>", lambda e: self._draw_grid())
        self.canvas.bind("<Button-1>", self._on_canvas_click)

        detail = ttk.LabelFrame(body, text="Selected day")
        detail.grid(row=0, column=1, sticky="nsew")
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(1, weight=1)

        self.day_label = ttk.Label(detail, text="",
                                   font=("TkDefaultFont", 11, "bold"))
        self.day_label.grid(row=0, column=0, columnspan=2, sticky="w",
                            padx=8, pady=(6, 4))

        self.tree = ttk.Treeview(detail, columns=("type", "what"),
                                 show="headings", selectmode="browse",
                                 height=10)
        self.tree.heading("type", text="Type")
        self.tree.heading("what", text="Details")
        self.tree.column("type", width=80, stretch=False)
        self.tree.column("what", width=220)
        self.tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0))
        scroll = ttk.Scrollbar(detail, orient="vertical", command=self.tree.yview)
        scroll.grid(row=1, column=1, sticky="ns", padx=(0, 8))
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Double-1>", lambda e: self._toggle_done())

        buttons = ttk.Frame(detail)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        ttk.Button(buttons, text="+ Add task",
                   command=self._add_task).pack(side="left")
        ttk.Button(buttons, text="+ Add planting",
                   command=self._add_planting).pack(side="left", padx=6)
        ttk.Button(buttons, text="Toggle task done",
                   command=self._toggle_done).pack(side="left")

        self.legend = tk.Canvas(self, height=24, highlightthickness=0)
        self.legend.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.legend.bind("<Configure>", lambda e: self._draw_legend())

    def _set_month(self, year, month):

        self.year, self.month = year, month
        self.weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)

    def _move_month(self, step):
        index = (self.year * 12 + self.month - 1) + step
        year, month = divmod(index, 12)
        self._set_month(year, month + 1)
        if (self.today.year, self.today.month) == (self.year, self.month):
            self.selected = self.today
        else:
            self.selected = date(self.year, self.month, 1)
        self.refresh()

    def _go_today(self):
        self.today = date.today()
        self._set_month(self.today.year, self.today.month)
        self.selected = self.today
        self.refresh()

    def _select_day(self, day):
        self.selected = day
        if (day.year, day.month) != (self.year, self.month):
            self._set_month(day.year, day.month)
            self.refresh()
        else:
            self._draw_grid()          
            self._fill_details()

    def refresh(self):

        self.today = date.today()
        try:
            self._load_events()
        except Exception as err:   
            self.events = {}
            messagebox.showerror(
                "Could not load Calendar",
                "Something went wrong while reading the database.\n\n"
                "Check that MySQL is running in XAMPP.\n\nDetails: %s" % err,
                parent=self)
        self.title_label.config(text=date(self.year, self.month, 1).strftime("%B %Y"))
        self._draw_grid()
        self._fill_details()

    def _load_events(self):

        first = self.weeks[0][0]
        last = self.weeks[-1][-1]
        events = {}

        def add(day, event):
            events.setdefault(to_date(day), []).append(event)

        for r in run_select(SQL_PLANTED, (first, last)):
            add(r["day"], {
                "kind": "plant", "id": r["id"], "done": False,
                "color": safe_color(r["color"]),
                "type_text": "Planting",
                "text": "%s in %s" % (r["crop_name"], r["plot_name"]),
            })
        for r in run_select(SQL_HARVESTS, (first, last)):
            add(r["day"], {
                "kind": "harvest", "id": r["id"], "done": False,
                "color": safe_color(r["color"]),
                "type_text": "Harvest",
                "text": "%s from %s" % (r["crop_name"], r["plot_name"]),
            })
        for r in run_select(SQL_TASKS, (first, last)):
            done = bool(r["done"])
            text = r["title"]
            if r.get("plot_name"):
                text += "  (%s)" % r["plot_name"]
            add(r["day"], {
                "kind": "task", "id": r["id"], "done": done,
                "color": safe_color(r["color"]),
                "type_text": "Task ✓" if done else "Task",
                "text": text,
            })
        self.events = events

    def _grid_size(self):

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        rows = max(len(self.weeks), 1)
        return w / 7.0, (h - HEADER_HEIGHT) / rows

    def _draw_grid(self):
        cv = self.canvas
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 60 or h < 60 or not self.weeks:
            return                      
        cw, ch = self._grid_size()

        for i, name in enumerate(DAY_NAMES):
            cv.create_text(cw * i + cw / 2, HEADER_HEIGHT / 2, text=name,
                           font=("TkDefaultFont", 9, "bold"), fill="#333333")

        for r, week in enumerate(self.weeks):
            for c, day in enumerate(week):
                x0 = c * cw
                y0 = HEADER_HEIGHT + r * ch
                x1, y1 = x0 + cw, y0 + ch
                in_month = (day.month == self.month)

                if day == self.today:
                    fill = "#fff3c4"       
                elif in_month:
                    fill = "#ffffff"
                else:
                    fill = "#efefef"       
                cv.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#c8c8c8")

                if day == self.selected:   
                    cv.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1,
                                        outline="#2e7d32", width=3)

                weight = "bold" if day == self.today else "normal"
                cv.create_text(x0 + 6, y0 + 4, anchor="nw", text=str(day.day),
                               font=("TkDefaultFont", 9, weight),
                               fill="#222222" if in_month else "#999999")

                self._draw_day_markers(day, x0, y0, cw, ch)

    def _draw_day_markers(self, day, x0, y0, cw, ch):

        events = self.events.get(day, [])
        if not events:
            return
        per_row = max(1, int((cw - 10) // MARKER_STEP))
        rows = max(1, int((ch - 26) // MARKER_STEP))
        capacity = per_row * rows

        shown = events
        extra = 0
        if len(events) > capacity:
            shown = events[:max(capacity - 1, 0)]
            extra = len(events) - len(shown)

        for i, ev in enumerate(shown):
            x = x0 + 6 + (i % per_row) * MARKER_STEP
            y = y0 + 22 + (i // per_row) * MARKER_STEP
            draw_marker(self.canvas, ev["kind"], x, y, MARKER_SIZE,
                        ev["color"], ev["done"])

        if extra:   
            i = len(shown)
            x = x0 + 6 + (i % per_row) * MARKER_STEP
            y = y0 + 22 + (i // per_row) * MARKER_STEP
            self.canvas.create_text(x, y - 1, anchor="nw", text="+%d" % extra,
                                    font=("TkDefaultFont", 8), fill="#444444")

    def _on_canvas_click(self, event):

        if not self.weeks or event.y < HEADER_HEIGHT:
            return
        cw, ch = self._grid_size()
        if cw <= 0 or ch <= 0:
            return
        col = min(int(event.x // cw), 6)
        row = min(int((event.y - HEADER_HEIGHT) // ch), len(self.weeks) - 1)
        self._select_day(self.weeks[row][col])

    def _draw_legend(self):
        lg = self.legend
        lg.delete("all")
        gray = "#555555"
        y = 7
        draw_marker(lg, "plant", 4, y, MARKER_SIZE, gray)
        lg.create_text(20, 12, anchor="w", text="Planting")
        draw_marker(lg, "harvest", 86, y, MARKER_SIZE, gray)
        lg.create_text(102, 12, anchor="w", text="Harvest due")
        draw_marker(lg, "task", 190, y, MARKER_SIZE, gray)
        lg.create_text(206, 12, anchor="w", text="Task")
        draw_marker(lg, "task", 252, y, MARKER_SIZE, gray, done=True)
        lg.create_text(268, 12, anchor="w", text="Task done")
        lg.create_text(350, 12, anchor="w",
                       text="Color = crop  (gray = task with no crop)")

    def _fill_details(self):
        self.day_label.config(text=self.selected.strftime("%A, %d %B %Y"))
        self.tree.delete(*self.tree.get_children())
        self.row_events = {}

        order = {"plant": 0, "harvest": 1, "task": 2}
        events = sorted(self.events.get(self.selected, []),
                        key=lambda e: order[e["kind"]])
        if not events:
            self.tree.insert("", "end", values=("", "Nothing planned for this day."))
            return
        for ev in events:
            row_id = "%s:%s" % (ev["kind"], ev["id"])
            self.tree.insert("", "end", iid=row_id,
                             values=(ev["type_text"], ev["text"]))
            self.row_events[row_id] = ev

    def _toggle_done(self):

        selection = self.tree.selection()
        ev = self.row_events.get(selection[0]) if selection else None
        if ev is None or ev["kind"] != "task":
            messagebox.showinfo("Pick a task",
                                "Click a task in the list first.", parent=self)
            return
        try:
            run_change(SQL_TOGGLE_DONE, (ev["id"],))
        except Exception as err:
            messagebox.showerror("Could not save",
                                 "The task was not updated.\n\nDetails: %s" % err,
                                 parent=self)
            return
        self.refresh()

    def _open_dialog(self, title):

        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.transient(self.winfo_toplevel())
        dlg.resizable(False, False)
        frame = ttk.Frame(dlg, padding=14)
        frame.pack(fill="both", expand=True)
        return dlg, frame

    @staticmethod
    def _lock_dialog(dlg):

        try:
            dlg.wait_visibility()
            dlg.grab_set()
        except tk.TclError:
            pass

    def _add_task(self):
        try:
            plots = run_select(SQL_PLOTS)
            plantings = run_select(SQL_GROWING_PLANTINGS)
        except Exception as err:
            messagebox.showerror("Could not open form",
                                 "Could not read the database.\n\nDetails: %s" % err,
                                 parent=self)
            return

        plot_word = "Bed" if get_mode() == "garden" else "Plot"
        plot_ids = {"(none)": None}
        for p in plots:
            plot_ids[p["name"]] = p["id"]
        planting_ids = {"(none)": None}
        planting_plot = {}
        for pl in plantings:
            label = "#%s  %s in %s (%s)" % (pl["id"], pl["crop_name"],
                                            pl["plot_name"],
                                            to_date(pl["plant_date"]))
            planting_ids[label] = pl["id"]
            planting_plot[pl["id"]] = pl["plot_id"]

        dlg, f = self._open_dialog("Add task")
        title_var = tk.StringVar()
        due_var = tk.StringVar(value=self.selected.isoformat())
        plot_var = tk.StringVar(value="(none)")
        planting_var = tk.StringVar(value="(none)")

        ttk.Label(f, text="Title *").grid(row=0, column=0, sticky="w", pady=4)
        title_entry = ttk.Entry(f, textvariable=title_var, width=40)
        title_entry.grid(row=0, column=1, pady=4)
        ttk.Label(f, text="Due date *").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=due_var, width=14).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(f, text="(YYYY-MM-DD)").grid(row=1, column=1, sticky="e")
        ttk.Label(f, text=plot_word).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=plot_var, values=list(plot_ids),
                     state="readonly", width=37).grid(row=2, column=1, pady=4)
        ttk.Label(f, text="Planting").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=planting_var, values=list(planting_ids),
                     state="readonly", width=37).grid(row=3, column=1, pady=4)

        def save():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("Missing title",
                                       "Please type a title for the task.", parent=dlg)
                return
            if len(title) > 200:
                messagebox.showwarning("Title too long",
                                       "Please keep the title under 200 characters.",
                                       parent=dlg)
                return
            due = parse_date(due_var.get())
            if due is None:
                messagebox.showwarning("Bad date",
                                       "Type the date like 2026-10-25 (year-month-day).",
                                       parent=dlg)
                return
            plot_id = plot_ids[plot_var.get()]
            planting_id = planting_ids[planting_var.get()]
            if planting_id is not None and plot_id is None:
                plot_id = planting_plot.get(planting_id)
            try:
                run_change(SQL_INSERT_TASK, (title, due, plot_id, planting_id))
            except Exception as err:
                messagebox.showerror("Could not save",
                                     "The task was not saved.\n\nDetails: %s" % err,
                                     parent=dlg)
                return
            dlg.destroy()
            self.selected = due
            self._set_month(due.year, due.month)   
            self.refresh()

        btns = ttk.Frame(f)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=save).pack(side="right", padx=6)
        dlg.bind("<Return>", lambda e: save())
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        title_entry.focus_set()
        self._lock_dialog(dlg)

    def _add_planting(self):
        try:
            plots = run_select(SQL_PLOTS)
            crops = run_select(SQL_CROPS)
        except Exception as err:
            messagebox.showerror("Could not open form",
                                 "Could not read the database.\n\nDetails: %s" % err,
                                 parent=self)
            return

        garden = (get_mode() == "garden")
        plot_word = "Bed" if garden else "Plot"
        crop_word = "Plant" if garden else "Crop"
        if not plots or not crops:
            messagebox.showinfo(
                "Add these first",
                "You need at least one %s and one %s before adding a planting.\n\n"
                "Add them in the Manage tab." % (plot_word.lower(), crop_word.lower()),
                parent=self)
            return

        plot_ids = {p["name"]: p["id"] for p in plots}
        crop_info = {c["name"]: (c["id"], int(c["days_to_harvest"] or 0)) for c in crops}

        dlg, f = self._open_dialog("Add planting")
        plot_var = tk.StringVar()
        crop_var = tk.StringVar()
        plant_var = tk.StringVar(value=self.selected.isoformat())
        harvest_var = tk.StringVar()
        harvest_touched = {"value": False}   

        def autofill_harvest(event=None):

            if harvest_touched["value"] or crop_var.get() not in crop_info:
                return
            start = parse_date(plant_var.get())
            if start is None:
                return
            days = crop_info[crop_var.get()][1]
            harvest_var.set((start + timedelta(days=days)).isoformat())

        ttk.Label(f, text=plot_word + " *").grid(row=0, column=0, sticky="w", pady=4)
        plot_box = ttk.Combobox(f, textvariable=plot_var, values=list(plot_ids),
                                state="readonly", width=30)
        plot_box.grid(row=0, column=1, pady=4)
        ttk.Label(f, text=crop_word + " *").grid(row=1, column=0, sticky="w", pady=4)
        crop_box = ttk.Combobox(f, textvariable=crop_var, values=list(crop_info),
                                state="readonly", width=30)
        crop_box.grid(row=1, column=1, pady=4)
        crop_box.bind("<<ComboboxSelected>>", autofill_harvest)

        ttk.Label(f, text="Plant date *").grid(row=2, column=0, sticky="w", pady=4)
        plant_entry = ttk.Entry(f, textvariable=plant_var, width=14)
        plant_entry.grid(row=2, column=1, sticky="w", pady=4)
        plant_entry.bind("<FocusOut>", autofill_harvest)
        ttk.Label(f, text="Expected harvest *").grid(row=3, column=0, sticky="w", pady=4)
        harvest_entry = ttk.Entry(f, textvariable=harvest_var, width=14)
        harvest_entry.grid(row=3, column=1, sticky="w", pady=4)
        harvest_entry.bind("<Key>", lambda e: harvest_touched.update(value=True))
        ttk.Label(f, text="Dates are YYYY-MM-DD. The harvest date fills in "
                          "automatically from the crop.",
                  foreground="#666666").grid(row=4, column=0, columnspan=2,
                                             sticky="w", pady=(4, 0))

        def save():
            if plot_var.get() not in plot_ids:
                messagebox.showwarning("Missing %s" % plot_word.lower(),
                                       "Please choose a %s." % plot_word.lower(),
                                       parent=dlg)
                return
            if crop_var.get() not in crop_info:
                messagebox.showwarning("Missing %s" % crop_word.lower(),
                                       "Please choose a %s." % crop_word.lower(),
                                       parent=dlg)
                return
            planted = parse_date(plant_var.get())
            harvest = parse_date(harvest_var.get())
            if planted is None or harvest is None:
                messagebox.showwarning("Bad date",
                                       "Type both dates like 2026-10-25 (year-month-day).",
                                       parent=dlg)
                return
            if harvest < planted:
                messagebox.showwarning("Check the dates",
                                       "The harvest date cannot be before the plant date.",
                                       parent=dlg)
                return
            try:
                run_change(SQL_INSERT_PLANTING,
                           (plot_ids[plot_var.get()], crop_info[crop_var.get()][0],
                            planted, harvest))
            except Exception as err:
                messagebox.showerror("Could not save",
                                     "The planting was not saved.\n\nDetails: %s" % err,
                                     parent=dlg)
                return
            dlg.destroy()
            self.selected = planted
            self._set_month(planted.year, planted.month)
            self.refresh()

        btns = ttk.Frame(f)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=save).pack(side="right", padx=6)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        plot_box.focus_set()
        self._lock_dialog(dlg)

    def auto_refresh(self):
        # The calendar may be destroyed when the user switches application
        # modes or closes the window. Do not schedule callbacks for dead tabs.
        try:
            if not self.winfo_exists():
                return
            self.refresh()
            if self.winfo_exists():
                self.root.after(5000, self.auto_refresh)
        except tk.TclError:
            return



if __name__ == "__main__":
    root = tk.Tk()
    root.title("Calendar tab test")
    root.geometry("1000x600")
    ttk.Style().theme_use("clam")
    tab = CalendarTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()
