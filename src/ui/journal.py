

import tkinter as tk
from datetime import date
from tkinter import ttk

import db
import translations
from helpers.streak import describe_streak
from ui.record_tab import RecordTab

tr = translations.tr


class JournalTab(RecordTab):
    KIND = "journal"
    NOUN = "entry"
    NOUN_PLURAL = "entries"

    def heading_text(self):
        return tr("tab_journal")

    def build_header_extra(self, header):
        self.streak_var = tk.StringVar()
        self.streak_label = ttk.Label(header, textvariable=self.streak_var, style="Muted.TLabel")
        self.streak_label.pack(side="right")

    def columns(self):
        return [("date", "Date", 125, "w"), ("title", "Title", 250, "w"),
                ("where", tr("plot"), 110, "w"), ("files", "Files", 50, "center")]

    def row_values(self, row):
        return (row["entry_date"].strftime("%a %d %b %Y"), row["title"],
                row["plot_name"] or "", row["files"] or "")

    def meta_text(self, row):
        parts = [row["entry_date"].strftime("%A %d %B %Y")]
        if row["mood_weather"]:
            parts.append(row["mood_weather"])
        links = self.links_text(row)
        if links:
            parts.append(links)
        return " | ".join(parts)

    def load_rows(self, search):
        sql = ("SELECT j.id, j.entry_date, j.title, j.body, j.mood_weather, j.plot_id, j.crop_id, "
               "p.name AS plot_name, c.name AS crop_name, "
               "(SELECT COUNT(*) FROM attachments a WHERE a.journal_id = j.id) AS files "
               "FROM journal_entries j "
               "LEFT JOIN plots p ON p.id = j.plot_id "
               "LEFT JOIN crops c ON c.id = j.crop_id")
        params = None
        if search:
            like = db.like_pattern(search)
            sql += (" WHERE (j.title LIKE %s OR j.body LIKE %s OR j.mood_weather LIKE %s "
                    "OR p.name LIKE %s OR c.name LIKE %s)")
            params = (like,) * 5
        sql += " ORDER BY j.entry_date DESC, j.id DESC"
        return db.query(sql, params)

    def after_refresh(self):

        today = date.today()
        try:
            rows = db.query("SELECT DISTINCT entry_date FROM journal_entries "
                            "WHERE entry_date <= %s", (today,))
        except db.DBError:
            self.streak_var.set("")
            return
        text, active = describe_streak([r["entry_date"] for r in rows], today)
        self.streak_var.set(text)
        self.streak_label.configure(style="Ok.TLabel" if active else "Muted.TLabel")
