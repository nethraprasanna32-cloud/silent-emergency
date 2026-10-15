import os
from contextlib import contextmanager
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sed_admin:sed_local_dev@localhost:5432/sed")
DB_CONNECT_TIMEOUT = int(os.getenv("SED_DB_CONNECT_TIMEOUT", "5"))

@contextmanager
def connection(isolation_level="read committed"):
    with psycopg.connect(DATABASE_URL, autocommit=False, connect_timeout=DB_CONNECT_TIMEOUT) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL " + isolation_level.upper())
        yield conn
