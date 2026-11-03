"""Offline regression checks for Cultiva's mode-aware SQL boundary."""
import ast
import pathlib
import re
import sys
import types

# The SQL rewriter has no need to connect to MySQL for these unit tests.
mysql = types.ModuleType("mysql")
connector = types.ModuleType("mysql.connector")
connector.Error = Exception
mysql.connector = connector
sys.modules.setdefault("mysql", mysql)
sys.modules.setdefault("mysql.connector", connector)

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import db


def test_select_scopes_every_join(mode, mode_id):
    sql = (
        "SELECT t.id, p.name, w.name AS worker_name "
        "FROM tasks t LEFT JOIN plots p ON p.id=t.plot_id "
        "LEFT JOIN workers w ON w.id=t.worker_id WHERE t.done=%s"
    )
    actual, params = db._scope_sql(sql, (0,))
    assert actual.count("WHERE mode_id = %s".replace("%s", str(mode_id))) == 3, actual
    assert "LEFT JOIN (SELECT * FROM `plots` WHERE mode_id = %d) p" % mode_id in actual
    assert "LEFT JOIN (SELECT * FROM `workers` WHERE mode_id = %d) w" % mode_id in actual
    assert params == (0,)


def test_single_table_select_keeps_where(mode_id):
    actual, params = db._scope_sql("SELECT * FROM tasks WHERE id=%s", (12,))
    assert "WHERE mode_id = %d" % mode_id in actual
    assert "WHERE id=%s" in actual
    assert params == (12,)


def test_writes_are_scoped(mode_id):
    actual, params = db._scope_sql("UPDATE tasks SET done=%s WHERE id=%s", (1, 9))
    assert "tasks.mode_id = %s" in actual
    assert params == (1, mode_id, 9)
    actual, params = db._scope_sql("DELETE FROM attendance WHERE id=%s", (3,))
    assert "attendance.mode_id = %s" in actual
    assert params == (mode_id, 3)


def test_inserts_receive_active_mode(mode_id):
    actual, params = db._scope_sql(
        "INSERT INTO crops (name,color) VALUES (%s,%s)", ("Tomato", "#fff")
    )
    assert "(name,color, mode_id)" in actual
    assert params == ("Tomato", "#fff", mode_id)
    actual, params = db._scope_sql(
        "INSERT IGNORE INTO resource_links (resource_id,module_key,record_id) VALUES (%s,%s,%s)",
        (4, "notes", 7),
    )
    assert "mode_id" in actual
    assert params == (4, "notes", 7, mode_id)
    actual, params = db._scope_sql(
        "INSERT INTO attendance (worker_id,att_date) VALUES (%s,%s),(%s,%s)",
        (1, "2026-11-03", 2, "2026-11-04"),
    )
    assert params == (1, "2026-11-03", mode_id, 2, "2026-11-04", mode_id)


def test_all_literal_selects_are_scoped(mode_id):
    mode_tables = set(db.MODE_TABLES)
    for path in (ROOT / "src").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            sql = node.value.strip()
            if not re.match(r"(?is)^SELECT\b", sql):
                continue
            refs = re.findall(
                r"(?i)\b(?:FROM|JOIN)\s+`?([a-z_][a-z0-9_]*)`?", sql
            )
            scoped_refs = [name.lower() for name in refs if name.lower() in mode_tables]
            if not scoped_refs:
                continue
            rewritten, _ = db._scope_sql(sql, ())
            for table in scoped_refs:
                expected = "(SELECT * FROM `%s` WHERE mode_id = %d)" % (table, mode_id)
                assert expected in rewritten, (path, table, sql, rewritten)


def main():
    for mode, mode_id in (("farm", 1), ("garden", 2)):
        db.set_active_mode(mode)
        test_select_scopes_every_join(mode, mode_id)
        test_single_table_select_keeps_where(mode_id)
        test_writes_are_scoped(mode_id)
        test_inserts_receive_active_mode(mode_id)
        test_all_literal_selects_are_scoped(mode_id)
    print("mode-scoping regression checks passed for Farm and Garden")


if __name__ == "__main__":
    main()
