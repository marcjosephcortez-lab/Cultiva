

import db
import translations
from ui.record_tab import RecordTab

tr = translations.tr


class NotesTab(RecordTab):
    KIND = "note"
    NOUN = "note"
    NOUN_PLURAL = "notes"

    def heading_text(self):
        return tr("tab_notes")

    def columns(self):
        return [("title", "Title", 250, "w"),
                ("linked", "%s / %s" % (tr("plot"), tr("crop")), 160, "w"),
                ("files", "Files", 50, "center"), ("added", "Added", 90, "center")]

    def row_values(self, row):
        linked = " / ".join(x for x in (row["plot_name"], row["crop_name"]) if x)
        return (row["title"], linked, row["files"] or "", row["created_at"].strftime("%Y-%m-%d"))

    def meta_text(self, row):
        parts = ["Added " + row["created_at"].strftime("%d %b %Y")]
        links = self.links_text(row)
        if links:
            parts.append(links)
        return " | ".join(parts)

    def load_rows(self, search):
        sql = ("SELECT n.id, n.title, n.body, n.plot_id, n.crop_id, n.created_at, "
               "p.name AS plot_name, c.name AS crop_name, "
               "(SELECT COUNT(*) FROM attachments a WHERE a.note_id = n.id) AS files "
               "FROM notes n "
               "LEFT JOIN plots p ON p.id = n.plot_id "
               "LEFT JOIN crops c ON c.id = n.crop_id")
        params = None
        if search:
            like = db.like_pattern(search)
            sql += " WHERE (n.title LIKE %s OR n.body LIKE %s OR p.name LIKE %s OR c.name LIKE %s)"
            params = (like,) * 4
        sql += " ORDER BY n.created_at DESC, n.id DESC"
        return db.query(sql, params)
