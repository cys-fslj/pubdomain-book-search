import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books.db")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = connect()
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS books ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  author TEXT NOT NULL DEFAULT '',"
        "  source_name TEXT NOT NULL,"
        "  source_url TEXT NOT NULL UNIQUE"
        ");"
        "CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);"
        "CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);"
        "CREATE INDEX IF NOT EXISTS idx_books_source_name ON books(source_name);"
    )
    conn.commit()
    conn.close()


def upsert_book(title, author, source_name, source_url):
    conn = connect()
    conn.execute(
        "INSERT INTO books (title, author, source_name, source_url) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(source_url) DO UPDATE SET "
        "title = excluded.title, author = excluded.author, source_name = excluded.source_name",
        (title, author, source_name, source_url),
    )
    conn.commit()
    conn.close()


def stats():
    conn = connect()
    rows = conn.execute("SELECT source_name, COUNT(*) AS n FROM books GROUP BY source_name").fetchall()
    conn.close()
    return {r["source_name"]: r["n"] for r in rows}
