from typing import Union


def convert_bits(size: Union[int, float]):
    units = ["Bytes", "kB", "MB", "GB", "TB", "PB", "EB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024


def size_transfer(size: str):
    digit, unit = size.strip().split()
    if unit == "Bytes":
        return float(digit)
    elif unit == "kB":
        return float(digit) * 1024
    elif unit == "MB":
        return float(digit) * 1024 * 1024
    elif unit == "GB":
        return float(digit) * 1024 * 1024 * 1024
    else:
        return 25 * 1024 * 1024 * 1024
