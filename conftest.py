"""Root pytest options: choose the database for tests and evaluation workers."""
import os


def pytest_addoption(parser):
    parser.addoption("--db", choices=["sqlite", "postgres"], default=os.getenv("TEST_DB", "sqlite"),
                     help="Database for tests and evaluation workers (default sqlite; postgres uses TEST_POSTGRES_URL).")


def pytest_configure(config):
    os.environ["EVAL_DB"] = config.getoption("--db")
