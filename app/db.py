"""Слой доступа к базе данных.

Поддерживаются два бэкенда:
  * PostgreSQL (основной, в Docker) — DATABASE_URL=postgresql://user:pass@host:5432/db
  * SQLite (для локальных тестов и CI unit-тестов) — DATABASE_URL=sqlite:///path.db
"""
import os
import sqlite3
from contextlib import contextmanager
from urllib.parse import urlparse

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS students (
        id {pk},
        full_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        group_name VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS disciplines (
        id {pk},
        title VARCHAR(255) UNIQUE NOT NULL,
        credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 10),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS grades (
        id {pk},
        student_id INTEGER NOT NULL REFERENCES students(id),
        discipline_id INTEGER NOT NULL REFERENCES disciplines(id),
        score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (student_id, discipline_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_students_group ON students (group_name)",
    "CREATE INDEX IF NOT EXISTS idx_grades_student ON grades (student_id)",
]


class Database:
    def __init__(self, url: str):
        self.url = url
        parsed = urlparse(url)
        self.kind = "sqlite" if parsed.scheme == "sqlite" else "postgres"
        if self.kind == "sqlite":
            path = url.replace("sqlite:///", "", 1)
            self.sqlite_path = path or ":memory:"
            self._mem_conn = None
            if self.sqlite_path == ":memory:":
                self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._mem_conn.row_factory = sqlite3.Row
                self._mem_conn.create_function(
                    "lower", 1, lambda v: v.lower() if isinstance(v, str) else v)

    # ------------------------------------------------------------------ utils
    def _connect(self):
        if self.kind == "sqlite":
            if self._mem_conn is not None:
                return self._mem_conn
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            # встроенный LOWER() в SQLite не понимает кириллицу — заменяем на Python-версию
            conn.create_function("lower", 1, lambda v: v.lower() if isinstance(v, str) else v)
            return conn
        import psycopg2  # импорт здесь: для SQLite-тестов драйвер не нужен
        import psycopg2.extras

        conn = psycopg2.connect(self.url, connect_timeout=3)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn

    def _sql(self, query: str) -> str:
        # В коде используется стиль %s; для SQLite заменяем на ?
        return query.replace("%s", "?") if self.kind == "sqlite" else query

    @contextmanager
    def transaction(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield Cursor(self, cur)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if self.kind == "postgres" or self._mem_conn is None:
                conn.close()

    def init_schema(self):
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if self.kind == "sqlite" else "SERIAL PRIMARY KEY"
        with self.transaction() as cur:
            for stmt in SCHEMA:
                cur.execute(stmt.format(pk=pk))

    def ping(self) -> bool:
        with self.transaction() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None


class Cursor:
    def __init__(self, db: Database, cur):
        self.db = db
        self.cur = cur

    def execute(self, query, params=()):
        self.cur.execute(self.db._sql(query), params)
        return self

    def insert(self, query, params=()):
        """INSERT с возвратом id новой записи."""
        if self.db.kind == "postgres":
            self.cur.execute(query + " RETURNING id", params)
            return self.cur.fetchone()["id"]
        self.cur.execute(self.db._sql(query), params)
        return self.cur.lastrowid

    def fetchone(self):
        row = self.cur.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(r) for r in self.cur.fetchall()]

    @property
    def rowcount(self):
        return self.cur.rowcount


def from_env() -> Database:
    return Database(os.environ.get("DATABASE_URL", "sqlite:///grades.db"))
