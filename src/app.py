

import sys
import tkinter as tk
from tkinter import messagebox

import db
import settings
import setup_db
import theme
from ui.main_window import MainWindow, WINDOW_SIZE


def connect_to_database():
    while True:
        try:
            setup_db.initialize_database()
            return True, settings.load_mode()
        except db.DBError as exc:
            retry = messagebox.askretrycancel(
                "Cannot use the database",
                str(exc) + "\n\nPress Retry after fixing the problem, or Cancel to quit.",
                icon="error")
            if not retry:
                return False, None
            db.close()  


def center_window(root, width, height):
    width = min(width, root.winfo_screenwidth() - 60)
    height = min(height, root.winfo_screenheight() - 100)
    x = (root.winfo_screenwidth() - width) // 2
    y = max((root.winfo_screenheight() - height) // 3, 0)
    root.geometry("%dx%d+%d+%d" % (width, height, x, y))


def main():
    root = tk.Tk()
    root.withdraw()                 
    theme.apply_theme(root, "farm")  

    connected, mode = connect_to_database()
    if not connected:
        root.destroy()
        return 1

    center_window(root, *WINDOW_SIZE)
    MainWindow(root, mode)
    root.deiconify()
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
