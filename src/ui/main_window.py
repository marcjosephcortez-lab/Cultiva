

import importlib
import tkinter as tk
import traceback
from tkinter import ttk

import config
import db
import settings
import theme
import translations
from helpers import dialogs
from ui.placeholder import ErrorTab, PlaceholderTab
from ui.welcome import WelcomeScreen

tr = translations.tr

TAB_MODULES = {
    "today": ("ui.today", "TodayTab", 6),
    "agenda": ("ui.agenda", "AgendaTab", 5),
    "calendar": ("ui.calendar_tab", "CalendarTab", 7),
    "timetable": ("ui.timetable", "TimetableTab", 8),
    "attendance": ("ui.attendance", "AttendanceTab", 9),
    "journal": ("ui.journal", "JournalTab", 10),
    "notes": ("ui.notes", "NotesTab", 10),
    "library": ("ui.library", "LibraryTab", 11),
    "manage": ("ui.manage", "ManageTab", 4),
}

WINDOW_SIZE = (1180, 740)
MIN_SIZE = (960, 620)


class MainWindow:


    def __init__(self, root, mode=None):
        self.root = root
        self.notebook = None
        self.tab_widgets = {}   
        self.mode_var = tk.StringVar(value=translations.current_mode())

        root.minsize(*MIN_SIZE)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.bind("<Control-q>", lambda event: self.quit())
        root.bind("<F5>", lambda event: self.refresh_current())

        if mode is None:
            self.show_welcome()
        else:
            self.show_main(mode)

    def _clear(self):

        self.notebook = None
        self.tab_widgets = {}
        for child in self.root.winfo_children():
            child.destroy()

    def show_welcome(self):

        self._clear()
        self.root.title("Cultiva")
        self._build_menu(with_settings=False)
        screen = WelcomeScreen(self.root, on_choose=self.choose_first_mode)
        screen.pack(fill="both", expand=True)

    def choose_first_mode(self, mode):

        try:
            settings.set_mode(mode)  
        except db.DBError as exc:
            dialogs.show_db_error(self.root, exc, "Could not save your choice")
            return
        self.show_main(mode)

    def show_main(self, mode, select_key=None):

        translations.set_current_mode(mode)
        theme.apply_theme(self.root, mode)
        self._clear()
        self.mode_var.set(mode)
        self.root.title("Cultiva")
        self._build_menu(with_settings=True)
        self._build_header()
        self._build_notebook(select_key)

    def _build_header(self):
        bar = ttk.Frame(self.root, style="Banner.TFrame")
        bar.pack(fill="x")
        ttk.Label(bar, text="Cultiva", style="Banner.TLabel").pack(side="left")
        ttk.Label(bar, text=tr("mode_name") + " mode",
                  style="Banner.TLabel").pack(side="right")

    def _build_notebook(self, select_key):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        for key, label in translations.tabs():
            tab = self._make_tab(key, label)
            self.notebook.add(tab, text=label)
            self.tab_widgets[key] = tab
        if select_key in self.tab_widgets:
            self.notebook.select(self.tab_widgets[select_key])
        self.notebook.bind("<<NotebookTabChanged>>", lambda event: self.refresh_current())
        self.root.after(50, self.refresh_current)  

    def _make_tab(self, key, label):

        module_name, class_name, step = TAB_MODULES[key]
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:          
                return PlaceholderTab(self.notebook, self, key, step)
            return self._error_tab(label, exc)   
        except Exception as exc:
            return self._error_tab(label, exc)

        tab_class = getattr(module, class_name, None)
        if tab_class is None:
            return PlaceholderTab(self.notebook, self, key, step)
        try:
            return tab_class(self.notebook, self)
        except Exception as exc:
            return self._error_tab(label, exc)

    def _error_tab(self, label, exc):
        traceback.print_exc()
        return ErrorTab(self.notebook, label, "%s: %s" % (type(exc).__name__, exc))

    def _build_menu(self, with_settings):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        if with_settings:
            file_menu.add_command(label="Refresh current tab", accelerator="F5",
                                  command=self.refresh_current)
            file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        if with_settings:
            settings_menu = tk.Menu(menubar, tearoff=False)
            settings_menu.add_command(label="Refresh current tab", accelerator="F5",
                                      command=self.refresh_current)
            settings_menu.add_separator()
            mode_menu = tk.Menu(settings_menu, tearoff=False)
            for mode in translations.MODES:
                mode_menu.add_radiobutton(
                    label=tr("mode_name", mode) + " mode", value=mode,
                    variable=self.mode_var,
                    command=lambda m=mode: self.switch_mode(m))
            settings_menu.add_cascade(label="Switch mode", menu=mode_menu)
            menubar.add_cascade(label="Settings", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menubar)

    def show_about(self):
        dialogs.show_info(
            self.root,
            "Garden / Farm Planner\n\n"
            "A planner for a garden or a farm, built with Python, Tkinter and MySQL.\n\n"
            "Database: %s on %s:%s\n"
            "Mode: %s\n"
            "Refresh the current tab with F5 or the Refresh button."
            % (config.DB_NAME, config.DB_HOST, config.DB_PORT, tr("mode_name")),
            title="About")

    def switch_mode(self, new_mode):

        current = translations.current_mode()
        if new_mode == current:
            return
        question = ("Switch to %s mode?\n\nFarm and Garden use separate records. "
                    "You will only see and edit data belonging to the selected mode."
                    % tr("mode_name", new_mode))
        if not dialogs.ask_yes_no(self.root, question, title="Switch mode"):
            self.mode_var.set(current)   
            return
        try:
            settings.set_mode(new_mode)
        except db.DBError as exc:
            self.mode_var.set(current)
            dialogs.show_db_error(self.root, exc, "Could not switch mode")
            return
        self.show_main(new_mode, select_key=self.current_tab_key())

    def _current_widget(self):

        if self.notebook is None:
            return None
        path = self.notebook.select()
        if not path:
            return None
        try:
            return self.root.nametowidget(path)
        except KeyError:
            return None

    def current_tab_key(self):

        widget = self._current_widget()
        for key, tab in self.tab_widgets.items():
            if tab is widget:
                return key
        return None

    def refresh_current(self):

        widget = self._current_widget()
        refresh = getattr(widget, "refresh", None)
        if refresh is None:
            return
        try:
            refresh()
        except db.DBError as exc:
            dialogs.show_db_error(self.root, exc)
        except Exception as exc:  
            traceback.print_exc()
            dialogs.show_error(self.root, "This tab could not refresh:\n%s: %s"
                               % (type(exc).__name__, exc))

    def quit(self):

        db.close()
        self.root.destroy()
