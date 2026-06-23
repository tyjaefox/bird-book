"""Database helpers for the Aviation Maintenance Analyzer.

Thin wrapper around the standard-library sqlite3 module so the rest of the app
never has to repeat connection boilerplate. No third-party ORM required.
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "maintenance.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection():
    """Return a connection with row access by column name and FKs enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema():
    """(Re)create all tables from schema.sql. Destroys existing data."""
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        ddl = f.read()
    conn = get_connection()
    conn.executescript(ddl)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_schema()
    print(f"Schema initialized at {DB_PATH}")
