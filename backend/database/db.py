import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps

import pymysql
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.session import Session

from configs.settings import DB_SETTINGS

# Configure engine based on database type
db_type = DB_SETTINGS.get("db_type", "mysql")

if db_type == "mysql":
    engine = create_engine(
        DB_SETTINGS["db_url"],
        pool_size=10,
        pool_recycle=3600,
        echo=False,
        max_overflow=20,
        echo_pool=False,
        connect_args={
            "charset": "utf8mb4",
            "connect_timeout": 60,
            "read_timeout": 60,
            "write_timeout": 60,
        },
    )
else:
    # SQLite configuration
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


def ensure_database_exists():
    """Ensure that the database exists, create it if it doesn't.
    This function only works for MySQL databases.
    """
    db_type = DB_SETTINGS.get("db_type", "mysql")
    
    if db_type != "mysql":
        # For SQLite, the database file is created automatically
        logging.info(f"Database type is {db_type}, skipping database creation check.")
        return
    
    # Extract connection parameters from DB_SETTINGS with defaults
    host = DB_SETTINGS.get("db_host", "localhost")
    port = DB_SETTINGS.get("db_port", 3306)
    username = DB_SETTINGS.get("db_user", "root")
    password = DB_SETTINGS.get("db_password", "")
    database_name = DB_SETTINGS.get("db_name", "argo")
    
    try:
        # Connect to MySQL server without specifying a database
        connection = pymysql.connect(
            host=host,
            port=port,
            user=username,
            password=password,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # Check if database exists
            cursor.execute("SHOW DATABASES LIKE %s", (database_name,))
            result = cursor.fetchone()
            
            if not result:
                # Database doesn't exist, create it
                logging.info(f"Database '{database_name}' does not exist. Creating it...")
                cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                logging.info(f"Database '{database_name}' created successfully.")
            else:
                logging.info(f"Database '{database_name}' already exists.")
        
        connection.close()
        
    except pymysql.Error as e:
        logging.error(f"Error connecting to MySQL server: {e}")
        raise RuntimeError(f"Failed to ensure database exists: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while ensuring database exists: {e}")
        raise RuntimeError(f"Failed to ensure database exists: {e}")


def init():
    """Initialize the database: ensure it exists and create all tables."""
    ensure_database_exists()
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
