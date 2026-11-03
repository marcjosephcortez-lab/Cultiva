

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


def words():

    if get_mode() == "garden":
        return {"heading": "Weekly care schedule", "item": "care routine",
                "add": "+ Add care routine", "worker": "Helper", "plot": "Bed"}
    return {"heading": "Weekly timetable", "item": "shift",
            "add": "+ Add shift", "worker": "Worker", "plot": "Plot"}


SQL_ALL_SHIFTS = """
    SELECT s.id, s.worker_id, s.title, s.weekday, s.start_time, s.end_time,
           s.plot_id, s.notes, w.name AS worker_name, p.name AS plot_name
    FROM shifts s
    LEFT JOIN workers w ON w.id = s.worker_id
    LEFT JOIN plots p ON p.id = s.plot_id
    ORDER BY s.weekday, s.start_time, s.id
"""

SQL_WORKERS = "SELECT id, name FROM workers WHERE active = 1 OR id = %s ORDER BY name"
SQL_PLOTS = "SELECT id, name FROM plots ORDER BY name"

SQL_INSERT_ONE = "(%s, %s, %s, %s, %s, %s, %s)"   
SQL_INSERT_START = ("INSERT INTO shifts "
                    "(worker_id, title, weekday, start_time, end_time, plot_id, notes) "
                    "VALUES ")

SQL_UPDATE = """
    UPDATE shifts
    SET worker_id = %s, title = %s, weekday = %s, start_time = %s,
        end_time = %s, plot_id = %s, notes = %s
    WHERE id = %s
"""
SQL_DELETE = "DELETE FROM shifts WHERE id = %s"

DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]

GUTTER = 52          
TOP_PAD = 8          
MIN_HOUR_H = 40      
HEADER_H = 28        
DEFAULT_START_H = 6  
DEFAULT_END_H = 18   

PALETTE = [("#cfe8cf", "#4c9f50"), ("#ffe3b3", "#d98a1f"),
           ("#cfe3f7", "#3b7dbf"), ("#f6d0d8", "#c0506b"),
           ("#e3d6f3", "#7e57c2"), ("#d4efe9", "#2a9d8f"),
           ("#f7ecb5", "#b59a1a"), ("#ffd6c2", "#d2693c")]
NO_WORKER = ("#e2e2e2", "#8a8a8a")


def to_minutes(value):

    if value is None:
        return 0
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    if hasattr(value, "hour"):                      
        return value.hour * 60 + value.minute
    parts = str(value).split(":")
    return int(parts[0]) * 60 + int(parts[1])


def fmt_minutes(minutes):

    return "%02d:%02d" % (minutes // 60, minutes % 60)


def parse_time(text):

    try:
        hours_text, minutes_text = text.strip().split(":")
        hours, minutes = int(hours_text), int(minutes_text)
    except ValueError:
        return None
    if 0 <= hours <= 23 and 0 <= minutes <= 59:
        return hours * 60 + minutes
    return None


def sql_time(minutes):

    return "%02d:%02d:00" % (minutes // 60, minutes % 60)


def layout_day(shifts):

    shifts.sort(key=lambda s: (s["start"], s["end"]))

    groups, current, current_end = [], [], -1
    for s in shifts:
        if current and s["start"] >= current_end:
            groups.append(current)
            current, current_end = [], -1
        current.append(s)
        current_end = max(current_end, s["end"])
    if current:
        groups.append(current)

    for group in groups:
        lane_ends = []                       
        for s in group:
            for i, free_at in enumerate(lane_ends):
                if s["start"] >= free_at:    
                    s["lane"] = i
                    lane_ends[i] = s["end"]
                    break
            else:                            
                s["lane"] = len(lane_ends)
                lane_ends.append(s["end"])
        for s in group:
            s["lanes"] = len(lane_ends)


class TimetableTab(ttk.Frame):


    def __init__(self, parent, app=None):
        super().__init__(parent, padding=10)
        self.app = app
        self.shifts = []                  
        self.start_h = DEFAULT_START_H    
        self.end_h = DEFAULT_END_H        
        self.geom = None                  

        self._build_ui()
        self.refresh()

        self.root = ttk.Frame.winfo_toplevel(self)
        self.auto_refresh()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)
        self.heading = ttk.Label(top, text="", font=("TkDefaultFont", 13, "bold"))
        self.heading.grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="Click a block to edit it. Click an empty spot "
                            "to add one there.",
                  foreground="#666666").grid(row=0, column=1, sticky="w", padx=12)
        self.add_button = ttk.Button(top, text="+ Add shift", command=self._add)
        self.add_button.grid(row=0, column=2)

        grid_area = ttk.Frame(self)
        grid_area.grid(row=1, column=0, sticky="nsew")
        grid_area.columnconfigure(0, weight=1)
        grid_area.rowconfigure(1, weight=1)

        self.header = tk.Canvas(grid_area, height=HEADER_H, bg="white",
                                highlightthickness=0)
        self.header.grid(row=0, column=0, sticky="ew")

        self.body = tk.Canvas(grid_area, bg="white", highlightthickness=1,
                              highlightbackground="#bbbbbb", height=320)
        self.body.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(grid_area, orient="vertical", command=self.body.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.body.configure(yscrollcommand=scroll.set)

        self.body.bind("<Configure>", lambda e: self._redraw())
        self.body.bind("<Button-1>", self._on_click)
        self.body.bind("<Enter>", lambda e: self.body.bind_all(
            "<MouseWheel>", self._on_wheel))
        self.body.bind("<Leave>", lambda e: self.body.unbind_all("<MouseWheel>"))

        self.legend = ttk.Frame(self)
        self.legend.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _on_wheel(self, event):
        self.body.yview_scroll(int(-event.delta / 120), "units")

    def refresh(self):

        w = words()
        self.heading.config(text=w["heading"])
        self.add_button.config(text=w["add"])
        try:
            self._load_shifts()
        except Exception as err:    
            self.shifts = []
            messagebox.showerror(
                "Could not load the timetable",
                "Something went wrong while reading the database.\n\n"
                "Check that MySQL is running in XAMPP.\n\nDetails: %s" % err,
                parent=self)
        self._fill_legend()
        self._redraw()

    def _load_shifts(self):
        rows = run_select(SQL_ALL_SHIFTS)
        shifts = []
        for r in rows:
            start = to_minutes(r["start_time"])
            end = to_minutes(r["end_time"])
            if end <= start:        
                continue
            wid = r["worker_id"]
            shifts.append({
                "id": r["id"], "worker_id": wid, "title": r["title"],
                "day": int(r["weekday"]), "start": start, "end": end,
                "plot_id": r["plot_id"], "notes": r["notes"],
                "worker_name": r["worker_name"], "plot_name": r["plot_name"],
                "colors": PALETTE[wid % len(PALETTE)] if wid else NO_WORKER,
            })

        start_h, end_h = DEFAULT_START_H, DEFAULT_END_H
        for s in shifts:
            start_h = min(start_h, s["start"] // 60)
            end_h = max(end_h, -(-s["end"] // 60))     
        self.start_h, self.end_h = start_h, min(end_h, 24)

        for day in range(7):
            layout_day([s for s in shifts if s["day"] == day])
        self.shifts = shifts

    def _fill_legend(self):
        for child in self.legend.winfo_children():
            child.destroy()
        seen = {}
        has_unassigned = False
        for s in self.shifts:
            if s["worker_id"]:
                seen[s["worker_id"]] = (s["worker_name"], s["colors"])
            else:
                has_unassigned = True
        entries = sorted(seen.values(), key=lambda item: item[0] or "")
        if has_unassigned:
            entries.append(("No %s" % words()["worker"].lower(), NO_WORKER))
        for name, (fill, outline) in entries:
            chip = tk.Label(self.legend, width=2, bg=fill, bd=1, relief="solid",
                            highlightbackground=outline)
            chip.pack(side="left", padx=(0, 4))
            ttk.Label(self.legend, text=name).pack(side="left", padx=(0, 14))

    def _redraw(self):
        cv = self.body
        cv.delete("all")
        self.header.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 120 or h < 60:
            return                          

        n_hours = self.end_h - self.start_h
        hour_h = max(MIN_HOUR_H, (h - 2 * TOP_PAD) / n_hours)
        total_h = n_hours * hour_h + 2 * TOP_PAD
        col_w = (w - GUTTER) / 7.0
        cv.configure(scrollregion=(0, 0, w, total_h))
        self.geom = {"hour_h": hour_h, "col_w": col_w}

        today_col = date.today().weekday()

        for c, name in enumerate(DAY_SHORT):
            x0 = GUTTER + c * col_w
            self.header.create_rectangle(
                x0, 0, x0 + col_w, HEADER_H, outline="#c8c8c8",
                fill="#fff3c4" if c == today_col else "#f2f2f2")
            self.header.create_text(
                x0 + col_w / 2, HEADER_H / 2, text=name,
                font=("TkDefaultFont", 10, "bold"), fill="#333333")

        tx = GUTTER + today_col * col_w
        cv.create_rectangle(tx, 0, tx + col_w, total_h,
                            fill="#fffbe6", outline="")

        for i in range(n_hours + 1):
            y = TOP_PAD + i * hour_h
            cv.create_line(GUTTER, y, w, y, fill="#d0d0d0")
            cv.create_text(GUTTER - 6, y, anchor="e",
                           text=fmt_minutes((self.start_h + i) * 60),
                           font=("TkDefaultFont", 8), fill="#666666")
            if i < n_hours:
                cv.create_line(GUTTER, y + hour_h / 2, w, y + hour_h / 2,
                               fill="#ececec", dash=(2, 4))

        for c in range(8):
            x = GUTTER + c * col_w
            cv.create_line(x, TOP_PAD, x, total_h - TOP_PAD, fill="#c8c8c8")

        for s in self.shifts:
            self._draw_block(s, hour_h, col_w)

        now = datetime.now()
        now_min = now.hour * 60 + now.minute
        if self.start_h * 60 <= now_min <= self.end_h * 60:
            y = TOP_PAD + (now_min - self.start_h * 60) / 60.0 * hour_h
            cv.create_line(tx, y, tx + col_w, y, fill="#c0392b", width=2)

        if not self.shifts:
            cv.create_text(GUTTER + (w - GUTTER) / 2, total_h / 2,
                           text="Nothing scheduled yet.\n"
                                "Click an empty spot or press \"%s\"." % words()["add"],
                           font=("TkDefaultFont", 11), fill="#888888",
                           justify="center")

    def _draw_block(self, s, hour_h, col_w):

        cv = self.body
        lane_w = (col_w - 4) / s["lanes"]
        x0 = GUTTER + s["day"] * col_w + 2 + s["lane"] * lane_w
        x1 = x0 + lane_w
        y0 = TOP_PAD + (s["start"] - self.start_h * 60) / 60.0 * hour_h
        y1 = TOP_PAD + (s["end"] - self.start_h * 60) / 60.0 * hour_h
        fill, outline = s["colors"]
        tag = "shift:%d" % s["id"]       

        cv.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1,
                            fill=fill, outline=outline, width=2, tags=(tag,))

        height = y1 - y0
        lines = [s["title"]]
        if height >= 40:
            lines.append("%s - %s" % (fmt_minutes(s["start"]), fmt_minutes(s["end"])))
        if height >= 58 and s["worker_name"]:
            lines.append(s["worker_name"])
        if height >= 74 and s["plot_name"]:
            lines.append(s["plot_name"])
        cv.create_text(x0 + 5, y0 + 4, anchor="nw", text="\n".join(lines),
                       width=max(int(lane_w - 10), 20),
                       font=("TkDefaultFont", 8), fill="#222222", tags=(tag,))

    def _on_click(self, event):
        if not self.geom:
            return
        cx = self.body.canvasx(event.x)
        cy = self.body.canvasy(event.y)

        for item in reversed(self.body.find_overlapping(cx, cy, cx, cy)):
            for tag in self.body.gettags(item):
                if tag.startswith("shift:"):
                    shift_id = int(tag.split(":")[1])
                    for s in self.shifts:
                        if s["id"] == shift_id:
                            self._open_form(shift=s)
                            return

        if cx < GUTTER:
            return
        day = int((cx - GUTTER) // self.geom["col_w"])
        if not 0 <= day <= 6:
            return
        minutes = self.start_h * 60 + (cy - TOP_PAD) / self.geom["hour_h"] * 60
        minutes = max(0, min(int(minutes // 30) * 30, 23 * 60))   
        self._open_form(day=day, start_min=minutes)

    def _add(self):

        self._open_form(day=date.today().weekday(), start_min=7 * 60)

    def _open_form(self, shift=None, day=None, start_min=None):

        editing = shift is not None
        w = words()
        try:
            current_worker = shift["worker_id"] if editing and shift["worker_id"] else 0
            workers = run_select(SQL_WORKERS, (current_worker,))
            plots = run_select(SQL_PLOTS)
        except Exception as err:
            messagebox.showerror("Could not open the form",
                                 "Could not read the database.\n\nDetails: %s" % err,
                                 parent=self)
            return

        worker_ids = {"(none)": None}
        for r in workers:
            label = r["name"]
            if label in worker_ids:                    
                label = "%s (#%s)" % (r["name"], r["id"])
            worker_ids[label] = r["id"]
        plot_ids = {"(none)": None}
        for r in plots:
            plot_ids[r["name"]] = r["id"]

        def label_for(mapping, wanted_id):
            for label, value in mapping.items():
                if value == wanted_id:
                    return label
            return "(none)"

        dlg = tk.Toplevel(self)
        dlg.title(("Edit " if editing else "Add ") + w["item"])
        dlg.transient(self.winfo_toplevel())
        dlg.resizable(False, False)
        f = ttk.Frame(dlg, padding=14)
        f.pack(fill="both", expand=True)

        if editing:
            start0, end0 = shift["start"], shift["end"]
        else:
            start0 = start_min if start_min is not None else 7 * 60
            end0 = min(start0 + 60, 23 * 60 + 59)
        title_var = tk.StringVar(value=shift["title"] if editing else "")
        worker_var = tk.StringVar(
            value=label_for(worker_ids, shift["worker_id"]) if editing else "(none)")
        plot_var = tk.StringVar(
            value=label_for(plot_ids, shift["plot_id"]) if editing else "(none)")
        start_var = tk.StringVar(value=fmt_minutes(start0))
        end_var = tk.StringVar(value=fmt_minutes(end0))
        notes_var = tk.StringVar(value=(shift["notes"] or "") if editing else "")

        row = 0
        ttk.Label(f, text="Title *").grid(row=row, column=0, sticky="w", pady=4)
        title_entry = ttk.Entry(f, textvariable=title_var, width=38)
        title_entry.grid(row=row, column=1, columnspan=2, sticky="w", pady=4)

        row += 1
        ttk.Label(f, text=w["worker"]).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=worker_var, values=list(worker_ids),
                     state="readonly", width=35).grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4)

        row += 1
        ttk.Label(f, text=w["plot"]).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(f, textvariable=plot_var, values=list(plot_ids),
                     state="readonly", width=35).grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4)

        row += 1
        ttk.Label(f, text="Day *" if editing else "Days *").grid(
            row=row, column=0, sticky="nw", pady=4)
        day_var = tk.StringVar(value=DAY_FULL[shift["day"]] if editing else "")
        day_vars = []
        if editing:
            ttk.Combobox(f, textvariable=day_var, values=DAY_FULL,
                         state="readonly", width=15).grid(
                row=row, column=1, sticky="w", pady=4)
        else:
            default_day = day if day is not None else date.today().weekday()
            days_box = ttk.Frame(f)
            days_box.grid(row=row, column=1, columnspan=2, sticky="w", pady=4)
            for i, name in enumerate(DAY_SHORT):
                var = tk.BooleanVar(value=(i == default_day))
                day_vars.append(var)
                ttk.Checkbutton(days_box, text=name, variable=var).grid(
                    row=0, column=i, padx=(0, 6))
            quick = ttk.Frame(f)
            quick.grid(row=row + 1, column=1, columnspan=2, sticky="w")

            def set_days(indexes):
                for i, var in enumerate(day_vars):
                    var.set(i in indexes)

            ttk.Button(quick, text="Mon-Fri",
                       command=lambda: set_days(range(0, 5))).pack(side="left")
            ttk.Button(quick, text="Every day",
                       command=lambda: set_days(range(0, 7))).pack(side="left", padx=4)
            ttk.Button(quick, text="Clear",
                       command=lambda: set_days([])).pack(side="left")
            row += 1

        row += 1
        ttk.Label(f, text="Start *").grid(row=row, column=0, sticky="w", pady=(10, 4))
        times = ttk.Frame(f)
        times.grid(row=row, column=1, columnspan=2, sticky="w", pady=(10, 4))
        ttk.Entry(times, textvariable=start_var, width=7).pack(side="left")
        ttk.Label(times, text="  End *  ").pack(side="left")
        ttk.Entry(times, textvariable=end_var, width=7).pack(side="left")
        ttk.Label(times, text="  (HH:MM, 24-hour)",
                  foreground="#666666").pack(side="left")

        row += 1
        ttk.Label(f, text="Notes").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=notes_var, width=38).grid(
            row=row, column=1, columnspan=2, sticky="w", pady=4)

        def save():
            title = title_var.get().strip()
            if not title:
                messagebox.showwarning("Missing title",
                                       "Please type a title.", parent=dlg)
                return
            if len(title) > 150:
                messagebox.showwarning("Title too long",
                                       "Please keep the title under 150 characters.",
                                       parent=dlg)
                return
            start = parse_time(start_var.get())
            end = parse_time(end_var.get())
            if start is None or end is None:
                messagebox.showwarning("Bad time",
                                       "Type the times like 07:30 (hours:minutes, "
                                       "24-hour).", parent=dlg)
                return
            if end <= start:
                messagebox.showwarning("Check the times",
                                       "The end time must be after the start time.\n"
                                       "(Overnight shifts: make one for each day.)",
                                       parent=dlg)
                return
            if editing:
                if day_var.get() not in DAY_FULL:
                    messagebox.showwarning("Missing day", "Please choose a day.",
                                           parent=dlg)
                    return
                days = [DAY_FULL.index(day_var.get())]
            else:
                days = [i for i, v in enumerate(day_vars) if v.get()]
                if not days:
                    messagebox.showwarning("Missing days",
                                           "Tick at least one day.", parent=dlg)
                    return

            worker_id = worker_ids.get(worker_var.get())
            plot_id = plot_ids.get(plot_var.get())
            notes = notes_var.get().strip() or None

            if worker_id is not None:
                try:
                    clashes = self._find_clashes(worker_id, days, start, end,
                                                 shift["id"] if editing else 0)
                except Exception:
                    clashes = []
                if clashes:
                    lines = ["%s %s-%s  %s" % (DAY_SHORT[c["day"]],
                                               fmt_minutes(c["start"]),
                                               fmt_minutes(c["end"]), c["title"])
                             for c in clashes[:4]]
                    more = "\n..." if len(clashes) > 4 else ""
                    if not messagebox.askyesno(
                            "Overlap",
                            "This person already has:\n\n%s%s\n\nSave anyway?"
                            % ("\n".join(lines), more), parent=dlg):
                        return

            try:
                if editing:
                    run_change(SQL_UPDATE, (worker_id, title, days[0], sql_time(start),
                                            sql_time(end), plot_id, notes,
                                            shift["id"]))
                else:
                    params = []
                    for d in days:
                        params += [worker_id, title, d, sql_time(start),
                                   sql_time(end), plot_id, notes]
                    run_change(SQL_INSERT_START + ", ".join([SQL_INSERT_ONE] * len(days)),
                               tuple(params))
            except Exception as err:
                messagebox.showerror("Could not save",
                                     "Nothing was saved.\n\nDetails: %s" % err,
                                     parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        def delete():
            if not messagebox.askyesno(
                    "Delete",
                    "Delete \"%s\" (%s %s-%s)?" % (
                        shift["title"], DAY_SHORT[shift["day"]],
                        fmt_minutes(shift["start"]), fmt_minutes(shift["end"])),
                    parent=dlg):
                return
            try:
                run_change(SQL_DELETE, (shift["id"],))
            except Exception as err:
                messagebox.showerror("Could not delete",
                                     "Nothing was deleted.\n\nDetails: %s" % err,
                                     parent=dlg)
                return
            dlg.destroy()
            self.refresh()

        row += 1
        btns = ttk.Frame(f)
        btns.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        if editing:
            ttk.Button(btns, text="Delete", command=delete).pack(side="left")
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="Save", command=save).pack(side="right", padx=6)

        dlg.bind("<Escape>", lambda e: dlg.destroy())
        title_entry.focus_set()
        try:                          
            dlg.wait_visibility()
            dlg.grab_set()
        except tk.TclError:
            pass

    def _find_clashes(self, worker_id, days, start, end, exclude_id):

        marks = ", ".join(["%s"] * len(days))
        sql = ("SELECT id, title, weekday, start_time, end_time FROM shifts "
               "WHERE worker_id = %s AND id <> %s AND weekday IN (" + marks + ") "
               "AND start_time < %s AND end_time > %s")
        rows = run_select(sql, (worker_id, exclude_id) + tuple(days)
                          + (sql_time(end), sql_time(start)))
        return [{"title": r["title"], "day": int(r["weekday"]),
                 "start": to_minutes(r["start_time"]),
                 "end": to_minutes(r["end_time"])} for r in rows]

    def auto_refresh(self):
        self.refresh()
        self.root.after(5000, self.auto_refresh)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Timetable tab test")
    root.geometry("1000x620")
    ttk.Style().theme_use("clam")
    tab = TimetableTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()
