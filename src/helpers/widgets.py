

import tkinter as tk
from datetime import date
from tkinter import colorchooser, ttk

import theme
from helpers import validation as v

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def center_on_parent(window, parent):

    window.update_idletasks()
    top = parent.winfo_toplevel()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    x = top.winfo_rootx() + (top.winfo_width() - width) // 2
    y = top.winfo_rooty() + (top.winfo_height() - height) // 3
    window.geometry("+%d+%d" % (max(x, 0), max(y, 0)))


class ScrollableTree(ttk.Frame):


    def __init__(self, parent, columns, headings=None, widths=None, anchors=None,
                 height=10, selectmode="browse", show="headings", sortable=True):
        super().__init__(parent)
        self.columns = tuple(columns)
        self._sortable = sortable
        self._sort_reverse = {}
        self._row_count = 0
        headings = headings or {}
        widths = widths or {}
        anchors = anchors or {}

        self.tree = ttk.Treeview(self, columns=self.columns, show=show,
                                 height=height, selectmode=selectmode)
        y_scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        for index, column in enumerate(self.columns):
            text = headings.get(column, column.replace("_", " ").title())
            anchor = anchors.get(column, "w")  
            if sortable:
                self.tree.heading(column, text=text, anchor=anchor,
                                  command=lambda col=column: self.sort_by(col))
            else:
                self.tree.heading(column, text=text, anchor=anchor)
            self.tree.column(column, width=widths.get(column, 100),
                             anchor=anchor, stretch=(index == 0))

        self.tree.tag_configure("odd", background=theme.colors()["row_alt"])

    def clear(self):

        self.tree.delete(*self.tree.get_children())
        self._row_count = 0

    def add(self, values, iid=None, tags=(), parent="", text=""):

        tags = tuple(t for t in tags if t)  
        if parent == "":
            if self._row_count % 2 == 1:
                tags += ("odd",)
            self._row_count += 1
        options = {"values": values, "tags": tags, "text": text}
        if iid is not None:
            options["iid"] = str(iid)
        return self.tree.insert(parent, "end", **options)

    def selected_iid(self):

        selection = self.tree.selection()
        return selection[0] if selection else None

    def selected_iids(self):
        return list(self.tree.selection())

    def selected_values(self):
        iid = self.selected_iid()
        return self.tree.item(iid, "values") if iid else None

    def select(self, iid):

        iid = str(iid)
        if self.tree.exists(iid):
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.tree.see(iid)

    def bind_select(self, callback):

        self.tree.bind("<<TreeviewSelect>>", lambda event: callback())

    def bind_activate(self, callback):

        self.tree.bind("<Double-1>", lambda event: callback())
        self.tree.bind("<Return>", lambda event: callback())

    def sort_by(self, column, reverse=None):

        if not self._sortable:
            return
        if reverse is None:
            reverse = not self._sort_reverse.get(column, True)
        self._sort_reverse[column] = reverse

        def key(item):
            text = str(item[0])
            try:
                return (0, float(text.replace(",", "").replace("\u20b1", "")), "")
            except ValueError:
                return (1, 0.0, text.lower())

        items = [(self.tree.set(iid, column), iid) for iid in self.tree.get_children("")]
        items.sort(key=key, reverse=reverse)
        for position, (_, iid) in enumerate(items):
            self.tree.move(iid, "", position)
        for position, (_, iid) in enumerate(items):
            tags = [t for t in self.tree.item(iid, "tags") if t != "odd"]
            if position % 2 == 1:
                tags.append("odd")
            self.tree.item(iid, tags=tags)


class ScrollableFrame(ttk.Frame):


    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0,
                                background=theme.colors()["bg"])
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.body.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._window, width=e.width))

        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)
        self.body.bind("<Enter>", self._bind_wheel)

    def _bind_wheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)   
        self.canvas.bind_all("<Button-4>", self._on_wheel)     
        self.canvas.bind_all("<Button-5>", self._on_wheel)     

    def _unbind_wheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if self.canvas.yview() == (0.0, 1.0):
            return  
        if getattr(event, "num", 0) == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")
        else:
            self.canvas.yview_scroll(1, "units")


class DateField(ttk.Frame):


    def __init__(self, parent, value=None, allow_blank=False, min_year=1990, max_year=2100):
        super().__init__(parent)
        self.allow_blank = allow_blank
        self.day_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.year_var = tk.StringVar()

        self.day_box = ttk.Spinbox(self, from_=1, to=31, width=3, wrap=True,
                                   format="%02.0f", textvariable=self.day_var)
        self.month_box = ttk.Combobox(self, values=MONTH_NAMES, width=5, state="readonly",
                                      textvariable=self.month_var)
        year_options = {"from_": min_year, "to": max_year, "width": 6,
                        "textvariable": self.year_var}
        self.year_box = ttk.Spinbox(self, **year_options)

        self.day_box.grid(row=0, column=0, padx=(0, 4))
        self.month_box.grid(row=0, column=1, padx=(0, 4))
        self.year_box.grid(row=0, column=2, padx=(0, 6))
        ttk.Button(self, text="Today", width=6, style="Soft.TButton",
                   command=self.set_today, takefocus=False).grid(row=0, column=3)
        if allow_blank:
            ttk.Button(self, text="Clear", width=6, style="Soft.TButton",
                       command=self.clear, takefocus=False).grid(row=0, column=4, padx=(4, 0))

        if value in (None, "") and not allow_blank:
            self.set_today()
        else:
            self.set(value)

    def set(self, value):

        text = v.date_to_text(value)
        match = text.split("-") if text else []
        if len(match) == 3 and all(part.isdigit() for part in match):
            year, month, day = int(match[0]), int(match[1]), int(match[2])
            self.year_var.set(str(year))
            self.month_var.set(MONTH_NAMES[month - 1] if 1 <= month <= 12 else "")
            self.day_var.set("%02d" % day)
        else:
            self.clear()

    def set_today(self):
        self.set(date.today())

    def clear(self):
        self.day_var.set("")
        self.month_var.set("")
        self.year_var.set("")

    def get(self):

        day = self.day_var.get().strip()
        month_name = self.month_var.get().strip()
        year = self.year_var.get().strip()
        if not (day or month_name or year):
            return ""
        month = str(MONTH_NAMES.index(month_name) + 1) if month_name in MONTH_NAMES else ""
        return "%s-%s-%s" % (year, month.zfill(2) if month else "", day.zfill(2) if day else "")

    def focus_set(self):
        self.day_box.focus_set()


class TimeField(ttk.Frame):


    def __init__(self, parent, value=None, allow_blank=False):
        super().__init__(parent)
        self.allow_blank = allow_blank
        self.hour_var = tk.StringVar()
        self.minute_var = tk.StringVar()

        hours = ["%02d" % h for h in range(24)]
        if allow_blank:
            hours = ["--"] + hours
        minutes = ["%02d" % m for m in range(60)]
        self.hour_box = ttk.Spinbox(self, values=hours, width=3, wrap=True,
                                    textvariable=self.hour_var)
        self.minute_box = ttk.Spinbox(self, values=minutes, width=3, wrap=True,
                                      textvariable=self.minute_var)
        self.hour_box.grid(row=0, column=0)
        ttk.Label(self, text=":").grid(row=0, column=1, padx=2)
        self.minute_box.grid(row=0, column=2)
        self.set(value)

    def set(self, value):

        text = v.time_to_text(value)
        if text and ":" in text:
            hour, minute = text.split(":")[:2]
            self.hour_var.set(hour.zfill(2))
            self.minute_var.set(minute.zfill(2))
        else:
            self.hour_var.set("--" if self.allow_blank else "08")
            self.minute_var.set("00")

    def get(self):
        hour = self.hour_var.get().strip()
        minute = self.minute_var.get().strip()
        if hour in ("", "--"):
            return ""
        return "%s:%s" % (hour.zfill(2), (minute or "00").zfill(2))

    def focus_set(self):
        self.hour_box.focus_set()


class ColorField(ttk.Frame):


    def __init__(self, parent, value="#4C9F50", width=10):
        super().__init__(parent)
        self.var = tk.StringVar(value=value)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.swatch = tk.Label(self, width=3, relief="solid", borderwidth=1)
        self.entry.grid(row=0, column=0, padx=(0, 6))
        self.swatch.grid(row=0, column=1, padx=(0, 6), ipady=2)
        ttk.Button(self, text="Choose...", style="Soft.TButton",
                   command=self.choose).grid(row=0, column=2)
        self.var.trace_add("write", lambda *args: self._update_swatch())
        self._update_swatch()

    def _update_swatch(self):
        try:
            self.swatch.configure(background=v.parse_color(self.var.get(), "Color"))
        except v.ValidationError:
            self.swatch.configure(background=theme.colors()["bg"])

    def choose(self):

        try:
            current = v.parse_color(self.var.get(), "Color")
        except v.ValidationError:
            current = None
        _, hex_color = colorchooser.askcolor(color=current, parent=self, title="Choose a color")
        if hex_color:
            self.var.set(hex_color.upper())

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value or "")

    def focus_set(self):
        self.entry.focus_set()


class SearchBox(ttk.Frame):


    def __init__(self, parent, on_change, delay_ms=300, label="Search:", width=24):
        super().__init__(parent)
        self._on_change = on_change
        self._delay = delay_ms
        self._after_id = None
        self.var = tk.StringVar()
        if label:
            ttk.Label(self, text=label).pack(side="left", padx=(0, 6))
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left")
        ttk.Button(self, text="Clear", style="Soft.TButton", width=6,
                   command=self.clear, takefocus=False).pack(side="left", padx=(6, 0))
        self.var.trace_add("write", lambda *args: self._schedule())

    def _schedule(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
        self._after_id = self.after(self._delay, self._fire)

    def _fire(self):
        self._after_id = None
        self._on_change()

    def get(self):
        return self.var.get().strip()

    def clear(self):
        self.var.set("")

    def focus_set(self):
        self.entry.focus_set()


class InlineMessage(ttk.Label):


    def __init__(self, parent, wraplength=420, **kwargs):
        super().__init__(parent, text="", wraplength=wraplength, **kwargs)
        self._after_id = None

    def _show(self, text, style, seconds):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.configure(text=text, style=style)
        if seconds:
            self._after_id = self.after(seconds * 1000, self.clear)

    def error(self, text):

        self._show(text, "Error.TLabel", 0)

    def ok(self, text, seconds=4):

        self._show(text, "Ok.TLabel", seconds)

    def clear(self):
        if self._after_id is not None:
            self.after_cancel(self._after_id)
            self._after_id = None
        self.configure(text="")
