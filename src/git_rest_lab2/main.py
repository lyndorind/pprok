
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from git_rest_lab2 import __version__
from git_rest_lab2.database import (
    get_connection,
    initialize_database,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Git REST Lab 2",
    version=__version__,
    lifespan=lifespan,
)


class RecordCreate(BaseModel):
    name: str
    value: int


class RecordResponse(RecordCreate):
    id: int


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Git REST Lab 2 service is running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello_user(name: str) -> dict[str, str]:
    return {"message": f"Hello, {name}!"}


@app.get("/about")
def about_service() -> dict[str, str]:
    return {
        "service": "Git REST Lab 2",
        "framework": "FastAPI",
    }


@app.get("/version")
def service_version() -> dict[str, str]:
    return {"version": __version__}


@app.post(
    "/records",
    response_model=RecordResponse,
    status_code=201,
)
def create_record(record: RecordCreate):
    with get_connection() as connection:
        result = connection.execute(
            """
            INSERT INTO records (name, value)
            VALUES (%s, %s)
            RETURNING id, name, value
            """,
            (record.name, record.value),
        )
        return result.fetchone()


@app.get(
    "/records",
    response_model=list[RecordResponse],
)
def list_records():
    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, name, value
            FROM records
            ORDER BY id
            """
        )
        return result.fetchall()


@app.get(
    "/records/{record_id}",
    response_model=RecordResponse,
)
def get_record(record_id: int):
    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT id, name, value
            FROM records
            WHERE id = %s
            """,
            (record_id,),
        )
        record = result.fetchone()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Record not found",
        )

    return record
