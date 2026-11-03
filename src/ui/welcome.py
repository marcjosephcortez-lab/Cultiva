

import tkinter as tk
from tkinter import ttk

import theme
import translations

tr = translations.tr


def _define_card_styles():

    style = ttk.Style()
    family = theme.font_family()
    for mode, pal in theme.PALETTES.items():
        prefix = mode.title()
        style.configure(prefix + "Card.TFrame", background=pal["surface"], relief="solid",
                        borderwidth=1, bordercolor=pal["border"])
        style.configure(prefix + "Card.TLabel", background=pal["surface"], foreground=pal["fg"])
        style.configure(prefix + "CardTitle.TLabel", background=pal["surface"],
                        foreground=pal["primary"], font=(family, 18, "bold"))
        style.configure(prefix + "CardMuted.TLabel", background=pal["surface"],
                        foreground=pal["muted"])
        style.configure(prefix + "Choice.TButton", background=pal["primary"],
                        foreground=pal["primary_fg"], bordercolor=pal["primary_dark"],
                        lightcolor=pal["primary"], darkcolor=pal["primary"],
                        focuscolor=pal["primary_fg"], padding=(16, 10),
                        font=(family, 11, "bold"))
        style.map(prefix + "Choice.TButton",
                  background=[("pressed", pal["primary_dark"]), ("active", pal["primary_dark"])],
                  lightcolor=[("pressed", pal["primary_dark"]), ("active", pal["primary_dark"])],
                  darkcolor=[("pressed", pal["primary_dark"]), ("active", pal["primary_dark"])])


class WelcomeScreen(ttk.Frame):


    def __init__(self, parent, on_choose):
        super().__init__(parent, padding=30)
        self.on_choose = on_choose
        _define_card_styles()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        inner = ttk.Frame(self)
        inner.grid(row=1, column=0)

        ttk.Label(inner, text="Welcome to the Planner", style="Title.TLabel").pack()
        ttk.Label(
            inner, justify="center", wraplength=640, style="Muted.TLabel",
            text="What are you planning? Pick one to begin. You can switch at any time "
                 "Farm and Garden keep separate records when you switch modes.",
        ).pack(pady=(6, 20))

        cards = ttk.Frame(inner)
        cards.pack()
        farm = self._make_card(cards, "farm", "Use Farm mode")
        garden = self._make_card(cards, "garden", "Use Garden mode")
        farm.grid(row=0, column=0, padx=12, sticky="nsew")      
        garden.grid(row=0, column=1, padx=12, sticky="nsew")    
        cards.columnconfigure(0, weight=1, uniform="card")
        cards.columnconfigure(1, weight=1, uniform="card")

        self.after(100, self.farm_button.focus_set)  

    def _make_card(self, parent, mode, button_text):

        pal = theme.PALETTES[mode]
        prefix = mode.title()
        card = ttk.Frame(parent, style=prefix + "Card.TFrame", padding=22)

        button = ttk.Button(card, text=button_text, style=prefix + "Choice.TButton",
                            command=lambda: self.on_choose(mode))
        button.pack(side="bottom", fill="x", pady=(16, 0))
        button.bind("<Return>", lambda event: button.invoke())  
        setattr(self, mode + "_button", button)

        swatches = tk.Frame(card, background=pal["surface"])
        swatches.pack(anchor="w", pady=(0, 10))
        for color in (pal["primary"], pal["accent"]):
            tk.Frame(swatches, width=44, height=12, background=color).pack(side="left", padx=(0, 4))

        ttk.Label(card, text=tr("mode_name", mode), style=prefix + "CardTitle.TLabel").pack(anchor="w")

        things = "%s, %s, %s and %s" % (tr("plots", mode), tr("workers", mode),
                                       tr("crops", mode), tr("plantings", mode))
        if mode == "farm":
            lines = [things,
                     "Attendance sheet and pay estimates for workers",
                     "Shifts on a weekly timetable",
                     "Deep green with palay gold"]
        else:
            lines = [things,
                     "A care schedule for watering and tending",
                     "No attendance sheet and no pay",
                     "Soft leaf green with blossom pink"]
        for line in lines:
            ttk.Label(card, text="\u2022 " + line, style=prefix + "Card.TLabel",
                      wraplength=250, justify="left").pack(anchor="w", pady=2)

        return card
