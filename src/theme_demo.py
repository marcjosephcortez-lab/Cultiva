

import tkinter as tk
from tkinter import ttk

import db
import theme
import translations
from helpers import dialogs
from helpers import validation as v
from helpers.forms import Field, ask_form
from helpers.widgets import (DateField, InlineMessage, ScrollableFrame,
                             ScrollableTree, SearchBox, TimeField)

tr = translations.tr


class DemoApp:


    def __init__(self, root):
        self.root = root
        root.title("Step 2 - theme and helpers demo")
        root.geometry("1000x740")
        root.minsize(820, 560)

        self.mode_var = tk.StringVar(value="farm")
        top = ttk.Frame(root, padding=(12, 10))
        top.pack(fill="x")
        ttk.Label(top, text="Mode:", style="Header.TLabel").pack(side="left", padx=(0, 8))
        for mode in translations.MODES:
            ttk.Radiobutton(top, text=mode.title(), value=mode, variable=self.mode_var,
                            command=self.switch_mode).pack(side="left", padx=4)
        self.title_label = ttk.Label(top, text="", style="Title.TLabel")
        self.title_label.pack(side="right")

        self.content = ttk.Frame(root, padding=(12, 0, 12, 12))
        self.content.pack(fill="both", expand=True)
        self.switch_mode()

    def switch_mode(self):

        mode = self.mode_var.get()
        theme.apply_theme(self.root, mode)
        translations.set_current_mode(mode)
        self.title_label.configure(text=tr("app_title"))
        for child in self.content.winfo_children():
            child.destroy()

        notebook = ttk.Notebook(self.content)
        notebook.pack(fill="both", expand=True)
        for index, (key, label) in enumerate(translations.tabs()):
            frame = ttk.Frame(notebook, padding=10)
            notebook.add(frame, text=label)
            if index == 0:
                self.build_widget_gallery(frame)
            else:
                ttk.Label(frame, text="The '%s' tab will be built in a later step." % label,
                          style="Muted.TLabel").pack(anchor="w")

    def build_widget_gallery(self, parent):
        scroller = ScrollableFrame(parent)
        scroller.pack(fill="both", expand=True)
        body = scroller.body
        body.columnconfigure(0, weight=1)

        words = ttk.LabelFrame(body, text="Wording in this mode", padding=10)
        words.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        line = "   |   ".join("%s: %s" % (k.title(), tr(k)) for k in
                              ("plots", "workers", "crops", "plantings", "harvest", "timetable"))
        ttk.Label(words, text=line).pack(anchor="w")
        features = "Attendance tab: %s   |   Worker pay shown: %s" % (
            "yes" if translations.feature("attendance") else "no",
            "yes" if translations.feature("pay") else "no")
        ttk.Label(words, text=features, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

        buttons = ttk.LabelFrame(body, text="Buttons", padding=10)
        buttons.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(buttons, text="Main").pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Accent", style="Accent.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Delete", style="Danger.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Soft", style="Soft.TButton").pack(side="left", padx=(0, 8))
        disabled = ttk.Button(buttons, text="Disabled")
        disabled.state(["disabled"])
        disabled.pack(side="left", padx=(0, 16))
        for text, style in (("Mon", "Day.TButton"), ("Tue", "DayToday.TButton"),
                            ("Wed", "DaySelected.TButton"), ("Thu", "DayMuted.TButton")):
            ttk.Button(buttons, text=text, style=style, width=6).pack(side="left", padx=2)

        inputs = ttk.LabelFrame(body, text="Inputs", padding=10)
        inputs.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(inputs, text="Entry").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Entry(inputs, width=24).grid(row=0, column=1, sticky="w", padx=8)
        ttk.Label(inputs, text="Combobox").grid(row=0, column=2, sticky="w", padx=(20, 0))
        ttk.Combobox(inputs, values=[tr("crop") + " 1", tr("crop") + " 2"],
                     state="readonly", width=16).grid(row=0, column=3, padx=8)
        ttk.Label(inputs, text="Spinbox").grid(row=1, column=0, sticky="w", pady=3)
        spin = ttk.Spinbox(inputs, from_=0, to=99, width=8)
        spin.grid(row=1, column=1, sticky="w", padx=8)
        spin.set(5)
        self.demo_check = tk.BooleanVar(value=True)
        ttk.Checkbutton(inputs, text="Checkbutton", variable=self.demo_check).grid(
            row=1, column=2, sticky="w", padx=(20, 0))
        radios = ttk.Frame(inputs)
        radios.grid(row=1, column=3, sticky="w", padx=8)
        self.demo_choice = tk.StringVar(value="present")
        ttk.Radiobutton(radios, text="Present", value="present", variable=self.demo_choice).pack(side="left")
        ttk.Radiobutton(radios, text="Absent", value="absent", variable=self.demo_choice).pack(side="left", padx=6)
        ttk.Label(inputs, text="DateField").grid(row=2, column=0, sticky="w", pady=3)
        self.demo_date = DateField(inputs)
        self.demo_date.grid(row=2, column=1, columnspan=2, sticky="w", padx=8)
        ttk.Label(inputs, text="TimeField").grid(row=3, column=0, sticky="w", pady=3)
        TimeField(inputs, value="06:30").grid(row=3, column=1, sticky="w", padx=8)
        self.search_result = ttk.Label(inputs, text="(type in the search box)", style="Muted.TLabel")
        SearchBox(inputs, on_change=self.on_search).grid(row=3, column=2, columnspan=2, sticky="w", padx=(20, 0))
        self.search_result.grid(row=4, column=1, columnspan=3, sticky="w", padx=8)
        self.search_box_hint = None

        bars = ttk.LabelFrame(body, text="Progress bars", padding=10)
        bars.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        bars.columnconfigure(1, weight=1)
        for row, (text, value, style) in enumerate((
                ("Growing", 45, "Horizontal.TProgressbar"),
                ("Ready to harvest", 100, "Ready.Horizontal.TProgressbar"),
                ("Overdue", 100, "Late.Horizontal.TProgressbar"))):
            ttk.Label(bars, text=text, width=16).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Progressbar(bars, value=value, maximum=100, style=style).grid(
                row=row, column=1, sticky="ew", padx=8)

        table_box = ttk.LabelFrame(body, text="Table (click a heading to sort, double-click a row)", padding=10)
        table_box.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        table_box.columnconfigure(0, weight=1)
        self.table = ScrollableTree(
            table_box, columns=("name", "area", "crop"), height=5,
            headings={"name": tr("plot") + " name", "area": "Area (sq m)", "crop": tr("crop")},
            widths={"name": 220, "area": 100, "crop": 160}, anchors={"area": "e"})
        self.table.grid(row=0, column=0, sticky="ew")
        crops = ["Palay", "Kamatis", "Talong", "Sitaw"] if self.mode_var.get() == "farm" \
            else ["Basil", "Mint", "Lettuce", "Marigold"]
        for number in range(1, 13):
            self.table.add(("%s %d" % (tr("plot"), number), number * 12, crops[number % 4]), iid=number)
        self.table.bind_activate(lambda: dialogs.show_info(
            self.root, "You opened row id %s." % self.table.selected_iid()))

        dialog_box = ttk.LabelFrame(body, text="Forms and pop-ups", padding=10)
        dialog_box.grid(row=5, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(dialog_box, text="Open sample form", command=self.open_form).pack(side="left", padx=(0, 8))
        ttk.Button(dialog_box, text="Delete (works)", style="Danger.TButton",
                   command=self.try_delete_ok).pack(side="left", padx=(0, 8))
        ttk.Button(dialog_box, text="Delete (blocked: in use)", style="Danger.TButton",
                   command=self.try_delete_blocked).pack(side="left", padx=(0, 8))
        ttk.Button(dialog_box, text="Bad date message", style="Soft.TButton",
                   command=self.show_bad_date).pack(side="left")
        self.message = InlineMessage(dialog_box, wraplength=700)
        self.message.pack(side="bottom", anchor="w", pady=(8, 0))

    def on_search(self):
        self.search_result.configure(text="Search ran (after you stopped typing).")

    def open_form(self):

        fields = [
            Field("name", tr("plot") + " name", required=True, max_length=100),
            Field("crop_id", tr("crop"), kind="combo", required=True,
                  options=[(1, "Option one"), (2, "Option two"), (3, "Option three")]),
            Field("plant_date", "Planting date", kind="date", required=True),
            Field("harvest_date", "Expected harvest", kind="date", required=True),
            Field("start", "Start time", kind="time", required=True),
            Field("finish", "Finish time", kind="time", required=True, default="09:00"),
            Field("notes", "Notes", kind="multiline", hint="Optional"),
            Field("active", "Active", kind="check", hint="Tick if still in use", default=True),
        ]
        if translations.feature("pay"):  
            fields.insert(2, Field("rate", tr("daily_rate"), kind="decimal", minimum=0,
                                   hint="Pesos per day, for example 550.00"))

        def check_rules(values):
            v.check_harvest_after_planting(values["plant_date"], values["harvest_date"])
            v.check_time_order(values["start"], values["finish"])

        def save(values):
            pass  

        result = ask_form(self.root, "Sample form", fields, values={"start": "08:00"},
                          save=save, validate=check_rules)
        if result:
            self.message.ok("Form accepted: " + ", ".join("%s=%s" % item for item in result.items()))
        else:
            self.message.ok("Form cancelled.")

    def try_delete_ok(self):
        deleted = dialogs.delete_record(self.root, tr("plot").lower(), "Sample item",
                                        delete_func=lambda: None)
        self.message.ok("Deleted." if deleted else "Not deleted.")

    def try_delete_blocked(self):
        def blocked():
            raise db.DBInUseError("foreign key")  
        deleted = dialogs.delete_record(
            self.root, tr("plot").lower(), "Palayan A", delete_func=blocked,
            in_use_hint="Delete or move its %s first." % tr("plantings").lower())
        self.message.ok("Deleted." if deleted else "Not deleted (blocked).")

    def show_bad_date(self):
        try:
            v.parse_date("2026-02-30", "Due date")
        except v.ValidationError as exc:
            dialogs.show_validation_error(self.root, exc)


def main():
    root = tk.Tk()
    theme.apply_theme(root, "farm")
    DemoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
