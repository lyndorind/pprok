from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from git_rest_lab2.main import app

client = TestClient(app)


def make_connection(data):
    cursor = MagicMock()
    cursor.fetchone.return_value = data
    cursor.fetchall.return_value = data

    connection = MagicMock()
    connection.execute.return_value = cursor
    connection.__enter__.return_value = connection
    return connection


def test_create_record():
    record = {"id": 1, "name": "Laboratory 7", "value": 100}

    with patch(
        "git_rest_lab2.main.get_connection",
        return_value=make_connection(record),
    ):
        response = client.post(
            "/records",
            json={"name": "Laboratory 7", "value": 100},
        )

    assert response.status_code == 201
    assert response.json() == record


def test_list_records():
    records = [{"id": 1, "name": "Laboratory 7", "value": 100}]

    with patch(
        "git_rest_lab2.main.get_connection",
        return_value=make_connection(records),
    ):
        response = client.get("/records")

    assert response.status_code == 200
    assert response.json() == records


def test_get_record():
    record = {"id": 1, "name": "Laboratory 7", "value": 100}

    with patch(
        "git_rest_lab2.main.get_connection",
        return_value=make_connection(record),
    ):
        response = client.get("/records/1")

    assert response.status_code == 200
    assert response.json() == record


def test_record_not_found():
    with patch(
        "git_rest_lab2.main.get_connection",
        return_value=make_connection(None),
    ):
        response = client.get("/records/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Record not found"}
