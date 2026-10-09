"""Run behavioral SQL tests against an explicitly selected test database."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


SQL_DIR = Path(__file__).parent / "sql"


@pytest.fixture
def run_database_sql():
    database_url = os.environ.get("MEAL_PLAN_TEST_DB_URL")
    if not database_url:
        pytest.skip("set MEAL_PLAN_TEST_DB_URL to run real PostgreSQL tests")
    psql = shutil.which("psql") or "/opt/homebrew/opt/postgresql@18/bin/psql"

    def run(filename):
        # Every case uses a transaction and generated IDs, and leaves no rows.
        sql = "begin;\n" + (SQL_DIR / "helpers.sql").read_text()
        case_sql = (SQL_DIR / filename).read_text()
        # Reuse the real deployment SQL inside the enclosing test transaction.
        auth_module = (SQL_DIR.parents[1] / "auth.sql").read_text()
        auth_module = auth_module.split("begin;\n", 1)[1].rsplit("commit;", 1)[0]
        sql += case_sql.replace("/* APPLY_AUTH_MODULE */", auth_module)
        sql += "\nset constraints all immediate;\nrollback;\n"
        result = subprocess.run(
            [psql, "-X", "--no-password", "-v", "ON_ERROR_STOP=1", "-d", database_url],
            input=sql, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr

    return run
