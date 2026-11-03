

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




SQL_TASKS_FOR_DAY = """
    SELECT t.id, t.title, t.done AS is_done, p.name AS plot_name
    FROM tasks t
    LEFT JOIN plots p ON p.id = t.plot_id
    WHERE t.due_date = %s
    ORDER BY t.done, t.id
"""

SQL_TASK_COUNTS = """
    SELECT due_date, COUNT(*) AS total, SUM(done) AS done
    FROM tasks
    WHERE due_date BETWEEN %s AND %s
    GROUP BY due_date
"""

SQL_SET_DONE = "UPDATE tasks SET done = %s WHERE id = %s"

SQL_SHIFTS_FOR_WEEKDAY = """
    SELECT s.title, w.name AS worker_name, p.name AS plot_name,
           s.start_time, s.end_time
    FROM shifts s
    LEFT JOIN workers w ON w.id = s.worker_id
    LEFT JOIN plots p ON p.id = s.plot_id
    WHERE s.weekday = %s
    ORDER BY s.start_time
"""

SQL_HARVEST_PROGRESS = """
    SELECT c.name AS crop_name, p.name AS plot_name,
           pl.plant_date AS planting_date,
           pl.expected_harvest AS expected_harvest_date
    FROM plantings pl
    JOIN crops c ON c.id = pl.crop_id
    LEFT JOIN plots p ON p.id = pl.plot_id
    WHERE pl.status = 'growing'
      AND pl.plant_date <= %s
      AND pl.expected_harvest >= %s
    ORDER BY pl.expected_harvest
    LIMIT 10
"""

try:
    import settings
except ImportError:
    settings = None
try:
    import translations
except ImportError:
    translations = None

_FALLBACK_TEXT = {
    "farm": {
        "shifts_title": "Today's shifts",
        "no_shifts": "No shifts planned for this day.",
        "plots": "Fields",
    },
    "garden": {
        "shifts_title": "Today's care",
        "no_shifts": "Nothing growing in the garden on this day.",
        "plots": "Beds",
    },
}


def get_mode():

    if settings is not None:
        for name in ("get_mode", "get_current_mode"):
            if hasattr(settings, name):
                return str(getattr(settings, name)()).lower()
        if hasattr(settings, "MODE"):
            return str(settings.MODE).lower()
    return "farm"


def tr(key):

    if translations is not None and hasattr(translations, "t"):
        try:
            text = translations.t(key)
            if text and text != key:
                return text
        except Exception:
            pass
    return _FALLBACK_TEXT.get(get_mode(), _FALLBACK_TEXT["farm"]).get(key, key)



DOT_PENDING = "#d98a1f"   
DOT_ALL_DONE = "#3f9b4f"  
DOT_OVERDUE = "#c0392b"   

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def to_date(value):

    if isinstance(value, datetime):
        return value.date()
    return value


def format_time(value):

    if value is None:
        return "--:--"
    if isinstance(value, timedelta):
        minutes = int(value.total_seconds() // 60)
        return "%02d:%02d" % (minutes // 60, minutes % 60)
    return str(value)[:5]


def monday_of(day):

    return day - timedelta(days=day.weekday())


class TodayTab(ttk.Frame):


    def __init__(self, parent, app=None):
        super().__init__(parent, padding=10)
        self.app = app
        self.today = date.today()
        self.selected = self.today               
        self.week_start = monday_of(self.selected)
        self.task_vars = {}                      

        self._build_ui()
        self.refresh()

        self.root = ttk.Frame.winfo_toplevel(self)
        self.auto_refresh()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        nav = ttk.Frame(self)
        nav.grid(row=0, column=0, sticky="ew")
        nav.columnconfigure(2, weight=1)

        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._move_week(-1)).grid(row=0, column=0)
        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._move_week(1)).grid(row=0, column=1, padx=(4, 0))
        self.title_label = ttk.Label(nav, text="", font=("TkDefaultFont", 13, "bold"))
        self.title_label.grid(row=0, column=2, sticky="w", padx=10)
        ttk.Button(nav, text="Today", command=self._go_today).grid(row=0, column=3)

        strip = ttk.Frame(self)
        strip.grid(row=1, column=0, sticky="ew", pady=8)
        self.day_canvases = []
        bg = ttk.Style().lookup("TFrame", "background") or "#f0f0f0"
        for i in range(7):
            strip.columnconfigure(i, weight=1, uniform="day")
            cv = tk.Canvas(strip, height=62, highlightthickness=1,
                           highlightbackground="#bbbbbb", bg=bg, cursor="hand2")
            cv.grid(row=0, column=i, padx=2, sticky="ew")
            cv.bind("<Button-1>", lambda e, i=i: self._select_index(i))
            cv.bind("<Configure>", lambda e: self._draw_strip())
            self.day_canvases.append(cv)

        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3, uniform="col")
        body.columnconfigure(1, weight=2, uniform="col")
        body.rowconfigure(0, weight=1)

        self.tasks_box = ttk.LabelFrame(self, text="Tasks")
        self.tasks_box.grid(in_=body, row=0, column=0, sticky="nsew", padx=(0, 6))
        self.tasks_inner = ttk.Frame(self.tasks_box, padding=8)
        self.tasks_inner.pack(fill="both", expand=True)

        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=2)

        self.shift_box = ttk.LabelFrame(right, text="")
        self.shift_box.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.shift_inner = ttk.Frame(self.shift_box, padding=8)
        self.shift_inner.pack(fill="both", expand=True)

        self.harvest_box = ttk.LabelFrame(right, text="Harvest progress")
        self.harvest_box.grid(row=1, column=0, sticky="nsew")
        self.harvest_inner = ttk.Frame(self.harvest_box, padding=8)
        self.harvest_inner.pack(fill="both", expand=True)

    def _move_week(self, direction):
        self.week_start += timedelta(days=7 * direction)
        self.selected = self.week_start       
        self.refresh()

    def _go_today(self):
        self.today = date.today()
        self.selected = self.today
        self.week_start = monday_of(self.today)
        self.refresh()

    def _select_index(self, index):
        self.selected = self.week_start + timedelta(days=index)
        self.refresh()

    def refresh(self):

        self.today = date.today()
        try:
            self._load_counts()
            self._draw_strip()
            self._fill_tasks()
            self._fill_shifts_or_care()
            self._fill_harvest()
        except Exception as err:  
            messagebox.showerror(
                "Could not load Today",
                "Something went wrong while reading the database.\n\n"
                "Check that MySQL is running in XAMPP.\n\nDetails: %s" % err,
                parent=self)

        self.title_label.config(
            text=self.selected.strftime("%A, %d %B %Y")
            + ("  (today)" if self.selected == self.today else ""))

    def _load_counts(self):

        end = self.week_start + timedelta(days=6)
        rows = run_select(SQL_TASK_COUNTS, (self.week_start, end))
        self.counts = {}
        for r in rows:
            self.counts[to_date(r["due_date"])] = (
                int(r["total"] or 0), int(r["done"] or 0))

    def _draw_strip(self):
        if not hasattr(self, "counts"):
            return
        for i, cv in enumerate(self.day_canvases):
            day = self.week_start + timedelta(days=i)
            total, done = self.counts.get(day, (0, 0))
            cv.delete("all")
            w = cv.winfo_width() or 80
            is_sel = (day == self.selected)

            cv.config(highlightthickness=3 if is_sel else 1,
                      highlightbackground="#2e7d32" if is_sel else "#bbbbbb")
            weight = "bold" if day == self.today else "normal"
            cv.create_text(w // 2, 14, text=DAY_NAMES[i],
                           font=("TkDefaultFont", 9, weight))
            cv.create_text(w // 2, 32, text=str(day.day),
                           font=("TkDefaultFont", 13, weight))

            if total:
                if done == total:
                    color = DOT_ALL_DONE
                elif day < self.today:
                    color = DOT_OVERDUE
                else:
                    color = DOT_PENDING
                cv.create_oval(w // 2 - 5, 46, w // 2 + 5, 56,
                               fill=color, outline="")

    @staticmethod
    def _clear(frame):
        for child in frame.winfo_children():
            child.destroy()

    def _fill_tasks(self):
        self._clear(self.tasks_inner)
        self.task_vars = {}
        tasks = run_select(SQL_TASKS_FOR_DAY, (self.selected,))

        if not tasks:
            ttk.Label(self.tasks_inner,
                      text="No tasks for this day. 🌱").pack(anchor="w")
            return

        for t in tasks:
            var = tk.BooleanVar(value=bool(t["is_done"]))
            self.task_vars[t["id"]] = var
            text = t["title"]
            if t.get("plot_name"):
                text += "   (%s)" % t["plot_name"]
            ttk.Checkbutton(
                self.tasks_inner, text=text, variable=var,
                command=lambda tid=t["id"]: self._toggle_task(tid)
            ).pack(anchor="w", pady=2)

    def _toggle_task(self, task_id):
        done = 1 if self.task_vars[task_id].get() else 0
        try:
            run_change(SQL_SET_DONE, (done, task_id))
        except Exception as err:
            self.task_vars[task_id].set(not done)
            messagebox.showerror("Could not save",
                                 "The task was not updated.\n\nDetails: %s" % err,
                                 parent=self)
            return
        self._load_counts()
        self._draw_strip()

    def _fill_shifts_or_care(self):
        self._clear(self.shift_inner)
        self.shift_box.config(text=tr("shifts_title"))

        rows = run_select(SQL_SHIFTS_FOR_WEEKDAY, (self.selected.weekday(),))
        if not rows:
            ttk.Label(self.shift_inner, text=tr("no_shifts")).pack(anchor="w")
            return

        for r in rows:
            extras = []
            if r.get("worker_name"):
                extras.append(r["worker_name"])
            if r.get("plot_name"):
                extras.append(r["plot_name"])
            tail = "  (%s)" % ", ".join(extras) if extras else ""
            ttk.Label(
                self.shift_inner,
                text="%s – %s   %s%s" % (format_time(r["start_time"]),
                                          format_time(r["end_time"]),
                                          r["title"], tail)
            ).pack(anchor="w", pady=1)

    def _fill_harvest(self):
        self._clear(self.harvest_inner)
        rows = run_select(SQL_HARVEST_PROGRESS, (self.selected, self.selected))

        if not rows:
            ttk.Label(self.harvest_inner,
                      text="Nothing growing toward harvest on this day."
                      ).pack(anchor="w")
            return

        for r in rows:
            planted = to_date(r["planting_date"])
            harvest = to_date(r["expected_harvest_date"])
            total_days = max((harvest - planted).days, 1)   
            passed = (self.selected - planted).days
            percent = max(0, min(100, passed * 100 / total_days))
            days_left = (harvest - self.selected).days

            where = " – %s" % r["plot_name"] if r.get("plot_name") else ""
            if days_left == 0:
                note = "harvest today!"
            else:
                note = "%d day%s to harvest" % (days_left, "" if days_left == 1 else "s")

            ttk.Label(self.harvest_inner,
                      text="%s%s  (%s)" % (r["crop_name"], where, note)
                      ).pack(anchor="w")
            bar = ttk.Progressbar(self.harvest_inner, maximum=100,
                                  value=percent, mode="determinate")
            bar.pack(fill="x", pady=(0, 8))

    def auto_refresh(self):
        self.refresh()
        self.root.after(5000, self.auto_refresh)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Today tab test")
    root.geometry("900x520")
    ttk.Style().theme_use("clam")
    tab = TodayTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()
