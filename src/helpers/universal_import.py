"""Centralized resource storage and safe spreadsheet import services."""
import csv
import hashlib
import mimetypes
import json
import io
import zipfile
import tempfile
import os
import re
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import config
import db

MAX_IMPORT_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024
BLOCKED_EXTENSIONS = {
    ".exe", ".dll", ".com", ".bat", ".cmd", ".msi", ".ps1", ".sh",
    ".py", ".pyc", ".vbs", ".js", ".mjs", ".cjs", ".php", ".html", ".htm",
    ".hta", ".asp", ".aspx", ".jsp", ".psm1", ".psd1", ".reg", ".lnk",
    ".url", ".desktop", ".jar", ".scr", ".app", ".appimage", ".apk",
    ".ipa", ".iso", ".dmg", ".pkg", ".deb", ".rpm"
}
SPREADSHEET_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CULTIVA_EXTENSION = ".cultiva"
CULTIVA_PACKAGE_VERSION = 1
# Only tables and columns that exist in Cultiva's current schema are exposed.
DESTINATIONS = {
    "Crops": {"table": "crops", "columns": {
        "name": {"required": True, "aliases": ("crop", "crop name", "plant", "plant name")},
        "color": {"required": False, "aliases": ("colour",)},
        "days_to_harvest": {"required": False, "aliases": ("days", "days to harvest", "harvest days")},
        "notes": {"required": False, "aliases": ("description", "remarks")}}, "unique": ("name",)},
    "Workers": {"table": "workers", "columns": {
        "name": {"required": True, "aliases": ("worker", "worker name", "employee", "full name")},
        "role": {"required": False, "aliases": ("position", "job", "designation")},
        "phone": {"required": False, "aliases": ("contact", "contact number", "mobile")},
        "daily_rate": {"required": False, "aliases": ("rate", "daily wage", "salary")},
        "active": {"required": False, "aliases": ("is active", "status")}}, "unique": ("name",)},
    "Plots": {"table": "plots", "columns": {
        "name": {"required": True, "aliases": ("plot", "plot name", "field", "bed", "bed name")},
        "area": {"required": False, "aliases": ("size", "land area")},
        "notes": {"required": False, "aliases": ("description", "remarks")}}, "unique": ("name",)},
    "Plantings": {"table": "plantings", "columns": {
        "plot_name": {"required": True, "aliases": ("plot", "plot name", "field")},
        "crop_name": {"required": True, "aliases": ("crop", "crop name", "plant")},
        "plant_date": {"required": True, "aliases": ("date planted", "planting date", "date")},
        "expected_harvest": {"required": False, "aliases": ("harvest date", "expected harvest date")},
        "status": {"required": False, "aliases": ()},
        "notes": {"required": False, "aliases": ("remarks", "description")}}, "unique": ("plot_name", "crop_name", "plant_date")},
    "Tasks": {"table": "tasks", "columns": {
        "title": {"required": True, "aliases": ("task", "task name", "description", "name")},
        "due_date": {"required": True, "aliases": ("date", "due", "deadline", "due date")},
        "priority": {"required": False, "aliases": ("urgency",)},
        "done": {"required": False, "aliases": ("completed", "is done")},
        "notes": {"required": False, "aliases": ("remarks", "details")},
        "plot_name": {"required": False, "aliases": ("plot", "plot name", "field")},
        "worker_name": {"required": False, "aliases": ("worker", "worker name", "assigned to")},
        "planting_plot_name": {"required": False, "aliases": ("planting plot",)},
        "planting_crop_name": {"required": False, "aliases": ("planting crop",)},
        "planting_date": {"required": False, "aliases": ("related planting date",)}}, "unique": ("title", "due_date")},
    "Shifts": {"table": "shifts", "columns": {
        "title": {"required": True, "aliases": ("shift", "activity", "routine", "task")},
        "weekday": {"required": True, "aliases": ("day", "day of week")},
        "start_time": {"required": True, "aliases": ("start", "from")},
        "end_time": {"required": True, "aliases": ("end", "to")},
        "worker_name": {"required": False, "aliases": ("worker", "worker name", "assigned to")},
        "plot_name": {"required": False, "aliases": ("plot", "plot name", "field")},
        "notes": {"required": False, "aliases": ("remarks", "details")}}, "unique": ("title", "weekday", "start_time")},
    "Attendance": {"table": "attendance", "columns": {
        "worker_name": {"required": True, "aliases": ("worker", "worker name", "employee")},
        "att_date": {"required": True, "aliases": ("date", "attendance date", "day")},
        "status": {"required": True, "aliases": ()},
        "time_in": {"required": False, "aliases": ("clock in", "time-in")},
        "time_out": {"required": False, "aliases": ("clock out", "time-out")},
        "remarks": {"required": False, "aliases": ("notes", "comments")}}, "unique": ("worker_name", "att_date")},
    "Journal": {"table": "journal_entries", "columns": {
        "entry_date": {"required": True, "aliases": ("date", "journal date")},
        "title": {"required": True, "aliases": ("subject", "heading")},
        "body": {"required": False, "aliases": ("content", "description", "details")},
        "mood_weather": {"required": False, "aliases": ("weather", "mood")},
        "plot_name": {"required": False, "aliases": ("plot", "plot name")},
        "crop_name": {"required": False, "aliases": ("crop", "crop name")}}, "unique": ("entry_date", "title")},
    "Notes": {"table": "notes", "columns": {
        "title": {"required": True, "aliases": ("subject", "heading", "note title")},
        "body": {"required": False, "aliases": ("content", "description", "details")},
        "plot_name": {"required": False, "aliases": ("plot", "plot name")},
        "crop_name": {"required": False, "aliases": ("crop", "crop name")}}, "unique": ("title",)},
}


CULTIVA_RECORD_FIELDS = ["record_type"] + list(dict.fromkeys(
    field for spec in DESTINATIONS.values() for field in spec["columns"]
))

def _safe_filename(name):
    name = Path(str(name)).name.replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9._ ()-]", "_", name).strip(" .")
    return (name or "imported_file")[:255]

def _file_info(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("The selected file does not exist.")
    ext = p.suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        raise ValueError("This file type is blocked for safety. Cultiva never executes imported files.")
    size = p.stat().st_size
    if size <= 0:
        raise ValueError("The selected file is empty.")
    if size > MAX_IMPORT_BYTES:
        raise ValueError("File exceeds the %d MB import limit." % config.MAX_UPLOAD_MB)
    return p, ext, size

def file_category(filename):
    ext = Path(filename).suffix.lower()
    if ext == ".cultiva": return "Cultiva package"
    if ext in {".xlsx", ".xls", ".csv"}: return "Spreadsheet"
    if ext == ".pdf": return "PDF document"
    if ext in {".doc", ".docx", ".odt"}: return "Document"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}: return "Image"
    if ext in {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}: return "Audio"
    if ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}: return "Video"
    return "Other"

def store_resource(path, description=None):
    """Deduplicated central storage; returns the existing resource for identical bytes."""
    source, ext, size = _file_info(path)
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    sha = digest.hexdigest()
    existing = db.query_one("SELECT * FROM resources WHERE sha256 = %s", (sha,))
    if existing:
        return existing, False
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored = uuid.uuid4().hex + ext
    target = config.UPLOAD_DIR / stored
    shutil.copy2(str(source), str(target))
    try:
        rid = db.execute(
            "INSERT INTO resources (stored_name, original_name, extension, category, "
            "mime_type, size_bytes, sha256, description) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (stored, _safe_filename(source.name), ext, file_category(source.name),
             mimetypes.guess_type(source.name)[0] or "application/octet-stream",
             size, sha, description))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return db.query_one("SELECT * FROM resources WHERE id = %s", (rid,)), True

def resource_path(resource):
    stored = resource["stored_name"]
    if Path(stored).name != stored or stored in ("", ".", ".."):
        raise ValueError("Invalid resource storage name.")
    return config.UPLOAD_DIR / stored

def list_resources(search=""):
    if search:
        pattern = db.like_pattern(search)
        return db.query(
            "SELECT * FROM resources WHERE original_name LIKE %s OR category LIKE %s "
            "ORDER BY created_at DESC, id DESC", (pattern, pattern))
    return db.query("SELECT * FROM resources ORDER BY created_at DESC, id DESC")

def parse_spreadsheet(path):
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        for encoding in ("utf-8-sig", "cp1252"):
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    rows = list(csv.reader(f))
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("CSV encoding could not be read. Save it as UTF-8 and try again.")
    elif ext == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise ValueError("XLSX support requires openpyxl. Install requirements.txt.")
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
    elif ext == ".xls":
        try:
            import xlrd
        except ImportError:
            raise ValueError("XLS support requires xlrd. Install requirements.txt.")
        book = xlrd.open_workbook(path, on_demand=True)
        sheet = book.sheet_by_index(0)
        rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        book.release_resources()
    else:
        raise ValueError("This is not a supported spreadsheet.")
    rows = [list(r) for r in rows if any(v not in (None, "") for v in r)]
    if len(rows) < 2:
        raise ValueError("The spreadsheet must contain a header row and at least one data row.")
    headers = [str(v).strip() if v is not None else "" for v in rows[0]]
    if not any(headers):
        raise ValueError("The first row must contain column names.")
    # Make duplicate/blank header names stable and distinguishable.
    seen = {}
    clean = []
    for i, header in enumerate(headers):
        base = header or "Column %d" % (i + 1)
        seen[base] = seen.get(base, 0) + 1
        clean.append(base if seen[base] == 1 else "%s (%d)" % (base, seen[base]))
    records = []
    for row_number, row in enumerate(rows[1:], start=2):
        records.append({clean[i]: (row[i] if i < len(row) else None) for i in range(len(clean))})
    return clean, records

def suggest_destination(headers):
    normalized = {re.sub(r"[^a-z0-9]+", " ", h.lower()).strip() for h in headers}
    scores = {}
    for label, spec in DESTINATIONS.items():
        aliases = set()
        for column, meta in spec["columns"].items():
            aliases.add(column.replace("_", " "))
            aliases.update(meta["aliases"])
        scores[label] = len(normalized.intersection(aliases))
    highest = max(scores.values())
    winners = [label for label, score in scores.items() if score == highest and score > 0]
    return winners[0] if len(winners) == 1 else None

def suggest_mapping(headers, destination):
    spec = DESTINATIONS[destination]
    mapping = {}
    for column, meta in spec["columns"].items():
        names = {column.replace("_", " "), *meta["aliases"]}
        match = next((h for h in headers if re.sub(r"[^a-z0-9]+", " ", h.lower()).strip() in names), None)
        mapping[column] = match or ""
    return mapping

def _parse_date(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError("use YYYY-MM-DD or a recognizable date")

def _parse_time(value):
    if isinstance(value, datetime): return value.strftime("%H:%M:%S")
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p"):
        try: return datetime.strptime(str(value).strip(), fmt).strftime("%H:%M:%S")
        except ValueError: pass
    raise ValueError("use HH:MM or a recognizable time")

def _clean_value(table, column, value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if column in ("name", "title", "role", "phone", "area", "color", "notes", "body", "mood_weather", "remarks", "plot_name", "crop_name", "worker_name"):
        return str(value).strip()
    if column == "days_to_harvest":
        number = int(float(value))
        if number < 0 or number > 3650: raise ValueError("must be between 0 and 3650")
        return number
    if column == "daily_rate":
        number = float(value)
        if number < 0: raise ValueError("cannot be negative")
        return round(number, 2)
    if column in ("active", "done"):
        v = str(value).strip().lower()
        if v in ("1", "true", "yes", "active", "done", "completed"): return 1
        if v in ("0", "false", "no", "inactive", "open", "pending"): return 0
        raise ValueError("use active/inactive, done/open, yes/no, or 1/0")
    if column in ("due_date", "plant_date", "expected_harvest", "att_date", "entry_date", "planting_date"):
        return _parse_date(value)
    if column in ("start_time", "end_time", "time_in", "time_out"):
        return _parse_time(value)
    if column == "priority":
        v = str(value).strip().lower()
        if v not in ("low", "medium", "high"): raise ValueError("use low, medium, or high")
        return v
    if column == "status":
        v = str(value).strip().lower().replace(" ", "_")
        allowed = {"plantings": ("growing", "harvested", "failed"), "attendance": ("present", "late", "half_day", "absent", "leave", "not_marked")}
        choices = allowed.get(table, ())
        if v not in choices: raise ValueError("choose one of: " + ", ".join(choices))
        return v
    if column == "weekday":
        days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        v = str(value).strip().lower()
        if v in days: return days[v]
        n = int(v)
        if n < 0 or n > 6: raise ValueError("use Monday-Sunday or 0-6 (Monday=0)")
        return n
    return value

def validate_rows(headers, records, destination, mapping):
    spec = DESTINATIONS[destination]
    issues, valid = [], []
    for index, record in enumerate(records, start=2):
        output, errors = {}, []
        for column, meta in spec["columns"].items():
            header = mapping.get(column, "")
            raw = record.get(header) if header else None
            if meta["required"] and raw in (None, ""):
                errors.append("%s is required" % column.replace("_", " ")); continue
            if raw not in (None, ""):
                try: output[column] = _clean_value(spec["table"], column, raw)
                except (ValueError, TypeError, OverflowError) as exc:
                    errors.append("%s: %s" % (column.replace("_", " "), exc))
        if destination == "Crops" and output.get("color") and not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(output["color"])):
            errors.append("color must be a hex value such as #4C9F50")
        if destination == "Plantings" and output.get("expected_harvest") and output.get("plant_date") and output["expected_harvest"] < output["plant_date"]:
            errors.append("expected harvest cannot be before plant date")
        if destination == "Shifts" and output.get("start_time") and output.get("end_time") and output["end_time"] <= output["start_time"]:
            errors.append("end time must be later than start time")
        if errors: issues.append({"row": index, "errors": errors})
        else: valid.append((index, output))
    return valid, issues

def _resolve_fk(table, name):
    if not name: return None
    matches = db.query("SELECT id FROM %s WHERE LOWER(name) = LOWER(%%s) LIMIT 2" % table, (name,))
    if not matches: raise ValueError("%s '%s' was not found; import it first" % (table[:-1], name))
    if len(matches) > 1:
        raise ValueError("%s '%s' is ambiguous because more than one matching record exists" % (table[:-1], name))
    return matches[0]["id"]

def _prepare_values(destination, values):
    values = dict(values)
    if destination in ("Plantings", "Tasks", "Shifts", "Attendance", "Journal", "Notes"):
        if "plot_name" in values: values["plot_id"] = _resolve_fk("plots", values.pop("plot_name"))
        if "crop_name" in values: values["crop_id"] = _resolve_fk("crops", values.pop("crop_name"))
        if "worker_name" in values: values["worker_id"] = _resolve_fk("workers", values.pop("worker_name"))
    if destination == "Tasks":
        planting_fields = ("planting_plot_name", "planting_crop_name", "planting_date")
        supplied = [values.get(field) not in (None, "") for field in planting_fields]
        if any(supplied):
            if not all(supplied):
                raise ValueError("related planting requires planting plot, planting crop and planting date")
            plot_id = _resolve_fk("plots", values.pop("planting_plot_name"))
            crop_id = _resolve_fk("crops", values.pop("planting_crop_name"))
            plant_date = values.pop("planting_date")
            planting = db.query_one("SELECT id FROM plantings WHERE plot_id=%s AND crop_id=%s AND plant_date=%s LIMIT 1", (plot_id, crop_id, plant_date))
            if not planting: raise ValueError("the related planting was not found; import it first")
            values["planting_id"] = planting["id"]
        else:
            for field in planting_fields: values.pop(field, None)
    if destination == "Plantings":
        if not values.get("expected_harvest"):
            crop = db.query_one("SELECT days_to_harvest FROM crops WHERE id = %s", (values["crop_id"],))
            from datetime import timedelta
            values["expected_harvest"] = (datetime.strptime(values["plant_date"], "%Y-%m-%d").date() + timedelta(days=int(crop["days_to_harvest"]))).isoformat()
    return values

def _unique_key(destination, values):
    spec = DESTINATIONS[destination]
    vals = []
    for col in spec["unique"]:
        if col.endswith("_name"):
            table = {"plot_name": "plots", "crop_name": "crops", "worker_name": "workers"}[col]
            vals.append(values.get(col) or "")
        else: vals.append(values.get(col) or "")
    return tuple(str(v).strip().casefold() for v in vals)

def detect_duplicates(destination, valid_rows):
    spec = DESTINATIONS[destination]
    seen, duplicates = set(), []
    for row_number, values in valid_rows:
        key = _unique_key(destination, values)
        if key in seen: duplicates.append(row_number); continue
        seen.add(key)
        try:
            prepared = _prepare_values(destination, values)
            unique_cols = spec["unique"]
            if destination == "Plantings":
                where, params = "plot_id=%s AND crop_id=%s AND plant_date=%s", (prepared["plot_id"], prepared["crop_id"], prepared["plant_date"])
            elif destination == "Attendance":
                where, params = "worker_id=%s AND att_date=%s", (prepared["worker_id"], prepared["att_date"])
            elif destination == "Shifts":
                where, params = "title=%s AND weekday=%s AND start_time=%s", (prepared["title"], prepared["weekday"], prepared["start_time"])
            elif destination in ("Tasks", "Journal"):
                where, params = ("title=%s AND due_date=%s", (prepared["title"], prepared["due_date"])) if destination == "Tasks" else ("title=%s AND entry_date=%s", (prepared["title"], prepared["entry_date"]))
            else:
                cols = spec["unique"]
                where = " AND ".join("LOWER(%s)=LOWER(%%s)" % c for c in cols)
                params = tuple(prepared[c] for c in cols)
            if db.query_one("SELECT id FROM %s WHERE %s LIMIT 1" % (spec["table"], where), params): duplicates.append(row_number)
        except ValueError:
            # Missing related names are validation/import errors, not duplicates.
            continue
    return duplicates

def import_records(destination, valid_rows):
    """Insert new records only. A single transaction rolls back on any failure."""
    spec = DESTINATIONS[destination]
    added, duplicates = 0, []
    with db.transaction():
        for row_number, values in valid_rows:
            prepared = _prepare_values(destination, values)
            if destination == "Plantings":
                where, params = "plot_id=%s AND crop_id=%s AND plant_date=%s", (prepared["plot_id"], prepared["crop_id"], prepared["plant_date"])
            elif destination == "Attendance":
                where, params = "worker_id=%s AND att_date=%s", (prepared["worker_id"], prepared["att_date"])
            elif destination == "Shifts":
                where, params = "title=%s AND weekday=%s AND start_time=%s", (prepared["title"], prepared["weekday"], prepared["start_time"])
            elif destination == "Tasks":
                where, params = "title=%s AND due_date=%s", (prepared["title"], prepared["due_date"])
            elif destination == "Journal":
                where, params = "title=%s AND entry_date=%s", (prepared["title"], prepared["entry_date"])
            else:
                cols = [c for c in spec["unique"]]
                where = " AND ".join("LOWER(%s)=LOWER(%%s)" % c for c in cols)
                params = tuple(prepared[c] for c in cols)
            if db.query_one("SELECT id FROM %s WHERE %s LIMIT 1" % (spec["table"], where), params):
                duplicates.append(row_number); continue
            columns = list(prepared)
            sql = "INSERT INTO %s (%s) VALUES (%s)" % (spec["table"], ", ".join(columns), ", ".join(["%s"] * len(columns)))
            db.execute(sql, tuple(prepared[c] for c in columns)); added += 1
    return added, duplicates


# Valid record owners for shared resource links. The owner table is selected
# only from this whitelist; caller-supplied identifiers are never interpolated.
RESOURCE_MODULES = {
    "crops": "crops", "workers": "workers", "plots": "plots",
    "plantings": "plantings", "tasks": "tasks", "shifts": "shifts",
    "attendance": "attendance", "journal": "journal_entries", "notes": "notes",
}

def link_resource(resource_id, module_key, record_id):
    if module_key not in RESOURCE_MODULES:
        raise ValueError("Unsupported resource destination module.")
    table = RESOURCE_MODULES[module_key]
    if not db.query_one("SELECT id FROM resources WHERE id = %s", (resource_id,)):
        raise ValueError("The Library resource does not exist.")
    if not db.query_one("SELECT id FROM %s WHERE id = %%s" % table, (record_id,)):
        raise ValueError("The destination record does not exist.")
    db.execute(
        "INSERT IGNORE INTO resource_links (resource_id, module_key, record_id) "
        "VALUES (%s, %s, %s)", (resource_id, module_key, record_id))

def unlink_resource(resource_id, module_key, record_id):
    db.execute(
        "DELETE FROM resource_links WHERE resource_id = %s AND module_key = %s AND record_id = %s",
        (resource_id, module_key, record_id))

def resources_for_record(module_key, record_id):
    if module_key not in RESOURCE_MODULES:
        raise ValueError("Unsupported resource destination module.")
    return db.query(
        "SELECT r.* FROM resources r JOIN resource_links l ON l.resource_id = r.id "
        "WHERE l.module_key = %s AND l.record_id = %s ORDER BY r.original_name",
        (module_key, record_id))

def resource_usage(resource_id):
    return db.query(
        "SELECT module_key, record_id, created_at FROM resource_links "
        "WHERE resource_id = %s ORDER BY module_key, record_id", (resource_id,))


# ---------------------------------------------------------------------------
# Portable Cultiva packages (.cultiva)
# ---------------------------------------------------------------------------
# The package uses natural-key references (names + dates), never source DB IDs.
# Import order is controlled so parent records exist before dependent records.
CULTIVA_EXPORT_QUERIES = {
    "Crops": "SELECT name,color,days_to_harvest,notes FROM crops ORDER BY id",
    "Workers": "SELECT name,role,phone,daily_rate,active FROM workers ORDER BY id",
    "Plots": "SELECT name,area,notes FROM plots ORDER BY id",
    "Plantings": ("SELECT p.name AS plot_name,c.name AS crop_name,pl.plant_date,"
                  "pl.expected_harvest,pl.status,pl.notes FROM plantings pl "
                  "JOIN plots p ON p.id=pl.plot_id JOIN crops c ON c.id=pl.crop_id ORDER BY pl.id"),
    "Tasks": ("SELECT t.title,t.due_date,t.priority,t.done,t.notes,p.name AS plot_name,"
              "w.name AS worker_name,pp.name AS planting_plot_name,pc.name AS planting_crop_name,"
              "pl.plant_date AS planting_date FROM tasks t LEFT JOIN plots p ON p.id=t.plot_id "
              "LEFT JOIN workers w ON w.id=t.worker_id LEFT JOIN plantings pl ON pl.id=t.planting_id "
              "LEFT JOIN plots pp ON pp.id=pl.plot_id LEFT JOIN crops pc ON pc.id=pl.crop_id ORDER BY t.id"),
    "Shifts": ("SELECT s.title,s.weekday,s.start_time,s.end_time,w.name AS worker_name,"
               "p.name AS plot_name,s.notes FROM shifts s LEFT JOIN workers w ON w.id=s.worker_id "
               "LEFT JOIN plots p ON p.id=s.plot_id ORDER BY s.id"),
    "Attendance": ("SELECT w.name AS worker_name,a.att_date,a.status,a.time_in,a.time_out,a.remarks "
                   "FROM attendance a JOIN workers w ON w.id=a.worker_id ORDER BY a.id"),
    "Journal": ("SELECT j.entry_date,j.title,j.body,j.mood_weather,p.name AS plot_name,"
                "c.name AS crop_name FROM journal_entries j LEFT JOIN plots p ON p.id=j.plot_id "
                "LEFT JOIN crops c ON c.id=j.crop_id ORDER BY j.id"),
    "Notes": ("SELECT n.title,n.body,p.name AS plot_name,c.name AS crop_name FROM notes n "
              "LEFT JOIN plots p ON p.id=n.plot_id LEFT JOIN crops c ON c.id=n.crop_id ORDER BY n.id"),
}
CULTIVA_IMPORT_ORDER = ("Crops", "Workers", "Plots", "Plantings", "Tasks", "Shifts", "Attendance", "Journal", "Notes")


def export_cultiva_package(destination_path):
    """Write a portable .cultiva ZIP package containing every supported record module."""
    from datetime import timezone
    destination = Path(destination_path)
    if destination.suffix.lower() != CULTIVA_EXTENSION:
        raise ValueError("Cultiva export files must use the .cultiva extension.")
    # Worker names are the portable reference used by attendance, shifts and tasks.
    # Refuse ambiguous source data rather than exporting relationships that cannot
    # be reconstructed safely on another installation.
    ambiguous_workers = db.query(
        "SELECT LOWER(name) AS normalized_name, COUNT(*) AS total FROM workers "
        "GROUP BY LOWER(name) HAVING COUNT(*) > 1 LIMIT 10")
    if ambiguous_workers:
        names = ", ".join(row["normalized_name"] for row in ambiguous_workers)
        raise ValueError("Cannot export safely: duplicate worker names make portable links ambiguous (%s). Rename the workers first." % names)
    rows = []
    counts = {}
    for module in CULTIVA_IMPORT_ORDER:
        module_rows = db.query(CULTIVA_EXPORT_QUERIES[module])
        counts[module] = len(module_rows)
        for record in module_rows:
            item = {key: record.get(key) for key in CULTIVA_RECORD_FIELDS if key != "record_type"}
            item["record_type"] = module
            rows.append(item)
    manifest = {
        "format": "Cultiva Portable Data Package",
        "format_id": "cultiva.portable",
        "package_version": CULTIVA_PACKAGE_VERSION,
        "minimum_importer_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_mode": __import__("translations").current_mode(),
        "record_file": "records.csv",
        "record_count": len(rows),
        "module_counts": counts,
        "modules": list(CULTIVA_IMPORT_ORDER),
        "identifier_strategy": "natural-key references; source database IDs are not exported",
        "notes": "Portable data records only. Library binary resources and note/journal attachments are not included in this package version."
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cultiva_export_") as temp_dir:
        csv_path = Path(temp_dir) / "records.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CULTIVA_RECORD_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                clean = {}
                for key, value in row.items():
                    if value is None:
                        clean[key] = ""
                    elif isinstance(value, timedelta):
                        seconds = int(value.total_seconds())
                        hours, remainder = divmod(seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        clean[key] = "%02d:%02d:%02d" % (hours, minutes, seconds)
                    elif hasattr(value, "isoformat"):
                        clean[key] = value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
                    else:
                        clean[key] = value
                writer.writerow(clean)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.write(csv_path, "records.csv")
            package.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def read_cultiva_package(path):
    """Validate package structure and return manifest, headers and records."""
    source = Path(path)
    if source.suffix.lower() != CULTIVA_EXTENSION:
        raise ValueError("Choose a .cultiva package.")
    if not zipfile.is_zipfile(source):
        raise ValueError("This .cultiva file is not a valid package archive.")
    with zipfile.ZipFile(source, "r") as package:
        names = set(package.namelist())
        if "manifest.json" not in names or "records.csv" not in names:
            raise ValueError("Package is incomplete: manifest.json and records.csv are required.")
        for info in package.infolist():
            name = Path(info.filename)
            if name.is_absolute() or ".." in name.parts:
                raise ValueError("Package contains an unsafe file path.")
            if info.file_size > MAX_IMPORT_BYTES:
                raise ValueError("A package entry exceeds the configured import size limit.")
        manifest = json.loads(package.read("manifest.json").decode("utf-8"))
        if manifest.get("format_id") != "cultiva.portable":
            raise ValueError("This is not a recognized Cultiva portable package.")
        version = manifest.get("package_version")
        if version != CULTIVA_PACKAGE_VERSION:
            raise ValueError("Unsupported Cultiva package version: %s" % version)
        raw = package.read("records.csv")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Package records are not valid UTF-8 CSV.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames or []
    if "record_type" not in headers:
        raise ValueError("Package records are missing the record_type column.")
    records = list(reader)
    if len(records) != int(manifest.get("record_count", -1)):
        raise ValueError("Package record count does not match its manifest.")
    unknown = sorted({r.get("record_type", "") for r in records} - set(DESTINATIONS))
    if unknown:
        raise ValueError("Package contains unsupported record types: " + ", ".join(unknown))
    return manifest, headers, records


def import_cultiva_package(path):
    """Import a .cultiva package atomically; parents are inserted before children."""
    manifest, headers, records = read_cultiva_package(path)
    grouped = {name: [] for name in CULTIVA_IMPORT_ORDER}
    issues = []
    for module, field in (("Crops", "name"), ("Workers", "name"), ("Plots", "name")):
        seen_names = set()
        for row_number, record in enumerate(records, start=2):
            if record.get("record_type", "").strip() != module:
                continue
            key = str(record.get(field, "")).strip().casefold()
            if key and key in seen_names:
                raise ValueError("Package contains repeated %s names; portable relationships would be ambiguous." % module.lower())
            if key:
                seen_names.add(key)
    for row_number, record in enumerate(records, start=2):
        module = record.get("record_type", "").strip()
        grouped[module].append((row_number, record))
    added = {name: 0 for name in CULTIVA_IMPORT_ORDER}
    duplicates = {name: 0 for name in CULTIVA_IMPORT_ORDER}
    invalid = []
    # Validate all rows before starting a database transaction.
    validated = {name: [] for name in CULTIVA_IMPORT_ORDER}
    for module in CULTIVA_IMPORT_ORDER:
        spec = DESTINATIONS[module]
        mapping = {field: field for field in spec["columns"]}
        for row_number, record in grouped[module]:
            valid, row_issues = validate_rows(headers, [record], module, mapping)
            if row_issues:
                invalid.append({"row": row_number, "record_type": module, "errors": row_issues[0]["errors"]})
            else:
                validated[module].append((row_number, valid[0][1]))
    if invalid:
        preview = "; ".join("row %s (%s): %s" % (x["row"], x["record_type"], ", ".join(x["errors"])) for x in invalid[:8])
        raise ValueError("Package validation failed; no records were imported. %s%s" % (preview, " …" if len(invalid) > 8 else ""))

    def duplicate_query(module, prepared):
        table = DESTINATIONS[module]["table"]
        if module == "Plantings":
            where, params = "plot_id=%s AND crop_id=%s AND plant_date=%s", (prepared["plot_id"], prepared["crop_id"], prepared["plant_date"])
        elif module == "Attendance":
            where, params = "worker_id=%s AND att_date=%s", (prepared["worker_id"], prepared["att_date"])
        elif module == "Shifts":
            where, params = "title=%s AND weekday=%s AND start_time=%s", (prepared["title"], prepared["weekday"], prepared["start_time"])
        elif module == "Tasks":
            where, params = "title=%s AND due_date=%s", (prepared["title"], prepared["due_date"])
        elif module == "Journal":
            where, params = "title=%s AND entry_date=%s", (prepared["title"], prepared["entry_date"])
        else:
            cols = DESTINATIONS[module]["unique"]
            where = " AND ".join("LOWER(%s)=LOWER(%%s)" % c for c in cols)
            params = tuple(prepared[c] for c in cols)
        return db.query_one("SELECT id FROM %s WHERE %s LIMIT 1" % (table, where), params)

    with db.transaction():
        for module in CULTIVA_IMPORT_ORDER:
            table = DESTINATIONS[module]["table"]
            for row_number, values in validated[module]:
                prepared = _prepare_values(module, values)
                if duplicate_query(module, prepared):
                    duplicates[module] += 1
                    continue
                columns = list(prepared)
                sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, ", ".join(columns), ", ".join(["%s"] * len(columns)))
                db.execute(sql, tuple(prepared[c] for c in columns))
                added[module] += 1
    return {"manifest": manifest, "added": added, "duplicates": duplicates, "invalid": invalid}
