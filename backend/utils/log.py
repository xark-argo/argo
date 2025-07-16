import logging
import os.path
import traceback

from configs.env import ARGO_STORAGE_PATH
from core.tracking.client import (
    USE_ARGO_TRACKING,
    ExceptionTrackingPayload,
    argo_tracking,
)

log_fmt = (
    "%(levelname)s %(asctime)s.%(msecs)03d [%(process)d-%(threadName)s] "
    "(%(funcName)s@%(filename)s:%(lineno)03d) %(message)s"
)
date_fmt = "%Y-%m-%d %H:%M:%S"
app_log_path = os.path.join(ARGO_STORAGE_PATH, "app.log")
logging.basicConfig(
    format=log_fmt,
    datefmt=date_fmt,
    level=logging.INFO,
    handlers=[logging.FileHandler(app_log_path), logging.StreamHandler()],
)
logging.info("init logging module")


def new_exception(msg, *args, exc_info=True, **kwargs):
    exc_string = "\n".join([str(arg) for arg in args] + [traceback.format_exc()])
    if USE_ARGO_TRACKING == "true":
        argo_tracking(ExceptionTrackingPayload(exception=exc_string))
    return logging.error(exc_string)


logging.exception = new_exception
