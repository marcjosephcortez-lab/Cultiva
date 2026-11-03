

from datetime import date

import db
import translations
from helpers import dialogs
from helpers import validation as v
from helpers.forms import Field, ask_form

tr = translations.tr

PRIORITY_OPTIONS = [("low", "Low"), ("medium", "Medium"), ("high", "High")]


def planting_label(row):

    text = "%s in %s (planted %s)" % (row["crop_name"], row["plot_name"],
                                      v.date_to_text(row["plant_date"]))
    if row["status"] != "growing":
        text += " - " + row["status"]
    return text


def load_options(task=None):

    plots = [(r["id"], r["name"])
             for r in db.query("SELECT id, name FROM plots ORDER BY name")]

    planting_rows = db.query(
        "SELECT pl.id, pl.plot_id, pl.plant_date, pl.status, p.name AS plot_name, "
        "c.name AS crop_name FROM plantings pl "
        "JOIN plots p ON p.id = pl.plot_id JOIN crops c ON c.id = pl.crop_id "
        "ORDER BY pl.plant_date DESC, pl.id DESC")
    plantings = [(r["id"], planting_label(r)) for r in planting_rows]
    planting_plot = {r["id"]: r["plot_id"] for r in planting_rows}

    keep_worker = task.get("worker_id") if task else None
    workers = []
    for r in db.query("SELECT id, name, active FROM workers ORDER BY name"):
        if r["active"] or r["id"] == keep_worker:
            workers.append((r["id"], r["name"] + ("" if r["active"] else " (inactive)")))

    return {"plots": plots, "plantings": plantings, "workers": workers,
            "planting_plot": planting_plot}


def build_fields(options):

    return [
        Field("title", "Task", required=True, max_length=200, width=40),
        Field("due_date", "Due date", kind="date", required=True),
        Field("priority", "Priority", kind="combo", required=True, options=PRIORITY_OPTIONS),
        Field("plot_id", tr("plot"), kind="combo", options=options["plots"]),
        Field("planting_id", tr("planting"), kind="combo", options=options["plantings"],
              hint="Optional. Choosing one also fills in its %s." % tr("plot").lower()),
        Field("worker_id", tr("worker"), kind="combo", options=options["workers"]),
        Field("done", "Done", kind="check", hint="Tick when the task is finished"),
        Field("notes", "Notes", kind="multiline"),
    ]


def make_rule(options):

    plot_names = dict(options["plots"])

    def check(values):
        planting_id, plot_id = values["planting_id"], values["plot_id"]
        if planting_id and plot_id and options["planting_plot"].get(planting_id) != plot_id:
            where = plot_names.get(options["planting_plot"].get(planting_id), "another %s"
                                   % tr("plot").lower())
            raise v.ValidationError(
                "That planting is in %s, not in the chosen %s. Pick the same %s, "
                "or leave the %s empty." % (where, tr("plot").lower(), tr("plot").lower(),
                                            tr("plot").lower()),
                field="plot_id")
    return check


def insert_task(values):

    return db.execute(
        "INSERT INTO tasks (title, due_date, priority, done, notes, plot_id, "
        "planting_id, worker_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (values["title"], values["due_date"], values["priority"],
         1 if values["done"] else 0, values["notes"], values["plot_id"],
         values["planting_id"], values["worker_id"]))


def update_task(task_id, values):

    db.execute(
        "UPDATE tasks SET title = %s, due_date = %s, priority = %s, done = %s, "
        "notes = %s, plot_id = %s, planting_id = %s, worker_id = %s WHERE id = %s",
        (values["title"], values["due_date"], values["priority"],
         1 if values["done"] else 0, values["notes"], values["plot_id"],
         values["planting_id"], values["worker_id"], task_id))


def open_task_form(parent, task=None, defaults=None):

    try:
        options = load_options(task)
    except db.DBError as exc:
        dialogs.show_db_error(parent, exc)
        return None

    if task is not None:
        start = dict(task)
        start["done"] = bool(task["done"])
    else:
        start = {"due_date": date.today(), "priority": "medium"}
        start.update(defaults or {})

    saved = {}

    def save(values):
        if values["planting_id"] and not values["plot_id"]:
            values["plot_id"] = options["planting_plot"].get(values["planting_id"])
        if task is None:
            saved["id"] = insert_task(values)
        else:
            update_task(task["id"], values)
            saved["id"] = task["id"]

    title = "Add task" if task is None else "Edit task"
    result = ask_form(parent, title, build_fields(options), values=start, save=save,
                      validate=make_rule(options))
    return saved.get("id") if result else None
