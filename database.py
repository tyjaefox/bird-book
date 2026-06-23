#Database helpers for the app.
#No external required.


import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "maintenance.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection():
    #return a connection with row access by column name and FKs enabled
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema():
    #recreate all tables. ***erases existing data.
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        ddl = f.read()
    conn = get_connection()
    conn.executescript(ddl)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_schema()
    print(f"Schema initialized at {DB_PATH}")
