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
    """Create database tables if they do not exist yet."""
    from app import models  # noqa: F401  (import registers models on Base)

    Base.metadata.create_all(bind=engine)
