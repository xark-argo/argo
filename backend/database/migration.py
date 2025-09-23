import logging
import os

from alembic import command
from alembic.config import Config
from utils.path import app_path
from database.db import ensure_database_exists

directory = app_path("alembic")
alembic_cfg = Config(os.path.join(directory, "alembic.ini"))
alembic_cfg.set_main_option("script_location", str(directory))


def run_online_migrations():
    """Run database migrations after ensuring the database exists."""
    try:
        # Ensure database exists before running migrations
        ensure_database_exists()
        
        # Check current revision first to avoid conflicts
        try:
            current_rev = command.current(alembic_cfg)
            logging.info(f"Current database revision: {current_rev}")
            
            # If we have a revision, try to upgrade
            if current_rev:
                try:
                    command.upgrade(alembic_cfg, "head")
                    logging.info("Database migration success.")
                    return
                except Exception as upgrade_error:
                    error_msg = str(upgrade_error).lower()
                    if "already exists" in error_msg or "1050" in error_msg:
                        logging.info("Tables already exist, database is already up to date")
                        return
                    else:
                        raise upgrade_error
                
        except Exception as rev_error:
            logging.info(f"Unable to get current revision (likely first run): {rev_error}")
        
        # Try to run upgrade for first time setup
        try:
            command.upgrade(alembic_cfg, "head")
            logging.info("Database migration success.")
        except Exception as upgrade_error:
            error_msg = str(upgrade_error).lower()
            if "already exists" in error_msg or "1050" in error_msg:
                logging.info("Tables already exist, marking database as up to date")
                # Mark the database as being at the latest revision
                command.stamp(alembic_cfg, "head")
                logging.info("Database marked as up to date.")
            else:
                raise upgrade_error
                
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "1050" in error_msg:
            logging.info("Tables already exist, database setup complete")
            try:
                command.stamp(alembic_cfg, "head")
                logging.info("Database marked as up to date.")
            except Exception as stamp_error:
                logging.warning(f"Could not stamp database: {stamp_error}")
        else:
            logging.exception("Database migration failed")
            raise RuntimeError(e)


def gen_migration_script():
    try:
        command.revision(alembic_cfg, autogenerate=True)
        logging.info("Script generate success.")
    except Exception as e:
        logging.exception("Script generate failed")
        raise RuntimeError(e)


if __name__ == "__main__":
    import models  # noqa: F401

    logging.basicConfig(level=logging.INFO)
    gen_migration_script()
