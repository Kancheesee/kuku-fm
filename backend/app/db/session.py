import os
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool

Base = declarative_base()

_engine = None
_SessionFactory = None


def get_database_url() -> Optional[str]:
    """Retrieve DATABASE_URL from environment.

    Normalizes 'postgres://' to 'postgresql://' for SQLAlchemy 2.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def get_engine():
    global _engine
    if _engine is None:
        db_url = get_database_url()
        if not db_url:
            return None
        # Serverless-friendly config for Neon PostgreSQL:
        # NullPool avoids exhausting connection limits in serverless lambdas/edge.
        _engine = create_engine(
            db_url,
            poolclass=NullPool,
            echo=False,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def get_session_factory():
    global _SessionFactory
    if _SessionFactory is None:
        engine = get_engine()
        if engine is None:
            return None
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionFactory


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI request-scoped dependency yielding a short-lived database session.

    Safe when no database is configured.
    """
    factory = get_session_factory()
    if factory is None:
        yield None
        return
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection() -> bool:
    """Non-blocking check if database is available and responding."""
    try:
        engine = get_engine()
        if engine is None:
            return False
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

