# PLACEHOLDER : à remplacer par le vrai backend de Raphael.
import os
import psycopg
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health")
def health():
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as conn:
            conn.execute("SELECT 1")
        return {"backend": "ok", "db": "ok"}
    except Exception as e:
        return {"backend": "ok", "db": f"erreur : {e}"}
