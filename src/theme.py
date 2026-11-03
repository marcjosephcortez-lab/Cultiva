

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

PALETTES = {
    "farm": {
        "name": "Farm",
        "bg": "#F7F4E6",          
        "surface": "#FFFDF5",     
        "fg": "#1E2B1E",          
        "muted": "#4F5F4C",       
        "primary": "#1B4D2E",     
        "primary_dark": "#12361F",
        "primary_fg": "#FFFFFF",
        "accent": "#E3B23C",      
        "accent_dark": "#C9981F",
        "accent_fg": "#2B2100",
        "select_bg": "#CFE3C8",   
        "select_fg": "#10230F",
        "border": "#B9B08A",
        "tab_bg": "#E4DEC0",      
        "header_bg": "#1B4D2E",   
        "header_fg": "#FFFFFF",
        "ok": "#2E7D32",
        "warn": "#8A5200",
        "danger": "#B3261E",
        "danger_dark": "#8C1D18",
        "danger_fg": "#FFFFFF",
        "today_bg": "#FFF1C2",    
        "row_alt": "#F1EDD7",     
    },
    "garden": {
        "name": "Garden",
        "bg": "#F1F8EE",
        "surface": "#FBFEF9",
        "fg": "#1F2E22",
        "muted": "#4F6354",
        "primary": "#3F7D4A",     
        "primary_dark": "#2F6339",
        "primary_fg": "#FFFFFF",
        "accent": "#F4B6C8",      
        "accent_dark": "#EE9BB4",
        "accent_fg": "#4A1F2C",
        "select_bg": "#D6EBD0",
        "select_fg": "#16301B",
        "border": "#A9C5A3",
        "tab_bg": "#DCEBD6",
        "header_bg": "#3F7D4A",
        "header_fg": "#FFFFFF",
        "ok": "#2E7D32",
        "warn": "#8A5200",
        "danger": "#B3261E",
        "danger_dark": "#8C1D18",
        "danger_fg": "#FFFFFF",
        "today_bg": "#FDE3EB",
        "row_alt": "#EAF3E6",
    },
}

FONT_CHOICES = ("Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans")

_current = {"mode": "farm", "colors": PALETTES["farm"], "font": "Helvetica"}


def hex_to_rgb(color):

    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):

    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(x)))) for x in rgb)


def _luminance(color):

    parts = []
    for value in hex_to_rgb(color):
        v = value / 255.0
        parts.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def contrast_ratio(color_a, color_b):

    la, lb = _luminance(color_a), _luminance(color_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def readable_text_color(background):

    dark, light = "#1B1B1B", "#FFFFFF"
    if contrast_ratio(dark, background) >= contrast_ratio(light, background):
        return dark
    return light


def blend(color_a, color_b, amount):

    a, b = hex_to_rgb(color_a), hex_to_rgb(color_b)
    return rgb_to_hex([x + (y - x) * amount for x, y in zip(a, b)])


def colors():

    return _current["colors"]


def font_family():

    return _current["font"]


def _pick_font(root):

    available = set(tkfont.families(root))
    for name in FONT_CHOICES:
        if name in available:
            return name
    return "Helvetica"


def apply_theme(root, mode):

    if mode not in PALETTES:
        raise ValueError("Unknown theme: %r" % (mode,))
    c = PALETTES[mode]
    family = _pick_font(root)
    _current.update(mode=mode, colors=c, font=family)

    for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont"):
        tkfont.nametofont(name).configure(family=family, size=10)

    style = ttk.Style(root)
    style.theme_use("clam")  
    root.configure(background=c["bg"])

    base = (family, 10)
    bold = (family, 10, "bold")

    style.configure(
        ".", background=c["bg"], foreground=c["fg"], fieldbackground=c["surface"],
        troughcolor=c["tab_bg"], bordercolor=c["border"], darkcolor=c["border"],
        lightcolor=c["surface"], focuscolor=c["accent"], font=base,
    )

    style.configure("TFrame", background=c["bg"])
    style.configure("Card.TFrame", background=c["surface"], relief="solid",
                    borderwidth=1, bordercolor=c["border"])
    style.configure("Banner.TFrame", background=c["header_bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("Card.TLabel", background=c["surface"], foreground=c["fg"])
    style.configure("Header.TLabel", font=(family, 13, "bold"), foreground=c["primary"])
    style.configure("Title.TLabel", font=(family, 18, "bold"), foreground=c["primary"])
    style.configure("Muted.TLabel", foreground=c["muted"])
    style.configure("Error.TLabel", foreground=c["danger"], font=bold)
    style.configure("Ok.TLabel", foreground=c["ok"], font=bold)
    style.configure("Warn.TLabel", foreground=c["warn"], font=bold)
    style.configure("Banner.TLabel", background=c["header_bg"],
                    foreground=c["header_fg"], font=(family, 12, "bold"), padding=(10, 6))
    style.configure("TSeparator", background=c["border"])
    style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"])
    style.configure("TLabelframe.Label", background=c["bg"], foreground=c["primary"], font=bold)
    style.configure("TPanedwindow", background=c["bg"])

    def button_style(name, bg, fg, hover, padding=(12, 6), font=bold):
        style.configure(name, background=bg, foreground=fg, bordercolor=hover,
                        lightcolor=bg, darkcolor=bg, focuscolor=fg,
                        padding=padding, font=font)
        style.map(
            name,
            background=[("disabled", c["tab_bg"]), ("pressed", hover), ("active", hover)],
            foreground=[("disabled", c["muted"])],
            lightcolor=[("pressed", hover), ("active", hover)],
            darkcolor=[("pressed", hover), ("active", hover)],
        )

    button_style("TButton", c["primary"], c["primary_fg"], c["primary_dark"])
    button_style("Accent.TButton", c["accent"], c["accent_fg"], c["accent_dark"])
    button_style("Danger.TButton", c["danger"], c["danger_fg"], c["danger_dark"])
    button_style("Soft.TButton", c["surface"], c["fg"], c["tab_bg"], font=base)
    style.configure("Soft.TButton", bordercolor=c["border"])
    button_style("Day.TButton", c["surface"], c["fg"], c["select_bg"], padding=(4, 8), font=base)
    button_style("DayToday.TButton", c["today_bg"], c["fg"], c["accent"], padding=(4, 8))
    button_style("DaySelected.TButton", c["primary"], c["primary_fg"], c["primary_dark"], padding=(4, 8))
    button_style("DayMuted.TButton", c["bg"], c["muted"], c["select_bg"], padding=(4, 8), font=base)
    for name in ("Day.TButton", "DayToday.TButton", "DayMuted.TButton"):
        style.configure(name, bordercolor=c["border"])
    style.map("DayToday.TButton", foreground=[("disabled", c["muted"])])

    style.configure("TNotebook", background=c["bg"], bordercolor=c["border"],
                    tabmargins=(2, 6, 2, 0))
    style.configure("TNotebook.Tab", background=c["tab_bg"], foreground=c["fg"],
                    padding=(14, 6), font=bold, bordercolor=c["border"])
    style.map(
        "TNotebook.Tab",
        background=[("selected", c["primary"]), ("active", c["accent"])],
        foreground=[("selected", c["primary_fg"]), ("active", c["accent_fg"])],
        padding=[("selected", (16, 8))],
    )

    style.configure("Sub.TNotebook", background=c["bg"], bordercolor=c["border"],
                    tabmargins=(0, 4, 2, 0))
    style.configure("Sub.TNotebook.Tab", background=c["tab_bg"], foreground=c["fg"],
                    padding=(12, 5), font=base, bordercolor=c["border"])
    style.map("Sub.TNotebook.Tab",
              background=[("selected", c["accent"]), ("active", c["select_bg"])],
              foreground=[("selected", c["accent_fg"]), ("active", c["fg"])],
              padding=[("selected", (12, 6))])

    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"],
                    foreground=c["fg"], rowheight=26, bordercolor=c["border"],
                    borderwidth=1, font=base)
    style.map("Treeview",
              background=[("selected", c["select_bg"])],
              foreground=[("selected", c["select_fg"])])
    style.configure("Treeview.Heading", background=c["header_bg"], foreground=c["header_fg"],
                    font=bold, relief="flat", padding=(6, 5))
    style.map("Treeview.Heading", background=[("active", c["primary_dark"])])

    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=c["surface"], foreground=c["fg"],
                        bordercolor=c["border"], lightcolor=c["border"],
                        darkcolor=c["border"], insertcolor=c["fg"], padding=4,
                        arrowcolor=c["primary"], selectbackground=c["select_bg"],
                        selectforeground=c["select_fg"])
        style.map(name,
                  bordercolor=[("focus", c["primary"])],
                  lightcolor=[("focus", c["primary"])],
                  darkcolor=[("focus", c["primary"])],
                  fieldbackground=[("disabled", c["tab_bg"]), ("readonly", c["surface"])],
                  foreground=[("disabled", c["muted"])])
    style.configure("TCombobox", background=c["tab_bg"])
    style.configure("TSpinbox", background=c["tab_bg"])
    style.map("TCombobox", selectbackground=[("readonly", c["select_bg"])],
              selectforeground=[("readonly", c["select_fg"])])

    root.option_add("*TCombobox*Listbox.background", c["surface"])
    root.option_add("*TCombobox*Listbox.foreground", c["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", c["primary_fg"])
    root.option_add("*TCombobox*Listbox.font", base)
    root.option_add("*Menu.background", c["surface"])
    root.option_add("*Menu.foreground", c["fg"])
    root.option_add("*Menu.activeBackground", c["primary"])
    root.option_add("*Menu.activeForeground", c["primary_fg"])
    root.option_add("*Menu.relief", "flat")

    for prefix, background in (("", c["bg"]), ("Card.", c["surface"])):
        for kind in ("TCheckbutton", "TRadiobutton"):
            name = prefix + kind
            style.configure(name, background=background, foreground=c["fg"],
                            indicatorbackground=c["surface"], indicatorforeground=c["fg"],
                            bordercolor=c["border"], focuscolor=background, padding=3)
            style.map(name,
                      background=[("active", background)],
                      foreground=[("disabled", c["muted"])],
                      indicatorbackground=[("disabled", c["tab_bg"]), ("pressed", c["tab_bg"]),
                                           ("selected", c["primary"])],
                      indicatorforeground=[("disabled", c["muted"]), ("selected", c["primary_fg"])])

    style.configure("TScrollbar", background=c["border"], troughcolor=c["tab_bg"],
                    bordercolor=c["tab_bg"], arrowcolor=c["fg"], relief="flat")
    style.map("TScrollbar", background=[("active", c["primary"])])
    for name, bar in (("Horizontal.TProgressbar", c["primary"]),
                      ("Ready.Horizontal.TProgressbar", c["ok"]),
                      ("Late.Horizontal.TProgressbar", c["danger"])):
        style.configure(name, background=bar, troughcolor=c["tab_bg"],
                        bordercolor=c["border"], lightcolor=bar, darkcolor=bar,
                        thickness=14)
    return c


def style_text(widget):

    c = colors()
    widget.configure(
        background=c["surface"], foreground=c["fg"], insertbackground=c["fg"],
        selectbackground=c["select_bg"], selectforeground=c["select_fg"],
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground=c["border"], highlightcolor=c["primary"],
        font=(font_family(), 10), padx=6, pady=4,
    )


def style_listbox(widget):

    c = colors()
    widget.configure(
        background=c["surface"], foreground=c["fg"],
        selectbackground=c["select_bg"], selectforeground=c["select_fg"],
        relief="flat", borderwidth=0, highlightthickness=1,
        highlightbackground=c["border"], highlightcolor=c["primary"],
        activestyle="none", font=(font_family(), 10),
    )


def style_canvas(widget):

    c = colors()
    widget.configure(background=c["surface"], highlightthickness=1,
                     highlightbackground=c["border"])
