

import mimetypes
import os
import secrets
import shutil
import subprocess
import sys

import config

CATEGORIES = {
    "Image": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
    "Video": {".mp4", ".mov", ".avi", ".mkv", ".webm"},
    "Audio": {".mp3", ".wav", ".ogg", ".m4a", ".aac"},
    "PDF": {".pdf"},
    "Office": {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
               ".odt", ".ods", ".odp", ".csv"},
}
ALLOWED_EXTENSIONS = set().union(*CATEGORIES.values())
MAX_BYTES = config.MAX_UPLOAD_MB * 1024 * 1024


class FileRejected(Exception):
    pass


def format_size(num_bytes):

    size = float(num_bytes)
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "bytes":
                return "%d bytes" % size
            return "%.1f %s" % (size, unit)
        size /= 1024.0


def category_of(filename):

    ext = os.path.splitext(filename)[1].lower()
    for name, extensions in CATEGORIES.items():
        if ext in extensions:
            return name
    return "Other"


def is_image(filename):
    return category_of(filename) == "Image"


def allowed_types_text():

    return "photos (JPG, PNG, GIF, BMP, WEBP), videos, audio, PDF and Office files"


def filedialog_types():

    def pattern(extensions):
        return " ".join("*" + ext for ext in sorted(extensions))
    return [
        ("All allowed files", pattern(ALLOWED_EXTENSIONS)),
        ("Photos", pattern(CATEGORIES["Image"])),
        ("Videos", pattern(CATEGORIES["Video"])),
        ("Audio", pattern(CATEGORIES["Audio"])),
        ("PDF", pattern(CATEGORIES["PDF"])),
        ("Office files", pattern(CATEGORIES["Office"])),
    ]


def validate_file(path):

    path = str(path)
    if not os.path.isfile(path):
        raise FileRejected("The file could not be found:\n%s" % path)

    original_name = os.path.basename(path)
    extension = os.path.splitext(original_name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        shown = extension if extension else "(no extension)"
        raise FileRejected(
            "'%s' cannot be attached.\nFiles of type %s are not allowed.\n\n"
            "Allowed: %s." % (original_name, shown, allowed_types_text())
        )

    try:
        size = os.path.getsize(path)
    except OSError as exc:
        raise FileRejected("The file could not be read: %s" % exc) from exc
    if size == 0:
        raise FileRejected("'%s' is empty (0 bytes)." % original_name)
    if size > MAX_BYTES:
        raise FileRejected(
            "'%s' is %s. The limit is %d MB per file."
            % (original_name, format_size(size), config.MAX_UPLOAD_MB)
        )

    mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    return {
        "original_name": original_name,
        "extension": extension,
        "mime_type": mime_type,
        "size_bytes": size,
    }


def store_file(path, upload_dir=None):

    info = validate_file(path)
    folder = str(upload_dir or config.UPLOAD_DIR)
    try:
        os.makedirs(folder, exist_ok=True)
        while True:
            stored_name = secrets.token_hex(16) + info["extension"]
            target = os.path.join(folder, stored_name)
            if not os.path.exists(target):
                break
        shutil.copyfile(str(path), target)
    except OSError as exc:
        raise FileRejected("The file could not be copied into the uploads folder: %s" % exc) from exc
    return {
        "stored_name": stored_name,
        "original_name": info["original_name"],
        "mime_type": info["mime_type"],
        "size_bytes": info["size_bytes"],
    }


def stored_path(stored_name, upload_dir=None):

    if (not stored_name or stored_name in (".", "..")
            or stored_name != os.path.basename(stored_name)
            or "/" in stored_name or "\\" in stored_name):
        raise FileRejected("Invalid stored file name.")
    return os.path.join(str(upload_dir or config.UPLOAD_DIR), stored_name)


def delete_stored_file(stored_name, upload_dir=None):

    path = stored_path(stored_name, upload_dir)
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise FileRejected("The stored file could not be deleted: %s" % exc) from exc


def open_with_system(path):

    path = str(path)
    if not os.path.isfile(path):
        raise FileRejected("The stored file is missing:\n%s" % path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as exc:
        raise FileRejected("The file could not be opened: %s" % exc) from exc


def pillow_available():

    try:
        import PIL  
        return True
    except ImportError:
        return False


def load_thumbnail(path, size=(96, 96)):

    try:
        from PIL import Image, ImageTk
    except ImportError:
        return None
    try:
        with Image.open(str(path)) as img:
            img = img.convert("RGB")
        img.thumbnail(size)
        return ImageTk.PhotoImage(img)
    except Exception:  
        return None
