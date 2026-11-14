"""Prompt history in SQLite, with FTS5 search when the build supports it."""
import json
import sqlite3
from datetime import datetime, timezone

from . import paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created TEXT NOT NULL,
  source_lang TEXT NOT NULL DEFAULT '',
  original TEXT NOT NULL,
  english TEXT NOT NULL DEFAULT '',
  improved TEXT NOT NULL,
  family TEXT NOT NULL,
  version TEXT NOT NULL,
  target_label TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'other',
  subtype TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  favorite INTEGER NOT NULL DEFAULT 0,
  backend TEXT NOT NULL DEFAULT '',
  guide TEXT NOT NULL DEFAULT '',
  changes TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS prompts_created ON prompts(created DESC);
CREATE INDEX IF NOT EXISTS prompts_category ON prompts(category);
CREATE INDEX IF NOT EXISTS prompts_family ON prompts(family);
"""

FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS prompts_fts USING fts5(
  title, tags, original, english, improved, content='prompts', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS prompts_ai AFTER INSERT ON prompts BEGIN
  INSERT INTO prompts_fts(rowid, title, tags, original, english, improved)
  VALUES (new.id, new.title, new.tags, new.original, new.english, new.improved);
END;
CREATE TRIGGER IF NOT EXISTS prompts_ad AFTER DELETE ON prompts BEGIN
  INSERT INTO prompts_fts(prompts_fts, rowid, title, tags, original, english, improved)
  VALUES ('delete', old.id, old.title, old.tags, old.original, old.english, old.improved);
END;
"""

LIST_COLUMNS = (
    "p.id, p.created, p.source_lang, p.family, p.version, p.target_label, p.category, "
    "p.subtype, p.title, p.tags, p.favorite, p.improved"
)


class Store:
    def __init__(self, path=None, fts=True):
        self.path = path or paths.history_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.fts = False
        if fts:
            try:
                self.db.executescript(FTS)
                self.fts = True
            except sqlite3.OperationalError:
                self.fts = False
        self.db.commit()

    def close(self):
        self.db.close()

    def add(self, entry):
        row = {
            "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_lang": entry.get("source_lang", ""),
            "original": entry["original"],
            "english": entry.get("english", ""),
            "improved": entry["improved"],
            "family": entry["family"],
            "version": entry["version"],
            "target_label": entry.get("target_label", ""),
            "category": entry.get("category", "other"),
            "subtype": entry.get("subtype", ""),
            "title": entry.get("title", ""),
            "tags": ",".join(entry.get("tags", [])),
            "backend": entry.get("backend", ""),
            "guide": entry.get("guide", ""),
            "changes": json.dumps(entry.get("changes", []), ensure_ascii=False),
        }
        cols = ", ".join(row)
        marks = ", ".join(f":{k}" for k in row)
        cur = self.db.execute(f"INSERT INTO prompts ({cols}) VALUES ({marks})", row)
        self.db.commit()
        return cur.lastrowid

    @staticmethod
    def _fts_query(text):
        # Quote each term so user input can't use FTS operators; prefix-match the last.
        terms = [t.replace('"', '""') for t in text.split() if t.strip()]
        if not terms:
            return ""
        quoted = [f'"{t}"' for t in terms]
        quoted[-1] += "*"
        return " ".join(quoted)

    def list(self, query="", category="", family="", favorite=False, limit=200):
        where, args = [], []
        if category:
            where.append("p.category = ?")
            args.append(category)
        if family:
            where.append("p.family = ?")
            args.append(family)
        if favorite:
            where.append("p.favorite = 1")
        query = (query or "").strip()
        source = "prompts p"
        if query and self.fts:
            source = "prompts p JOIN prompts_fts f ON f.rowid = p.id"
            where.append("prompts_fts MATCH ?")
            args.append(self._fts_query(query))
        elif query:
            like = f"%{query.replace('%', '').replace('_', '')}%"
            where.append("(p.title LIKE ? OR p.tags LIKE ? OR p.original LIKE ? OR p.improved LIKE ?)")
            args += [like] * 4
        sql = f"SELECT {LIST_COLUMNS} FROM {source}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY p.favorite DESC, p.created DESC, p.id DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        return [self._row(r) for r in self.db.execute(sql, args)]

    def get(self, entry_id):
        row = self.db.execute("SELECT * FROM prompts WHERE id = ?", (int(entry_id),)).fetchone()
        return self._row(row) if row else None

    def delete(self, entry_id):
        cur = self.db.execute("DELETE FROM prompts WHERE id = ?", (int(entry_id),))
        self.db.commit()
        return cur.rowcount > 0

    def set_favorite(self, entry_id, value=None):
        if value is None:
            self.db.execute("UPDATE prompts SET favorite = 1 - favorite WHERE id = ?", (int(entry_id),))
        else:
            self.db.execute("UPDATE prompts SET favorite = ? WHERE id = ?", (1 if value else 0, int(entry_id)))
        self.db.commit()
        row = self.db.execute("SELECT favorite FROM prompts WHERE id = ?", (int(entry_id),)).fetchone()
        return None if row is None else bool(row[0])

    def stats(self):
        cats = {r[0]: r[1] for r in self.db.execute("SELECT category, COUNT(*) FROM prompts GROUP BY category")}
        fams = {r[0]: r[1] for r in self.db.execute("SELECT family, COUNT(*) FROM prompts GROUP BY family")}
        total = self.db.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
        return {"total": total, "categories": cats, "families": fams}

    @staticmethod
    def _row(row):
        d = dict(row)
        d["tags"] = [t for t in d.get("tags", "").split(",") if t]
        d["favorite"] = bool(d.get("favorite"))
        if "changes" in d:
            try:
                d["changes"] = json.loads(d["changes"])
            except ValueError:
                d["changes"] = []
        return d
