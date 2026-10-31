from unittest.mock import MagicMock, patch

import pytest

from git_rest_lab2.database import (
    get_connection,
    get_db_password,
    initialize_database,
)


def test_password_from_environment(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "testpassword")

    assert get_db_password() == "testpassword"


def test_password_from_file(monkeypatch, tmp_path):
    password_file = tmp_path / "password.txt"
    password_file.write_text("secret123\n", encoding="utf-8")

    monkeypatch.setenv("DB_PASSWORD_FILE", str(password_file))

    assert get_db_password() == "secret123"


def test_missing_password(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("DB_PASSWORD", raising=False)

    with pytest.raises(RuntimeError):
        get_db_password()


def test_connection(monkeypatch):
    monkeypatch.delenv("DB_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("DB_PASSWORD", "testpassword")
    monkeypatch.setenv("DB_HOST", "localhost")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "lab7")
    monkeypatch.setenv("DB_USER", "labuser")

    with patch("git_rest_lab2.database.psycopg.connect") as connect:
        get_connection()

    connect.assert_called_once()
    assert connect.call_args.kwargs["dbname"] == "lab7"
    assert connect.call_args.kwargs["password"] == "testpassword"


def test_initialize_database():
    connection = MagicMock()
    connection.__enter__.return_value = connection

    with patch(
        "git_rest_lab2.database.get_connection",
        return_value=connection,
    ):
        initialize_database()

    sql = connection.execute.call_args.args[0]
    assert "CREATE TABLE IF NOT EXISTS records" in sql
