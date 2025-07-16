import logging
import os
import platform
import shutil
import tarfile
import time

import requests


def get_bin_name(tool_name):
    system = platform.system().lower()
    if system == "windows":
        return tool_name + ".exe"
    return tool_name


class McpToolInstaller:
    def __init__(self, base_url, filename, bin_name, target_dir):
        self.target_dir = target_dir
        self.bin_name = bin_name
        self.filename = filename

        self.file_unpack_dir = os.path.join(target_dir, bin_name)

        system = platform.system().lower()
        if system != "windows" and bin_name == "node":
            subdir = "bin"
        else:
            subdir = ""

        self.final_bin_path = os.path.join(self.file_unpack_dir, subdir, get_bin_name(bin_name))

        self.url = base_url + filename
        self.file_path = os.path.join(target_dir, filename)

    def is_exist(self):
        return os.path.exists(self.final_bin_path)

    def is_processing(self):
        """
        判断文件是否存在，并且时间戳在一分钟内
        :param file_path: 文件路径
        :return: True（文件存在且时间戳在一分钟内），False（否则）
        """
        if not os.path.exists(self.file_path):
            return False

        file_mtime = os.path.getmtime(self.file_path)
        current_time = time.time()
        time_diff = current_time - file_mtime

        # 判断时间差是否在一分钟内
        return time_diff <= 60

    def clear_package(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)

    def download_package(self):
        # 下载文件
        try:
            logging.info(f"start to download: {self.url}")
            response = requests.get(self.url, stream=True)
            response.raise_for_status()  # 检查请求是否成功
            with open(self.file_path, "wb") as f:
                f.writelines(response.iter_content(chunk_size=8192))
            logging.info(f"file download to: {self.file_path}")
        except requests.exceptions.RequestException as e:
            logging.exception("Download package failed.")
            raise Exception(f"Please check network and retry. error: {e}")

    def _chmod_recursive(self, path, mode=0o755):
        """递归设置权限"""
        if os.path.isdir(path):
            os.chmod(path, mode)
            for entry in os.listdir(path):
                self._chmod_recursive(os.path.join(path, entry), mode)
        else:
            os.chmod(path, mode)

    def _extract_and_move_files(self, extract_path):
        extracted_items = os.listdir(extract_path)

        if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_path, extracted_items[0])):
            sub_dir_name = extracted_items[0]
            sub_dir_path = os.path.join(extract_path, sub_dir_name)

            for item in os.listdir(sub_dir_path):
                item_path = os.path.join(sub_dir_path, item)
                self._chmod_recursive(item_path)
                shutil.move(item_path, extract_path)

            shutil.rmtree(sub_dir_path)

        else:
            for item in extracted_items:
                item_path = os.path.join(extract_path, item)
                self._chmod_recursive(item_path)

    def _unpack_install_gz(self):
        os.makedirs(self.file_unpack_dir, exist_ok=True)

        # 解压文件
        try:
            with tarfile.open(self.file_path, "r:gz") as tar:
                tar.extractall(self.file_unpack_dir)
            logging.info(f"gz uncompress successfully to：{self.file_unpack_dir}")

            self._extract_and_move_files(self.file_unpack_dir)
        except tarfile.TarError as e:
            logging.exception("gz uncompress error")
            raise Exception(f"gz uncompress error: {e}")

    def _unpack_install_zip(self):
        os.makedirs(self.file_unpack_dir, exist_ok=True)

        # 解压文件
        try:
            shutil.unpack_archive(self.file_path, self.file_unpack_dir, "zip")
            logging.info(f"zip uncompress to: {self.file_unpack_dir}")

            self._extract_and_move_files(self.file_unpack_dir)
        except Exception as e:
            logging.exception("zip uncompress error")
            raise Exception(f"zip uncompress error: {e}")

    def unpack_install(self):
        if ".tar.gz" in self.filename:
            return self._unpack_install_gz()
        if ".zip" in self.filename:
            return self._unpack_install_zip()

    def process(self):
        # 创建目标目录（如果不存在）
        os.makedirs(self.target_dir, exist_ok=True)

        if self.is_exist():
            logging.info(f"{self.bin_name} exists")
            return
        if self.is_processing():
            logging.info(f"{self.file_path} installing")
            return

        self.clear_package()
        self.download_package()
        self.unpack_install()
        self.clear_package()


if __name__ == "__main__":
    UvInstaller = McpToolInstaller(
        base_url="https://github.com/astral-sh/uv/releases/download/0.6.12/",
        filename="uv-aarch64-apple-darwin.tar.gz",
        bin_name="uv",
        target_dir=os.path.expanduser("~/.dev"),
    )
    BunInstaller = McpToolInstaller(
        base_url="https://github.com/oven-sh/bun/releases/download/bun-v1.2.8/",
        filename="bun-darwin-aarch64.zip",
        bin_name="bun",
        target_dir=os.path.expanduser("~/.dev"),
    )

    UvInstaller.process()
    BunInstaller.process()
