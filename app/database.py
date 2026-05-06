import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from .models import *  # Ensure all models are loaded for table creation

database_url = os.getenv("DATABASE_URL", "sqlite:///./pawsledger.db")

# SQLite-specific configuration for multi-instance support
connect_args = {}
engine_kwargs = {"echo": False}

if database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        # Timeout waiting for the write lock (seconds)
        # Default is 5s — matches PRAGMA busy_timeout for multi-instance
        "timeout": 5,
    }
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)


def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Configure SQLite pragmas for concurrent access."""
    cursor = dbapi_conn.cursor()
    # WAL mode: allows concurrent readers while one writer is active
    cursor.execute("PRAGMA journal_mode=WAL")
    # Synchronous NORMAL: good balance of safety and performance with WAL
    cursor.execute("PRAGMA synchronous=NORMAL")
    # Busy timeout: wait up to 5s for locks instead of failing immediately
    cursor.execute("PRAGMA busy_timeout=5000")
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Apply pragmas on every new connection
if database_url.startswith("sqlite"):
    event.listen(engine, "connect", _set_sqlite_pragma)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
