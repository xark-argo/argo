from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session

from configs.settings import DB_SETTINGS

engine = create_engine(
    DB_SETTINGS["db_url"],
    pool_size=1,
    pool_recycle=3600,
    echo=False,
    max_overflow=10,
    echo_pool=True,
    connect_args={"timeout": 15},
)

if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA threads = SERIALIZED")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=True,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


Base = declarative_base()


def init():
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def with_session(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with session_scope() as session:
            return f(session, *args, **kwargs)

    return wrapper
