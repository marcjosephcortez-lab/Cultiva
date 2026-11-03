

FARM = "farm"
GARDEN = "garden"
MODES = (FARM, GARDEN)

WORDS = {
    FARM: {
        "app_title": "Farm Planner",
        "mode_name": "Farm",
        "plot": "Plot", "plots": "Plots",
        "worker": "Worker", "workers": "Workers",
        "crop": "Crop", "crops": "Crops",
        "planting": "Planting", "plantings": "Plantings",
        "harvest": "Harvest",
        "shift": "Shift", "shifts": "Shifts",
        "timetable": "Timetable",
        "shift_name": "Shift name",
        "add_shift": "Add shift",
        "on_duty_today": "On shift today",
        "growing_now": "Growing now",
        "days_to_harvest": "Days to harvest",
        "daily_rate": "Daily rate",
        "tab_today": "Today",
        "tab_agenda": "Agenda",
        "tab_calendar": "Calendar",
        "tab_timetable": "Timetable",
        "tab_attendance": "Attendance",
        "tab_journal": "Journal",
        "tab_notes": "Notes",
        "tab_library": "Library",
        "tab_manage": "Manage",
    },
    GARDEN: {
        "app_title": "Garden Planner",
        "mode_name": "Garden",
        "plot": "Bed", "plots": "Beds",
        "worker": "Helper", "workers": "Helpers",
        "crop": "Plant", "crops": "Plants",
        "planting": "Planting", "plantings": "Plantings",
        "harvest": "Harvest",
        "shift": "Care routine", "shifts": "Care routines",
        "timetable": "Care schedule",
        "shift_name": "Routine name",
        "add_shift": "Add care routine",
        "on_duty_today": "Care scheduled today",
        "growing_now": "Growing now",
        "days_to_harvest": "Days to harvest",
        "daily_rate": "Daily rate",
        "tab_today": "Today",
        "tab_agenda": "Agenda",
        "tab_calendar": "Calendar",
        "tab_timetable": "Care schedule",
        "tab_attendance": "Attendance",
        "tab_journal": "Journal",
        "tab_notes": "Notes",
        "tab_library": "Library",
        "tab_manage": "Manage",
    },
}

FEATURES = {
    FARM: {"attendance": True, "pay": True},
    GARDEN: {"attendance": False, "pay": False},
}

TAB_ORDER = ("today", "agenda", "calendar", "timetable", "attendance",
             "journal", "notes", "library", "manage")

_current_mode = FARM


def set_current_mode(mode):

    global _current_mode
    if mode not in MODES:
        raise ValueError("Unknown mode: %r (expected 'farm' or 'garden')" % (mode,))
    _current_mode = mode
    try:
        import db
        db.set_active_mode(mode)
    except ImportError:
        pass


def current_mode():

    return _current_mode


def tr(key, mode=None):

    words = WORDS[mode or _current_mode]
    return words.get(key, "[%s]" % key)


def tr_lower(key, mode=None):

    return tr(key, mode).lower()


def feature(name, mode=None):

    return FEATURES[mode or _current_mode].get(name, False)


def tabs(mode=None):

    result = []
    for key in TAB_ORDER:
        if key == "attendance" and not feature("attendance", mode):
            continue
        result.append((key, tr("tab_" + key, mode)))
    return result
