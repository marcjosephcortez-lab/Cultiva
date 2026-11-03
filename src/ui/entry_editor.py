

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

import db
import theme
import translations
from helpers.attachment_list import AttachmentList

tr = translations.tr

NONE_TEXT = "(none)"
WEATHER_CHOICES = ("Sunny", "Cloudy", "Rainy", "Windy", "Hot", "Cool")
MAX_TITLE = 200
MAX_MOOD = 50
MAX_BODY_BYTES = 60000  


def open_editor(parent, kind, record=None, on_saved=None):

    try:
        plots = db.query("SELECT id, name FROM plots ORDER BY name")
        crops = db.query("SELECT id, name FROM crops ORDER BY name")
    except db.DBError as exc:
        messagebox.showerror("Cannot open the form", str(exc), parent=parent.winfo_toplevel())
        return None
    return EntryEditor(parent, kind, record, plots, crops, on_saved)


class EntryEditor(tk.Toplevel):


    def __init__(self, parent, kind, record, plots, crops, on_saved):
        self._owner_window = parent.winfo_toplevel()
        super().__init__(self._owner_window)
        self.kind = kind                    
        self.record = record
        self.on_saved = on_saved
        self.plot_ids = {p["name"]: p["id"] for p in plots}
        self.crop_ids = {c["name"]: c["id"] for c in crops}
        self.plot_names = {p["id"]: p["name"] for p in plots}
        self.crop_names = {c["id"]: c["name"] for c in crops}

        noun = "entry" if kind == "journal" else "note"
        self.title(("Edit " if record else "New ") + noun)
        self.configure(background=theme.colors()["bg"])
        self.transient(self._owner_window)

        self._build(plots, crops)

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda event: self.cancel())
        self.bind("<Control-s>", lambda event: self.save())
        self._place()
        self.wait_visibility()   
        self.grab_set()          
        self.title_entry.focus_set()

    def _build(self, plots, crops):
        record = self.record or {}
        journal = self.kind == "journal"

        body = ttk.Frame(self, padding=14)
        body.pack(fill="both", expand=True)
        body.columnconfigure(1, weight=1)
        row = 0

        def label(text, sticky="w"):
            ttk.Label(body, text=text).grid(row=row, column=0, sticky=sticky, pady=4, padx=(0, 10))

        if journal:
            label("Date")
            date_box = ttk.Frame(body)
            date_box.grid(row=row, column=1, sticky="w")
            self.date_var = tk.StringVar(value=str(record.get("entry_date") or date.today()))
            ttk.Entry(date_box, textvariable=self.date_var, width=14).pack(side="left")
            ttk.Label(date_box, text="  year-month-day, e.g. 2026-10-17",
                      style="Muted.TLabel").pack(side="left")
            row += 1

        label("Title *")
        self.title_var = tk.StringVar(value=record.get("title") or "")
        self.title_entry = ttk.Entry(body, textvariable=self.title_var)
        self.title_entry.grid(row=row, column=1, sticky="ew")
        row += 1

        if journal:
            label("Weather / mood")
            self.mood_var = tk.StringVar(value=record.get("mood_weather") or "")
            ttk.Combobox(body, textvariable=self.mood_var, values=WEATHER_CHOICES,
                         width=22).grid(row=row, column=1, sticky="w")  
            row += 1

        label(tr("plot"))
        self.plot_var = tk.StringVar(value=self.plot_names.get(record.get("plot_id"), NONE_TEXT))
        ttk.Combobox(body, textvariable=self.plot_var, state="readonly", width=30,
                     values=[NONE_TEXT] + [p["name"] for p in plots]).grid(row=row, column=1, sticky="w")
        row += 1

        label(tr("crop"))
        self.crop_var = tk.StringVar(value=self.crop_names.get(record.get("crop_id"), NONE_TEXT))
        ttk.Combobox(body, textvariable=self.crop_var, state="readonly", width=30,
                     values=[NONE_TEXT] + [c["name"] for c in crops]).grid(row=row, column=1, sticky="w")
        row += 1

        label("Entry" if journal else "Note", sticky="nw")
        text_box = ttk.Frame(body)
        text_box.grid(row=row, column=1, sticky="nsew")
        self.body_text = tk.Text(text_box, height=8, wrap="word", undo=True)
        theme.style_text(self.body_text)
        scrollbar = ttk.Scrollbar(text_box, orient="vertical", command=self.body_text.yview)
        self.body_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.body_text.pack(side="left", fill="both", expand=True)
        self.body_text.insert("1.0", record.get("body") or "")
        body.rowconfigure(row, weight=1)
        row += 1

        self.files = AttachmentList(body, self.kind, editable=True, height=110)
        self.files.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.files.load(record.get("id"))
        row += 1

        self.error_var = tk.StringVar()
        ttk.Label(body, textvariable=self.error_var, style="Error.TLabel", wraplength=560,
                  justify="left").grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        row += 1

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", style="Soft.TButton",
                   command=self.cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton",
                   command=self.save).pack(side="right")

    def _place(self):

        self.update_idletasks()
        width = min(660, self.winfo_screenwidth() - 80)
        height = min(700, self.winfo_screenheight() - 120)
        owner = self._owner_window
        x = max(owner.winfo_rootx() + (owner.winfo_width() - width) // 2, 0)
        y = max(owner.winfo_rooty() + 20, 0)
        self.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.minsize(520, 480)

    def _read(self):

        title = self.title_var.get().strip()
        if not title:
            raise ValueError("Please type a title.")
        if len(title) > MAX_TITLE:
            raise ValueError("The title is too long (maximum %d characters)." % MAX_TITLE)
        values = {"title": title}

        if self.kind == "journal":
            text = self.date_var.get().strip()
            try:
                day = datetime.strptime(text, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("The date must be a real day written like 2026-10-17 "
                                 "(year-month-day).") from None
            if day.year < 1900:
                raise ValueError("Please choose a date after the year 1900.")
            values["entry_date"] = day
            mood = self.mood_var.get().strip()
            if len(mood) > MAX_MOOD:
                raise ValueError("Weather / mood is too long (maximum %d characters)." % MAX_MOOD)
            values["mood_weather"] = mood or None

        text = self.body_text.get("1.0", "end-1c").strip()
        if len(text.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError("The text is too long. Please shorten it or split it into two.")
        values["body"] = text or None
        values["plot_id"] = self.plot_ids.get(self.plot_var.get())   
        values["crop_id"] = self.crop_ids.get(self.crop_var.get())
        return values

    def _write(self, v):

        if self.kind == "journal":
            data = (v["entry_date"], v["title"], v["body"], v["mood_weather"],
                    v["plot_id"], v["crop_id"])
            if self.record:
                db.execute("UPDATE journal_entries SET entry_date=%s, title=%s, body=%s, "
                           "mood_weather=%s, plot_id=%s, crop_id=%s WHERE id=%s",
                           data + (self.record["id"],))
                return self.record["id"]
            return db.execute("INSERT INTO journal_entries (entry_date, title, body, "
                              "mood_weather, plot_id, crop_id) VALUES (%s,%s,%s,%s,%s,%s)", data)
        data = (v["title"], v["body"], v["plot_id"], v["crop_id"])
        if self.record:
            db.execute("UPDATE notes SET title=%s, body=%s, plot_id=%s, crop_id=%s WHERE id=%s",
                       data + (self.record["id"],))
            return self.record["id"]
        return db.execute("INSERT INTO notes (title, body, plot_id, crop_id) "
                          "VALUES (%s,%s,%s,%s)", data)

    def save(self):
        self.error_var.set("")
        try:
            values = self._read()
        except ValueError as exc:
            self.error_var.set(str(exc))
            return
        try:
            record_id = self._write(values)
        except db.DBError as exc:
            self.error_var.set(str(exc))
            return

        problems = self.files.apply(record_id)   
        callback, owner = self.on_saved, self._owner_window
        self.destroy()
        if problems:
            messagebox.showwarning(
                "Saved, but some files had a problem",
                "The text was saved, but:\n\n" + "\n\n".join(problems), parent=owner)
        if callback:
            callback(record_id)

    def cancel(self):
        self.destroy()
