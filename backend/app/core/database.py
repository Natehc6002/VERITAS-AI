"""SQLAlchemy engine, session management and database initialisation."""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(settings.database_url, connect_args=connect_args, future=True)


engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a scoped session and always closes it."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create database tables if they do not exist yet and run light migrations."""
    from app import models  # noqa: F401  (import registers models on Base)

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations(engine)


def _run_lightweight_migrations(engine: Engine) -> None:
    """Add ownership columns to pre-existing SQLite databases without rebuilding them."""
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        columns = {
            row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()
        }
        for column in ("owner_id", "investigation_id"):
            if column not in columns:
                conn.exec_driver_sql(f"ALTER TABLE documents ADD COLUMN {column} VARCHAR(36)")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_documents_owner_id ON documents (owner_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_documents_investigation_id "
            "ON documents (investigation_id)"
        )
