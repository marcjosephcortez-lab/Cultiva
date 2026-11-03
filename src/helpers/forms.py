

import tkinter as tk
from tkinter import ttk

import db
import theme
from helpers import validation as v
from helpers.widgets import ColorField, DateField, InlineMessage, TimeField, center_on_parent

NONE_LABEL = "(none)"


class Field:


    KINDS = ("text", "multiline", "int", "decimal", "date", "time",
             "combo", "check", "color")

    def __init__(self, name, label, kind="text", required=False, options=None,
                 default=None, minimum=None, maximum=None, max_length=None,
                 width=32, height=5, hint=""):
        if kind not in self.KINDS:
            raise ValueError("Unknown field kind: %r" % (kind,))
        self.name = name              
        self.label = label            
        self.kind = kind
        self.required = required
        self.options = options or []  
        self.default = default
        self.minimum = minimum
        self.maximum = maximum
        self.max_length = max_length
        self.width = width
        self.height = height          
        self.hint = hint              


def convert_value(field, raw):

    kind, label = field.kind, field.label
    if kind in ("text", "multiline"):
        return v.clean_text(raw, label, field.required, field.max_length)
    if kind == "int":
        return v.parse_int(raw, label, field.required, field.minimum, field.maximum)
    if kind == "decimal":
        return v.parse_decimal(raw, label, field.required, field.minimum, field.maximum)
    if kind == "date":
        return v.parse_date(raw, label, field.required)
    if kind == "time":
        return v.parse_time(raw, label, field.required)
    if kind == "color":
        return v.parse_color(raw, label, field.required)
    if kind == "check":
        return bool(raw)
    if kind == "combo":
        if raw in (None, "") and field.required:
            raise v.ValidationError("Please choose a value for %s." % label)
        return None if raw in (None, "") else raw
    raise ValueError("Unknown field kind: %r" % (kind,))


class FormDialog(tk.Toplevel):


    def __init__(self, parent, title, fields, values=None, save=None,
                 validate=None, save_text="Save"):
        super().__init__(parent)
        self.withdraw()  
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.configure(background=theme.colors()["bg"])

        self.parent = parent
        self.fields = fields
        self.save_callback = save          
        self.validate_callback = validate  
        self.result = None                 
        self._getters = {}
        self._setters = {}
        self._widgets = {}
        values = values or {}

        body = ttk.Frame(self, padding=14)
        body.grid(row=0, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1)

        grid_row = 0
        for field in fields:
            label_text = field.label + (" *" if field.required else "")
            ttk.Label(body, text=label_text).grid(row=grid_row, column=0, sticky="nw",
                                                  padx=(0, 12), pady=(6, 0))
            widget = self._build_widget(body, field)
            widget.grid(row=grid_row, column=1, sticky="ew", pady=(6, 0))
            self._widgets[field.name] = widget
            initial = values.get(field.name, field.default)
            self._setters[field.name](initial)
            grid_row += 1
            if field.hint:
                ttk.Label(body, text=field.hint, style="Muted.TLabel").grid(
                    row=grid_row, column=1, sticky="w")
                grid_row += 1

        if any(f.required for f in fields):
            ttk.Label(body, text="* required", style="Muted.TLabel").grid(
                row=grid_row, column=0, columnspan=2, sticky="w", pady=(10, 0))
            grid_row += 1

        self.message = InlineMessage(body, wraplength=380)
        self.message.grid(row=grid_row, column=0, columnspan=2, sticky="w", pady=(8, 0))
        grid_row += 1

        buttons = ttk.Frame(body)
        buttons.grid(row=grid_row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        self.save_button = ttk.Button(buttons, text=save_text, command=self._on_save)
        self.save_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Cancel", style="Soft.TButton",
                   command=self.cancel).pack(side="left")

        self.bind("<Return>", self._on_return)
        self.bind("<KP_Enter>", self._on_return)
        self.bind("<Control-Return>", self._on_save)
        self.bind("<Escape>", lambda event: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        center_on_parent(self, parent)
        self.deiconify()
        try:
            self.wait_visibility()
            self.grab_set()  
        except tk.TclError:
            pass
        if fields:
            self.after(50, self._focus_first)

    def _build_widget(self, parent, field):

        name, kind = field.name, field.kind

        if kind == "multiline":
            frame = ttk.Frame(parent)
            text = tk.Text(frame, width=field.width, height=field.height,
                           wrap="word", undo=True)
            theme.style_text(text)
            scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            text.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            text.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[1])
            text.bind("<Shift-Tab>", lambda e: (e.widget.tk_focusPrev().focus_set(), "break")[1])

            def set_text(value, box=text):
                box.delete("1.0", "end")
                box.insert("1.0", "" if value is None else str(value))

            self._getters[name] = lambda box=text: box.get("1.0", "end-1c")
            self._setters[name] = set_text
            return frame

        if kind == "date":
            widget = DateField(parent, allow_blank=not field.required)
            self._getters[name] = widget.get
            self._setters[name] = widget.set
            return widget

        if kind == "time":
            widget = TimeField(parent, allow_blank=not field.required)
            self._getters[name] = widget.get
            self._setters[name] = widget.set
            return widget

        if kind == "color":
            widget = ColorField(parent, width=field.width // 3)
            self._getters[name] = widget.get
            self._setters[name] = widget.set
            return widget

        if kind == "check":
            var = tk.BooleanVar()
            widget = ttk.Checkbutton(parent, text=field.hint or "", variable=var)
            self._getters[name] = var.get
            self._setters[name] = lambda value, var=var: var.set(bool(value))
            return widget

        if kind == "combo":
            options = list(field.options)
            if not field.required:
                options = [("", NONE_LABEL)] + options
            label_to_value = {label: value for value, label in options}
            combo = ttk.Combobox(parent, values=[label for _, label in options],
                                 state="readonly", width=max(field.width - 2, 10))

            def set_combo(value, box=combo, opts=options):
                box.set("")
                for option_value, option_label in opts:
                    if value is not None and str(option_value) == str(value):
                        box.set(option_label)
                        return
                if not field.required:
                    box.set(NONE_LABEL)  

            self._getters[name] = lambda box=combo, m=label_to_value: m.get(box.get(), "")
            self._setters[name] = set_combo
            return combo

        var = tk.StringVar()
        entry = ttk.Entry(parent, textvariable=var, width=field.width)
        self._getters[name] = var.get
        self._setters[name] = lambda value, var=var: var.set("" if value is None else str(value))
        return entry

    def collect(self):

        values = {}
        for field in self.fields:
            raw = self._getters[field.name]()
            try:
                values[field.name] = convert_value(field, raw)
            except v.ValidationError as exc:
                exc.field = field.name
                raise
        if self.validate_callback:
            self.validate_callback(values)  
        return values

    def _on_return(self, event):

        widget = event.widget
        if isinstance(widget, tk.Text):
            return None  
        if isinstance(widget, ttk.Button):
            widget.invoke()  
            return "break"
        return self._on_save()

    def _on_save(self, event=None):

        self.message.clear()
        try:
            values = self.collect()
        except v.ValidationError as exc:
            self._show_problem(exc)
            return "break"

        if self.save_callback is not None:
            self.save_button.state(["disabled"])  
            try:
                self.save_callback(values)
            except v.ValidationError as exc:
                self._show_problem(exc)
                return "break"
            except db.DBError as exc:
                self.message.error(str(exc))
                return "break"
            finally:
                if self.winfo_exists():
                    self.save_button.state(["!disabled"])

        self.result = values
        self.destroy()
        return "break"

    def _show_problem(self, exc):

        self.message.error(exc.message)
        widget = self._widgets.get(exc.field) if exc.field else None
        if widget is not None:
            widget.focus_set()

    def _focus_first(self):
        if self.winfo_exists():
            first = self._widgets.get(self.fields[0].name)
            if first is not None:
                first.focus_set()

    def cancel(self):

        self.result = None
        self.destroy()

    def show(self):

        self.wait_window(self)
        return self.result


def ask_form(parent, title, fields, values=None, save=None, validate=None,
             save_text="Save"):

    dialog = FormDialog(parent, title, fields, values=values, save=save,
                        validate=validate, save_text=save_text)
    return dialog.show()
