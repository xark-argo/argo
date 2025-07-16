import logging
import os

from alembic import command
from alembic.config import Config
from utils.path import app_path

directory = app_path("alembic")
alembic_cfg = Config(os.path.join(directory, "alembic.ini"))
alembic_cfg.set_main_option("script_location", str(directory))


def run_online_migrations():
    try:
        command.upgrade(alembic_cfg, "head")
        logging.info("Database migration success.")
    except Exception as e:
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
