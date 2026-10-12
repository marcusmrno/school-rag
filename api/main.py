import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from core.db import connect

app = FastAPI(title="CourseLens")


@app.get("/health")
def health():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
    except psycopg.OperationalError:
        return JSONResponse({"status": "db unreachable"}, status_code=503)
    return {"status": "ok"}
