import os
from contextlib import contextmanager
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sed_admin:sed_local_dev@localhost:5432/sed")

@contextmanager
def connection(isolation_level="read committed"):
    with psycopg.connect(DATABASE_URL, autocommit=False) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL " + isolation_level.upper())
        yield conn
