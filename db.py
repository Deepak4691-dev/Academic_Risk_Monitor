"""Oracle FreeSQL connection helper (python-oracledb, Thin mode)."""
import os
import oracledb
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return oracledb.connect(
        user=os.getenv("ORACLE_USER"),
        password=os.getenv("ORACLE_PASSWORD"),
        dsn=os.getenv("ORACLE_DSN"),
    )


def query(sql, params=None):
    """Run a SELECT and return a list of dicts with lower-case keys."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [c[0].lower() for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def execute(sql, params=None):
    """Run an INSERT/UPDATE/DELETE and commit."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
        conn.commit()


def call_procedure(name):
    """Call a stored procedure with no arguments and commit."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.callproc(name)
        conn.commit()
