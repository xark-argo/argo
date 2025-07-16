import hashlib
import json


def calculate_sha256(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as fp:
        for byte_block in iter(lambda: fp.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def calculate_content_sha256(file_content: bytes) -> str:
    sha256_hash = hashlib.sha256()
    sha256_hash.update(file_content)
    return sha256_hash.hexdigest()


def calculate_url_sha256(url_info: dict) -> str:
    json_str = json.dumps(url_info, sort_keys=True)
    sha256_hash = hashlib.sha256(json_str.encode())
    return sha256_hash.hexdigest()
