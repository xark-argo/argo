"""Milvus Server"""

import datetime
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from os.path import abspath, dirname, join

import yaml
from qdrant_client import QdrantClient, models

from configs.env import ARGO_STORAGE_PATH
from configs.settings import VECTOR_SETTINTS
from utils.path import app_path


def _initialize_data_files(base_dir: str) -> tuple[str, str]:
    qdrant_dir = join(base_dir, "qdrant")
    logs_dir = join(qdrant_dir, "logs")

    os.makedirs(logs_dir, exist_ok=True)
    return qdrant_dir, logs_dir


def get_qdrant_executable_path():
    current = dirname(abspath(__file__))
    bin_dir = join(current, "bin")

    if sys.platform.lower() == "win32":
        return join(bin_dir, "qdrant.exe")
    return join(bin_dir, "qdrant")


def wait_qdrant_started(uri, timeout=10000):
    start_time = datetime.datetime.now()
    qdrant = QdrantClient(uri)

    while (datetime.datetime.now() - start_time).total_seconds() < (timeout / 1000):
        try:
            info = qdrant.info()
            if info.version:
                logging.info(f"qdrant start with {info}")
                break
        except Exception as e:
            time.sleep(0.2)


class QdrantServer:
    def __init__(self, base_data_dir=ARGO_STORAGE_PATH):
        self.uri = ""
        qdrant_dir, log_dir = _initialize_data_files(base_data_dir)
        self.qdrant_dir = qdrant_dir
        self.log_dir = log_dir

    def prepare_config_file(self):
        config_file = join(self.qdrant_dir, "qdrant.yaml")
        if os.path.exists(config_file):
            return config_file

        current = dirname(abspath(__file__))
        template_file = app_path(current, "qdrant-template.yaml")

        with open(template_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        config["storage"]["path"] = self.qdrant_dir

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config, f)
        return config_file

    def start(self, _debug=False):
        qdrant_exe = get_qdrant_executable_path()

        old_pwd = os.getcwd()
        os.chdir(self.qdrant_dir)
        envs = os.environ.copy()
        proc_fds = {}

        uri = VECTOR_SETTINTS.get("QDRANT_URI", "")
        if sys.platform.lower() == "linux":
            pass
        if sys.platform.lower() == "darwin":
            pass

        for name in ("stdout", "stderr"):
            run_log = join(self.log_dir, f"qdrant-{name}.log")
            # pylint: disable=consider-using-with
            proc_fds[name] = open(run_log, "w", encoding="utf-8")

        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        config_file = self.prepare_config_file()
        cmds = [qdrant_exe, "--config-path", config_file]
        logging.info(f"start qdrant {cmds}")

        if _debug:
            server_proc = subprocess.Popen(cmds, env=envs, creationflags=creationflags)
        else:
            # pylint: disable=consider-using-with
            server_proc = subprocess.Popen(
                cmds,
                stdout=proc_fds["stdout"],
                stderr=proc_fds["stderr"],
                env=envs,
                creationflags=creationflags,
            )
        os.chdir(old_pwd)
        threading.Thread(target=(wait_qdrant_started), args=(uri,), daemon=True)

        self.uri = uri
        wait_qdrant_started(uri)


default_server = QdrantServer()
# default_server.start(ARGO_STORAGE_PATH)
