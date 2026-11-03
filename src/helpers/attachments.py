

import mimetypes
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import config
import db

try:
    from PIL import Image
except ImportError:  
    Image = None

MAX_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
DOCUMENT_EXTENSIONS = (".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx")
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS

SIGNATURES = {
    ".pdf": b"%PDF",
    ".docx": b"PK",
    ".xlsx": b"PK",
}

OWNERS = {
    "note": {"column": "note_id", "table": "notes"},
    "journal": {"column": "journal_id", "table": "journal_entries"},
}


class AttachmentError(Exception):
    pass


def _owner(kind):
    if kind not in OWNERS:
        raise ValueError("Unknown attachment owner: %r (use 'note' or 'journal')" % (kind,))
    return OWNERS[kind]


def format_size(size_bytes):

    size = float(size_bytes or 0)
    if size < 1024:
        return "%d bytes" % size
    if size < 1024 * 1024:
        return "%d KB" % round(size / 1024)
    return "%.1f MB" % (size / (1024 * 1024))


def validate_file(path):

    path = Path(path)
    name = path.name

    if not path.is_file():
        raise AttachmentError("'%s' was not found. Was it moved or deleted?" % name)

    extension = path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise AttachmentError(
            "'%s' cannot be attached: %s files are not allowed.\n"
            "Allowed types: %s" % (
                name, extension or "this kind of",
                ", ".join(e.lstrip(".") for e in ALLOWED_EXTENSIONS)))

    try:
        size = path.stat().st_size
    except OSError as exc:
        raise AttachmentError("Could not read '%s': %s" % (name, exc)) from exc
    if size == 0:
        raise AttachmentError("'%s' is empty (0 bytes)." % name)
    if size > MAX_BYTES:
        raise AttachmentError(
            "'%s' is too big (%s). The limit is %d MB per file."
            % (name, format_size(size), config.MAX_UPLOAD_MB))

    _check_really_that_type(path, extension)
    return size


def _check_really_that_type(path, extension):

    signature = SIGNATURES.get(extension)
    if signature is not None:
        try:
            with open(path, "rb") as handle:
                start = handle.read(len(signature))
        except OSError as exc:
            raise AttachmentError("Could not read '%s': %s" % (path.name, exc)) from exc
        if start != signature:
            raise AttachmentError(
                "'%s' does not look like a real %s file (it may have been renamed)."
                % (path.name, extension.lstrip(".").upper()))

    if extension in IMAGE_EXTENSIONS and Image is not None:
        try:
            with Image.open(path) as picture:
                picture.verify()  
        except Exception as exc:  
            raise AttachmentError(
                "'%s' does not look like a real picture (it may be damaged "
                "or renamed)." % path.name) from exc


def upload_dir():

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return config.UPLOAD_DIR


def stored_path(stored_name):

    return config.UPLOAD_DIR / Path(stored_name).name


def remove_stored_file(stored_name):

    try:
        stored_path(stored_name).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def add_attachment(owner_kind, owner_id, source_path):

    column = _owner(owner_kind)["column"]
    source = Path(source_path)
    size = validate_file(source)

    stored_name = uuid.uuid4().hex + source.suffix.lower()
    target = upload_dir() / stored_name
    try:
        shutil.copy2(source, target)
    except OSError as exc:
        raise AttachmentError("Could not copy '%s' into the uploads folder: %s"
                              % (source.name, exc)) from exc

    mime_type = mimetypes.guess_type(source.name)[0]
    try:
        return db.execute(
            "INSERT INTO attachments (" + column + ", stored_name, original_name, "
            "mime_type, size_bytes) VALUES (%s, %s, %s, %s, %s)",
            (owner_id, stored_name, source.name[:255], mime_type, size))
    except Exception:
        remove_stored_file(stored_name)  
        raise


def list_attachments(owner_kind, owner_id):

    column = _owner(owner_kind)["column"]
    return db.query(
        "SELECT id, stored_name, original_name, mime_type, size_bytes "
        "FROM attachments WHERE " + column + " = %s ORDER BY id", (owner_id,))


def delete_attachment(attachment_id):

    row = db.query_one("SELECT stored_name FROM attachments WHERE id = %s",
                       (attachment_id,))
    if row is None:
        return
    db.execute("DELETE FROM attachments WHERE id = %s", (attachment_id,))
    remove_stored_file(row["stored_name"])


def delete_owner(owner_kind, owner_id):

    table = _owner(owner_kind)["table"]
    names = [row["stored_name"] for row in list_attachments(owner_kind, owner_id)]
    db.execute("DELETE FROM " + table + " WHERE id = %s", (owner_id,))
    for name in names:
        remove_stored_file(name)


def open_file(path):

    path = Path(path)
    if not path.is_file():
        raise AttachmentError(
            "The file '%s' could not be found on this computer.\n"
            "It may have been moved or deleted outside the app." % path.name)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))                      
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])        
        else:
            subprocess.Popen(["xdg-open", str(path)])    
    except OSError as exc:
        raise AttachmentError("Could not open '%s': %s" % (path.name, exc)) from exc
