
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def get_db_password() -> str:
    password_file = os.getenv("DB_PASSWORD_FILE")

    if password_file:
        return Path(password_file).read_text(encoding="utf-8").strip()

    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "Database password is not configured. "
            "Set DB_PASSWORD or DB_PASSWORD_FILE."
        )

    return password


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "lab7"),
        user=os.getenv("DB_USER", "labuser"),
        password=get_db_password(),
        row_factory=dict_row,
    )


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER NOT NULL
            )
            """
        )
