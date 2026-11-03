import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

UPLOAD_DIR = BASE_DIR / "uploads"

MAX_UPLOAD_MB = 25

DEFAULTS = {
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
    "DB_USER": "root",
    "DB_PASSWORD": "",
    "DB_NAME": "farm_garden_cultiva",
}


def read_env_file(path):

    values = {}
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return values  

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[name] = value
    return values


def load_config(env_path=ENV_FILE):
    settings = dict(DEFAULTS)
    settings.update(read_env_file(env_path))
    for name in DEFAULTS:
        if name in os.environ:
            settings[name] = os.environ[name]
    return settings


def _to_port(text):
    try:
        port = int(text)
        return port if 0 < port < 65536 else 3306
    except (TypeError, ValueError):
        return 3306


_settings = load_config()

DB_HOST = _settings["DB_HOST"]
DB_PORT = _to_port(_settings["DB_PORT"])
DB_USER = _settings["DB_USER"]
DB_PASSWORD = _settings["DB_PASSWORD"]
DB_NAME = _settings["DB_NAME"]
