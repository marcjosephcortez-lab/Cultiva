

from contextlib import contextmanager

import mysql.connector
import re

import config


class DBError(Exception):


    def __init__(self, message, technical=""):
        super().__init__(message)
        self.message = message
        self.technical = technical  


class DBConnectionError(DBError):
    pass


class DBInUseError(DBError):
    pass


class DBDuplicateError(DBError):
    pass


ERR_ACCESS_DENIED = 1045
ERR_UNKNOWN_DB = 1049
ERR_NO_SUCH_TABLE = 1146       
ERR_DUPLICATE = 1062
ERR_ROW_IS_REFERENCED = 1451   
ERR_NO_REFERENCED_ROW = 1452   
ERR_CANT_CONNECT = (2002, 2003, 2006, 2013)


def _connection_help(detail):

    return (
        "Could not connect to the MySQL database.\n\n"
        "What to try:\n"
        "1. Open the XAMPP Control Panel and click Start next to MySQL.\n"
        "2. Open the .env file in the project folder and check DB_HOST, "
        "DB_PORT, DB_USER, DB_PASSWORD and DB_NAME.\n"
        "3. If the database or tables are missing, create them with:\n"
        "      python setup_db.py\n\n"
        "Technical detail: " + str(detail)
    )


def translate_error(exc):

    if isinstance(exc, DBError):
        return exc

    errno = getattr(exc, "errno", None)
    detail = str(exc)

    if errno == ERR_UNKNOWN_DB:
        return DBConnectionError(
            "The database '%s' does not exist yet.\n\n"
            "Create it by running:\n    python setup_db.py" % config.DB_NAME,
            detail,
        )
    if errno == ERR_NO_SUCH_TABLE:
        return DBConnectionError(
            "The database exists, but its tables are missing.\n\n"
            "Create them by running:\n    python setup_db.py",
            detail,
        )
    if errno == ERR_ACCESS_DENIED:
        return DBConnectionError(
            "MySQL refused the user name or password.\n\n"
            "Check DB_USER and DB_PASSWORD in the .env file. "
            "(XAMPP default: user root, empty password.)\n\n"
            "Technical detail: " + detail,
            detail,
        )
    if errno in ERR_CANT_CONNECT or isinstance(exc, OSError):
        return DBConnectionError(_connection_help(detail), detail)
    if errno == ERR_ROW_IS_REFERENCED:
        return DBInUseError(
            "This item cannot be deleted because other records still use it.\n"
            "Remove or change those records first, then try again.",
            detail,
        )
    if errno == ERR_NO_REFERENCED_ROW:
        return DBError(
            "The linked item no longer exists. Please refresh the list "
            "and choose again.",
            detail,
        )
    if errno == ERR_DUPLICATE:
        return DBDuplicateError(
            "That value already exists. Please use a different one.", detail
        )
    return DBError("A database error happened:\n" + detail, detail)


_connection = None
_active_mode = "farm"
_mode_scope_enabled = True
MODE_TABLES = {
    "workers", "plots", "crops", "plantings", "tasks", "shifts",
    "attendance", "journal_entries", "notes", "attachments",
    "resources", "resource_links",
}


def set_mode_scope_enabled(enabled):
    global _mode_scope_enabled
    _mode_scope_enabled = bool(enabled)


def set_active_mode(mode):
    global _active_mode
    if mode not in ("farm", "garden"):
        raise ValueError("Unknown Cultiva mode: %r" % (mode,))
    _active_mode = mode


def _scope_sql(sql, params):
    """Apply the active mode to ordinary application SQL.

    DDL and metadata queries are untouched. Inserts receive the active mode_id;
    SELECT/UPDATE/DELETE statements are constrained to the active mode.
    """
    if not _mode_scope_enabled or not isinstance(sql, str):
        return sql, params
    text = sql.strip()
    values = list(params or ())
    if not text:
        return sql, params

    # INSERT INTO <scoped table> (columns...) VALUES (...)
    match = re.match(r"(?is)^(INSERT\s+(?:IGNORE\s+)?INTO\s+)(`?)([a-z_]+)\2\s*\((.*?)\)\s*(VALUES\s*)(.*)$", text)
    if match and match.group(3).lower() in MODE_TABLES:
        table, cols, tail = match.group(3).lower(), match.group(4), match.group(6)
        if not re.search(r"(?i)(^|,)\s*mode_id\s*(,|$)", cols):
            # Keep ON DUPLICATE KEY UPDATE outside the VALUES tuple parser.
            duplicate_match = re.search(r"(?is)\s+ON\s+DUPLICATE\s+KEY\s+UPDATE\b", tail)
            values_part = tail[:duplicate_match.start()] if duplicate_match else tail
            suffix = tail[duplicate_match.start():] if duplicate_match else ""
            if not re.match(r"(?is)^\s*\(", values_part):
                raise DBError("This insert form is not supported by mode-aware storage.")
            cols = cols.rstrip() + ", mode_id"
            values_part = re.sub(r"\)(\s*,\s*\()", r", %s)\1", values_part)
            pos = values_part.rfind(")")
            if pos < 0:
                raise DBError("Could not safely add the active mode to this insert.")
            values_part = values_part[:pos] + ", %s" + values_part[pos:]
            mode_value = 1 if _active_mode == "farm" else 2
            if values and isinstance(values[0], (tuple, list)):
                values = [tuple(row) + (mode_value,) for row in values]
            else:
                original_placeholders = sql.count("%s")
                tuple_count = len(re.findall(r"\)\s*,\s*\(", values_part)) + 1
                if tuple_count > 1 and original_placeholders % tuple_count == 0:
                    per_row = original_placeholders // tuple_count
                    expanded = []
                    for offset in range(0, len(values), per_row):
                        expanded.extend(values[offset:offset + per_row])
                        expanded.append(mode_value)
                    values = expanded
                else:
                    values.append(mode_value)
            tail = values_part + suffix
            text = match.group(1) + match.group(2) + table + match.group(2) + " (" + cols + ") " + match.group(5) + tail
        return text, tuple(values) if not (values and isinstance(values[0], (tuple, list))) else values

    # Scope EVERY mode-owned table reference in SELECT statements.  The old
    # implementation constrained only one FROM reference, allowing LEFT JOINs
    # and multi-table screens to leak rows from the other mode.  Derived tables
    # keep the filter local to each source and preserve LEFT JOIN semantics.
    if re.match(r"(?is)^SELECT\b", text):
        mode_value = 1 if _active_mode == "farm" else 2
        reserved = {
            "where", "join", "left", "right", "inner", "outer", "cross",
            "on", "using", "group", "order", "limit", "having", "union",
            "for", "lock", "straight_join", "use", "force", "ignore",
        }
        table_ref = re.compile(
            r"(?is)\b(FROM|JOIN)\s+(`?)([a-z_][a-z0-9_]*)\2"
            r"(?:\s+(?:AS\s+)?([a-z_][a-z0-9_]*))?"
        )

        def scope_table(match):
            table = match.group(3).lower()
            if table not in MODE_TABLES:
                return match.group(0)
            alias = match.group(4)
            trailing_keyword = ""
            if alias and alias.lower() in reserved:
                trailing_keyword = " " + alias
                alias = None
            source = "(SELECT * FROM `" + table + "` WHERE mode_id = " + str(mode_value) + ")"
            if alias:
                source += " " + alias
            else:
                source += " AS `" + table + "`"
            return match.group(1) + " " + source + trailing_keyword

        text = table_ref.sub(scope_table, text)
        return text, tuple(values)

    # UPDATE / DELETE of a scoped table.
    m = re.match(r"(?is)^(UPDATE|DELETE\s+FROM)\s+(`?)([a-z_]+)\2(?:\s+(?:AS\s+)?([a-z_]+))?\b", text)
    if m and m.group(3).lower() in MODE_TABLES:
        table = m.group(3).lower()
        alias = m.group(4) if m.group(4) and m.group(4).lower() not in {"set", "where", "order", "limit"} else table
        condition = alias + ".mode_id = %s"
        where = re.search(r"(?i)\bWHERE\b", text)
        if where:
            text = text[:where.end()] + " " + condition + " AND " + text[where.end():]
        else:
            text += " WHERE " + condition
        if m.group(1).upper().startswith("UPDATE"):
            where = re.search(r"(?i)\bWHERE\b", text)
            insert_at = text[:where.start()].count("%s") if where else 0
        else:
            insert_at = 0
        values.insert(insert_at, 1 if _active_mode == "farm" else 2)
        return text, tuple(values)
    return sql, params



def connect(with_database=True):

    options = dict(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=True,       
        connection_timeout=5,  
    )
    if with_database:
        options["database"] = config.DB_NAME
    try:
        return mysql.connector.connect(**options)
    except (mysql.connector.Error, OSError) as exc:
        raise translate_error(exc) from exc


def get_connection():

    global _connection
    if _connection is not None:
        try:
            if _connection.is_connected():
                return _connection
        except mysql.connector.Error:
            pass
        _connection = None
    _connection = connect(with_database=True)
    return _connection


def close():

    global _connection
    if _connection is not None:
        try:
            _connection.close()
        except mysql.connector.Error:
            pass
        _connection = None


def check_connection():

    get_connection()


def _run(sql, params, fetch, many=False):

    sql, params = _scope_sql(sql, params)
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        if many:
            cursor.executemany(sql, params)
        else:
            cursor.execute(sql, params)
        if fetch:
            return cursor.fetchall()
        return cursor.lastrowid
    except (mysql.connector.Error, OSError) as exc:
        raise translate_error(exc) from exc
    finally:
        cursor.close()


def like_pattern(text):

    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return "%" + escaped + "%"


def query(sql, params=None):

    return _run(sql, params, fetch=True)


def query_one(sql, params=None):

    rows = _run(sql, params, fetch=True)
    return rows[0] if rows else None


def execute(sql, params=None):

    return _run(sql, params, fetch=False)


def execute_many(sql, rows):

    return _run(sql, rows, fetch=False, many=True)


@contextmanager
def transaction():

    connection = get_connection()
    connection.start_transaction()
    try:
        yield
        connection.commit()
    except Exception:
        try:
            connection.rollback()
        except mysql.connector.Error:
            pass
        raise
