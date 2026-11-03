

from tkinter import messagebox

import db
from helpers import files
from helpers import validation as v


def show_info(parent, message, title="Information"):
    messagebox.showinfo(title, message, parent=parent)


def show_warning(parent, message, title="Please check"):
    messagebox.showwarning(title, message, parent=parent)


def show_error(parent, message, title="Something went wrong"):
    messagebox.showerror(title, message, parent=parent)


def ask_yes_no(parent, message, title="Please confirm"):

    return messagebox.askyesno(title, message, parent=parent,
                               icon="question", default="no")


def show_validation_error(parent, error):

    messagebox.showwarning("Please check the form", error.message, parent=parent)


def show_db_error(parent, error, title="Database problem"):

    messagebox.showerror(title, str(error), parent=parent)


def show_file_error(parent, error, title="File problem"):

    messagebox.showwarning(title, str(error), parent=parent)


def confirm_delete(parent, kind, name, warning=""):

    text = "Delete the %s \"%s\"?" % (kind, name)
    if warning:
        text += "\n\n" + warning
    text += "\n\nThis cannot be undone."
    return ask_yes_no(parent, text, title="Delete %s" % kind)


def delete_record(parent, kind, name, delete_func, in_use_hint="", warning=""):

    if not confirm_delete(parent, kind, name, warning):
        return False
    try:
        delete_func()
    except db.DBInUseError:
        message = ("The %s \"%s\" cannot be deleted because other records "
                   "still use it." % (kind, name))
        if in_use_hint:
            message += "\n\n" + in_use_hint
        messagebox.showwarning("Cannot delete", message, parent=parent)
        return False
    except db.DBError as exc:
        show_db_error(parent, exc)
        return False
    return True


def safe_call(parent, func, *args, **kwargs):

    try:
        return True, func(*args, **kwargs)
    except db.DBError as exc:
        show_db_error(parent, exc)
    except files.FileRejected as exc:
        show_file_error(parent, exc)
    except v.ValidationError as exc:
        show_validation_error(parent, exc)
    return False, None
