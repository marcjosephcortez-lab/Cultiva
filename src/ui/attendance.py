

import calendar
import csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
from decimal import Decimal

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




SQL_DAILY = """
    SELECT w.id, w.name, w.role, a.status, a.time_in, a.time_out, a.remarks
    FROM workers w
    LEFT JOIN attendance a ON a.worker_id = w.id AND a.att_date = %s
    WHERE w.active = 1 OR a.id IS NOT NULL
    ORDER BY w.name
"""

SQL_UPSERT_START = ("INSERT INTO attendance "
                    "(worker_id, att_date, status, time_in, time_out, remarks) VALUES ")
SQL_UPSERT_ROW = "(%s, %s, %s, %s, %s, %s)"
SQL_UPSERT_END = (" ON DUPLICATE KEY UPDATE status = VALUES(status), "
                  "time_in = VALUES(time_in), time_out = VALUES(time_out), "
                  "remarks = VALUES(remarks)")

SQL_DELETE_START = "DELETE FROM attendance WHERE att_date = %s AND worker_id IN ("

SQL_MONTH = """
    SELECT w.id, w.name, w.daily_rate, a.status, COUNT(a.id) AS cnt
    FROM workers w
    LEFT JOIN attendance a ON a.worker_id = w.id
                          AND a.att_date BETWEEN %s AND %s
    WHERE w.active = 1 OR a.id IS NOT NULL
    GROUP BY w.id, w.name, w.daily_rate, a.status
    ORDER BY w.name
"""


STATUSES = [("present", "Present"), ("late", "Late"), ("half_day", "Half day"),
            ("absent", "Absent"), ("leave", "Leave")]
STATUS_KEYS = [key for key, _ in STATUSES]

PAY_FACTOR = {
    "present": Decimal("1"),
    "late": Decimal("1"),
    "half_day": Decimal("0.5"),
    "absent": Decimal("0"),
    "leave": Decimal("0"),
}
PAY_RULE_TEXT = ("Pay estimate = daily rate x (present + late + half of the "
                 "half days). Absent and leave days are not paid.")


def to_minutes(value):

    if value is None:
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60)
    if hasattr(value, "hour"):                      
        return value.hour * 60 + value.minute
    parts = str(value).split(":")
    return int(parts[0]) * 60 + int(parts[1])


def fmt_minutes(minutes):

    if minutes is None:
        return ""
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

    if minutes is None:
        return None
    return "%02d:%02d:00" % (minutes // 60, minutes % 60)


def parse_date(text):

    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def build_summary(rows):

    by_worker, order = {}, []
    for r in rows:
        wid = r["id"]
        if wid not in by_worker:
            by_worker[wid] = {"name": r["name"],
                              "rate": Decimal(str(r["daily_rate"] or 0)),
                              "counts": {key: 0 for key in STATUS_KEYS}}
            order.append(wid)
        if r["status"] in by_worker[wid]["counts"]:
            by_worker[wid]["counts"][r["status"]] += int(r["cnt"])

    workers = []
    totals = {"counts": {key: 0 for key in STATUS_KEYS},
              "days": Decimal("0"), "pay": Decimal("0.00")}
    for wid in order:
        w = by_worker[wid]
        w["days"] = sum((PAY_FACTOR[k] * w["counts"][k] for k in STATUS_KEYS),
                        Decimal("0"))
        w["pay"] = (w["days"] * w["rate"]).quantize(Decimal("0.01"))
        workers.append(w)
        for k in STATUS_KEYS:
            totals["counts"][k] += w["counts"][k]
        totals["days"] += w["days"]
        totals["pay"] += w["pay"]
    return workers, totals


def write_summary_csv(path, month_text, workers, totals):

    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        out = csv.writer(handle)
        out.writerow(["Month", "Worker"] + [label for _, label in STATUSES]
                     + ["Paid days", "Daily rate", "Pay estimate"])
        for w in workers:
            out.writerow([month_text, w["name"]]
                         + [w["counts"][k] for k in STATUS_KEYS]
                         + ["%g" % float(w["days"]), "%.2f" % w["rate"],
                            "%.2f" % w["pay"]])
        out.writerow([month_text, "TOTAL"]
                     + [totals["counts"][k] for k in STATUS_KEYS]
                     + ["%g" % float(totals["days"]), "", "%.2f" % totals["pay"]])


class AttendanceTab(ttk.Frame):


    def __init__(self, parent, app=None):
        super().__init__(parent, padding=10)
        self.app = app
        self.sheet_date = date.today()                 
        self.month_year = date.today().year            
        self.month_num = date.today().month
        self.rows = []         
        self.dirty = False     
        self._loading = False  
        self.summary = ([], None)
        self.root = ttk.Frame.winfo_toplevel(self)

        # Build all widgets before refresh accesses self.sheet and other UI fields.
        self._build_ui()
        self.auto_refresh()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.sub = ttk.Notebook(self)
        self.sub.grid(row=0, column=0, sticky="nsew")
        self.daily_frame = ttk.Frame(self.sub, padding=8)
        self.month_frame = ttk.Frame(self.sub, padding=8)
        self.sub.add(self.daily_frame, text="Daily sheet")
        self.sub.add(self.month_frame, text="Monthly summary")
        self.sub.bind("<<NotebookTabChanged>>", self._on_subtab)

        self._build_daily()
        self._build_monthly()

    def _build_daily(self):
        f = self.daily_frame
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        nav = ttk.Frame(f)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        nav.columnconfigure(3, weight=1)
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._change_date(self.sheet_date - timedelta(days=1))
                   ).grid(row=0, column=0)
        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._change_date(self.sheet_date + timedelta(days=1))
                   ).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(nav, text="Today",
                   command=lambda: self._change_date(date.today())
                   ).grid(row=0, column=2, padx=(8, 0))
        self.date_label = ttk.Label(nav, text="", font=("TkDefaultFont", 13, "bold"))
        self.date_label.grid(row=0, column=3, sticky="w", padx=12)
        self.goto_var = tk.StringVar()
        goto = ttk.Entry(nav, textvariable=self.goto_var, width=12)
        goto.grid(row=0, column=4)
        goto.bind("<Return>", lambda e: self._goto_date())
        ttk.Button(nav, text="Go to date",
                   command=self._goto_date).grid(row=0, column=5, padx=(4, 0))

        area = ttk.Frame(f)
        area.grid(row=1, column=0, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        self.sheet_canvas = tk.Canvas(area, highlightthickness=1,
                                      highlightbackground="#bbbbbb", bg="white")
        self.sheet_canvas.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(area, orient="vertical",
                               command=self.sheet_canvas.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.sheet_canvas.configure(yscrollcommand=scroll.set)

        self.sheet = ttk.Frame(self.sheet_canvas, padding=6)
        self.sheet_window = self.sheet_canvas.create_window(
            (0, 0), window=self.sheet, anchor="nw")
        self.sheet.bind("<Configure>", lambda e: self.sheet_canvas.configure(
            scrollregion=self.sheet_canvas.bbox("all")))
        self.sheet_canvas.bind("<Configure>", lambda e: self.sheet_canvas.itemconfigure(
            self.sheet_window, width=e.width))
        self.sheet_canvas.bind("<Enter>", lambda e: self.sheet_canvas.bind_all(
            "<MouseWheel>", self._on_wheel))
        self.sheet_canvas.bind("<Leave>", lambda e: self.sheet_canvas.unbind_all(
            "<MouseWheel>"))

        self.counts_label = ttk.Label(f, text="")
        self.counts_label.grid(row=2, column=0, sticky="w", pady=(8, 0))

        bar = ttk.Frame(f)
        bar.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(bar, text="Mark everyone present",
                   command=self._mark_all_present).pack(side="left")
        self.state_label = ttk.Label(bar, text="")
        self.state_label.pack(side="left", padx=12)
        ttk.Button(bar, text="Save", command=self._save).pack(side="right")
        ttk.Button(bar, text="Reload",
                   command=self._reload_clicked).pack(side="right", padx=6)

    def _on_wheel(self, event):
        self.sheet_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _build_monthly(self):
        f = self.month_frame
        f.columnconfigure(0, weight=1)
        f.rowconfigure(1, weight=1)

        nav = ttk.Frame(f)
        nav.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        nav.columnconfigure(3, weight=1)
        ttk.Button(nav, text="◀", width=3,
                   command=lambda: self._move_month(-1)).grid(row=0, column=0)
        ttk.Button(nav, text="▶", width=3,
                   command=lambda: self._move_month(1)).grid(row=0, column=1, padx=(4, 0))
        ttk.Button(nav, text="This month",
                   command=self._this_month).grid(row=0, column=2, padx=(8, 0))
        self.month_label = ttk.Label(nav, text="", font=("TkDefaultFont", 13, "bold"))
        self.month_label.grid(row=0, column=3, sticky="w", padx=12)
        ttk.Button(nav, text="Export CSV",
                   command=self._export_csv).grid(row=0, column=4)

        columns = ["worker"] + STATUS_KEYS + ["days", "rate", "pay"]
        self.month_tree = ttk.Treeview(f, columns=columns, show="headings",
                                       selectmode="browse")
        self.month_tree.heading("worker", text="Worker")
        self.month_tree.column("worker", width=160, anchor="w")
        for key, label in STATUSES:
            self.month_tree.heading(key, text=label)
            self.month_tree.column(key, width=70, anchor="e")
        self.month_tree.heading("days", text="Paid days")
        self.month_tree.column("days", width=80, anchor="e")
        self.month_tree.heading("rate", text="Daily rate")
        self.month_tree.column("rate", width=90, anchor="e")
        self.month_tree.heading("pay", text="Pay estimate")
        self.month_tree.column("pay", width=110, anchor="e")
        self.month_tree.tag_configure("total", font=("TkDefaultFont", 9, "bold"))
        self.month_tree.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(f, orient="vertical", command=self.month_tree.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.month_tree.configure(yscrollcommand=scroll.set)

        ttk.Label(f, text=PAY_RULE_TEXT, foreground="#666666").grid(
            row=2, column=0, sticky="w", pady=(8, 0))

    def refresh(self):

        if not self.dirty:
            self._load_daily()
        self._load_monthly()

    def _on_subtab(self, event=None):
        self._load_monthly()

    def _load_daily(self):
        self._loading = True
        for child in self.sheet.winfo_children():
            child.destroy()
        self.rows = []
        self.date_label.config(text=self.sheet_date.strftime("%A, %d %B %Y"))
        self.goto_var.set(self.sheet_date.isoformat())

        try:
            data = run_select(SQL_DAILY, (self.sheet_date,))
        except Exception as err:     
            data = []
            messagebox.showerror(
                "Could not load attendance",
                "Something went wrong while reading the database.\n\n"
                "Check that MySQL is running in XAMPP.\n\nDetails: %s" % err,
                parent=self)

        if not data:
            ttk.Label(self.sheet,
                      text="No workers yet. Add them in the Manage tab first."
                      ).grid(row=0, column=0, padx=8, pady=8)
        else:
            self._build_sheet_header()
            for i, r in enumerate(data, start=1):
                self._build_sheet_row(i, r)

        self._loading = False
        self.dirty = False
        self._update_state()

    def _build_sheet_header(self):
        heads = ["Worker"] + [label for _, label in STATUSES] + \
                ["In (HH:MM)", "Out (HH:MM)", "Remarks", ""]
        for c, text in enumerate(heads):
            ttk.Label(self.sheet, text=text,
                      font=("TkDefaultFont", 9, "bold")).grid(
                row=0, column=c, sticky="w", padx=4, pady=(0, 6))
        self.sheet.columnconfigure(8, weight=1)      

    def _build_sheet_row(self, row, r):

        status = r["status"] if r["status"] in STATUS_KEYS else "not_marked"
        status_var = tk.StringVar(value=status)
        in_var = tk.StringVar(value=fmt_minutes(to_minutes(r["time_in"])))
        out_var = tk.StringVar(value=fmt_minutes(to_minutes(r["time_out"])))
        rem_var = tk.StringVar(value=r["remarks"] or "")

        name = r["name"] + ("  (%s)" % r["role"] if r.get("role") else "")
        ttk.Label(self.sheet, text=name).grid(row=row, column=0, sticky="w",
                                              padx=4, pady=3)
        for c, (key, label) in enumerate(STATUSES, start=1):
            ttk.Radiobutton(self.sheet, text=label, value=key,
                            variable=status_var).grid(row=row, column=c,
                                                      sticky="w", padx=4)
        ttk.Entry(self.sheet, textvariable=in_var, width=7).grid(
            row=row, column=6, padx=4)
        ttk.Entry(self.sheet, textvariable=out_var, width=7).grid(
            row=row, column=7, padx=4)
        ttk.Entry(self.sheet, textvariable=rem_var).grid(
            row=row, column=8, sticky="ew", padx=4)
        ttk.Button(self.sheet, text="✕", width=3,
                   command=lambda v=status_var: v.set("not_marked")).grid(
            row=row, column=9, padx=4)

        for var in (status_var, in_var, out_var, rem_var):
            var.trace_add("write", self._on_change)
        self.rows.append({"worker_id": r["id"], "name": r["name"],
                          "status": status_var, "in": in_var,
                          "out": out_var, "rem": rem_var})

    def _on_change(self, *args):

        if self._loading:
            return
        self.dirty = True
        self._update_state()

    def _update_state(self):

        counts = {key: 0 for key in STATUS_KEYS}
        not_marked = 0
        for r in self.rows:
            value = r["status"].get()
            if value in counts:
                counts[value] += 1
            else:
                not_marked += 1
        parts = ["%s %d" % (label, counts[key]) for key, label in STATUSES]
        parts.append("Not marked %d" % not_marked)
        self.counts_label.config(text="   ".join(parts))
        self.state_label.config(
            text="Unsaved changes" if self.dirty else "All saved",
            foreground="#c0711f" if self.dirty else "#2e7d32")

    def _mark_all_present(self):
        if not self.rows:
            return
        would_change = [r for r in self.rows
                        if r["status"].get() not in ("not_marked", "present")]
        overwrite = True
        if would_change:
            answer = messagebox.askyesnocancel(
                "Mark everyone present",
                "%d worker(s) already have another status (late, absent ...).\n\n"
                "Yes = change everyone to Present\n"
                "No = only fill in the workers not marked yet\n"
                "Cancel = do nothing" % len(would_change), parent=self)
            if answer is None:
                return
            overwrite = answer
        for r in self.rows:
            if overwrite or r["status"].get() == "not_marked":
                r["status"].set("present")

    def _reload_clicked(self):
        if self.dirty and not messagebox.askyesno(
                "Discard changes",
                "Throw away the unsaved changes and reload this day?",
                parent=self):
            return
        self._load_daily()

    def _save(self):

        upserts, deletes = [], []
        for r in self.rows:
            status = r["status"].get()
            time_in_text = r["in"].get().strip()
            time_out_text = r["out"].get().strip()
            remarks = r["rem"].get().strip()

            time_in = parse_time(time_in_text) if time_in_text else None
            time_out = parse_time(time_out_text) if time_out_text else None
            if (time_in_text and time_in is None) or (time_out_text and time_out is None):
                messagebox.showwarning(
                    "Bad time",
                    "%s: type times like 07:30 (hours:minutes, 24-hour)." % r["name"],
                    parent=self)
                return False
            if time_in is not None and time_out is not None and time_out <= time_in:
                messagebox.showwarning(
                    "Check the times",
                    "%s: the time out must be after the time in." % r["name"],
                    parent=self)
                return False
            if len(remarks) > 255:
                messagebox.showwarning(
                    "Remarks too long",
                    "%s: keep remarks under 255 characters." % r["name"],
                    parent=self)
                return False

            if status == "not_marked" and time_in is None and time_out is None \
                    and not remarks:
                deletes.append(r["worker_id"])        
            else:
                upserts.append((r["worker_id"], self.sheet_date, status,
                                sql_time(time_in), sql_time(time_out),
                                remarks or None))

        try:
            if upserts:
                sql = (SQL_UPSERT_START + ", ".join([SQL_UPSERT_ROW] * len(upserts))
                       + SQL_UPSERT_END)
                params = tuple(value for row in upserts for value in row)
                run_change(sql, params)
            if deletes:
                sql = SQL_DELETE_START + ", ".join(["%s"] * len(deletes)) + ")"
                run_change(sql, (self.sheet_date,) + tuple(deletes))
        except Exception as err:
            messagebox.showerror("Could not save",
                                 "The sheet was not saved.\n\nDetails: %s" % err,
                                 parent=self)
            return False

        self.dirty = False
        self._update_state()
        self.state_label.config(
            text="Saved at %s" % datetime.now().strftime("%H:%M"),
            foreground="#2e7d32")
        self._load_monthly()
        return True

    def _change_date(self, new_date):

        if self.dirty:
            answer = messagebox.askyesnocancel(
                "Unsaved changes",
                "Save the changes for %s first?" % self.sheet_date.strftime("%d %B %Y"),
                parent=self)
            if answer is None:
                return
            if answer and not self._save():
                return
        self.sheet_date = new_date
        self.dirty = False
        self._load_daily()

    def _goto_date(self):
        picked = parse_date(self.goto_var.get())
        if picked is None:
            messagebox.showwarning("Bad date",
                                   "Type the date like 2026-10-25 (year-month-day).",
                                   parent=self)
            return
        self._change_date(picked)

    def _move_month(self, step):
        index = (self.month_year * 12 + self.month_num - 1) + step
        year, month = divmod(index, 12)
        self.month_year, self.month_num = year, month + 1
        self._load_monthly()

    def _this_month(self):
        today = date.today()
        self.month_year, self.month_num = today.year, today.month
        self._load_monthly()

    def _month_text(self):
        return "%04d-%02d" % (self.month_year, self.month_num)

    def _load_monthly(self):
        self.month_label.config(
            text=date(self.month_year, self.month_num, 1).strftime("%B %Y"))
        first = date(self.month_year, self.month_num, 1)
        last = date(self.month_year, self.month_num,
                    calendar.monthrange(self.month_year, self.month_num)[1])
        try:
            rows = run_select(SQL_MONTH, (first, last))
        except Exception as err:
            rows = []
            messagebox.showerror(
                "Could not load the summary",
                "Something went wrong while reading the database.\n\n"
                "Check that MySQL is running in XAMPP.\n\nDetails: %s" % err,
                parent=self)

        workers, totals = build_summary(rows)
        self.summary = (workers, totals)

        self.month_tree.delete(*self.month_tree.get_children())
        for w in workers:
            self.month_tree.insert("", "end", values=(
                [w["name"]] + [w["counts"][k] for k in STATUS_KEYS]
                + ["%g" % float(w["days"]), "{:,.2f}".format(w["rate"]),
                   "{:,.2f}".format(w["pay"])]))
        if workers:
            self.month_tree.insert("", "end", tags=("total",), values=(
                ["TOTAL"] + [totals["counts"][k] for k in STATUS_KEYS]
                + ["%g" % float(totals["days"]), "",
                   "{:,.2f}".format(totals["pay"])]))
        else:
            self.month_tree.insert("", "end",
                                   values=("No workers yet.",) + ("",) * 8)

    def _export_csv(self):
        workers, totals = self.summary
        if not workers:
            messagebox.showinfo("Nothing to export",
                                "There are no workers to put in the file.",
                                parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="Export attendance summary",
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
            initialfile="attendance_%s.csv" % self._month_text())
        if not path:
            return                       
        try:
            write_summary_csv(path, self._month_text(), workers, totals)
        except OSError as err:
            messagebox.showerror(
                "Could not save the file",
                "The file was not saved. Is it open in Excel?\n\nDetails: %s" % err,
                parent=self)
            return
        messagebox.showinfo("Exported", "Saved:\n%s" % path, parent=self)

    def auto_refresh(self):
        # Refresh only after the interface has been built, and stop safely
        # when the tab or application window has been destroyed.
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
    root.title("Attendance tab test")
    root.geometry("1100x600")
    ttk.Style().theme_use("clam")
    tab = AttendanceTab(root)
    tab.pack(fill="both", expand=True)
    root.mainloop()
