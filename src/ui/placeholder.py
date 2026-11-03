

from tkinter import ttk

import db
import translations

tr = translations.tr

CHECKS = {
    "today": ("SELECT COUNT(*) AS n FROM tasks", lambda: "tasks"),
    "agenda": ("SELECT COUNT(*) AS n FROM tasks", lambda: "tasks"),
    "calendar": ("SELECT COUNT(*) AS n FROM plantings", lambda: tr("plantings").lower()),
    "timetable": ("SELECT COUNT(*) AS n FROM shifts", lambda: tr("shifts").lower()),
    "attendance": ("SELECT COUNT(*) AS n FROM attendance", lambda: "attendance records"),
    "journal": ("SELECT COUNT(*) AS n FROM journal_entries", lambda: "journal entries"),
    "notes": ("SELECT COUNT(*) AS n FROM notes", lambda: "notes"),
    "manage": ("SELECT COUNT(*) AS n FROM plots", lambda: tr("plots").lower()),
}


def describe(key):

    texts = {
        "today": "A week strip, today's tasks, %s, and progress bars showing days left to harvest."
                 % tr("on_duty_today").lower(),
        "agenda": "Tasks grouped as Overdue, Today, Tomorrow and Later, with filters, "
                  "search and a quick-add row.",
        "calendar": "A month grid showing planting days, expected harvest days and task due dates.",
        "timetable": "A weekly grid of %s as colored blocks." % tr("shifts").lower(),
        "attendance": "A daily attendance sheet and a monthly summary with an estimated pay.",
        "journal": "Dated diary entries with mood or weather, attachments and a streak counter.",
        "notes": "Titled notes with photos, videos, audio, PDFs and Office files attached.",
        "manage": "Add, edit and delete %s, %s, %s and %s."
                  % (tr("plantings").lower(), tr("crops").lower(),
                     tr("plots").lower(), tr("workers").lower()),
    }
    return texts.get(key, "")


class PlaceholderTab(ttk.Frame):


    def __init__(self, parent, app, key, step):
        super().__init__(parent, padding=24)
        self.app = app
        self.key = key
        ttk.Label(self, text=tr("tab_" + key), style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="This screen is built in Step %d." % step,
                  style="Warn.TLabel").pack(anchor="w", pady=(4, 12))
        ttk.Label(self, text=describe(key), wraplength=680, justify="left").pack(anchor="w")
        ttk.Separator(self).pack(fill="x", pady=16)
        self.check_label = ttk.Label(self, text="Database check: ...", style="Muted.TLabel",
                                     wraplength=680, justify="left")
        self.check_label.pack(anchor="w")

    def refresh(self):

        sql, noun = CHECKS[self.key]
        try:
            row = db.query_one(sql)
        except db.DBError as exc:
            self.check_label.configure(text="Database check failed: %s" % exc,
                                       style="Error.TLabel")
            return
        self.check_label.configure(
            text="Database check: found %d %s in MySQL." % (row["n"], noun()),
            style="Ok.TLabel")


class ErrorTab(ttk.Frame):


    def __init__(self, parent, label, error_text):
        super().__init__(parent, padding=24)
        ttk.Label(self, text=label, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="This tab could not be loaded.", style="Error.TLabel").pack(
            anchor="w", pady=(4, 12))
        ttk.Label(self, text=error_text, wraplength=680, justify="left").pack(anchor="w")
        ttk.Label(self, text="The details are also printed in the terminal window.",
                  style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
