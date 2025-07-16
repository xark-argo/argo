import os
import platform
import shutil
from subprocess import DEVNULL, check_output

__version__ = "1.4.1.2"
CREATE_NO_WINDOW = 0x08000000

NVIDIA_SMI_QUERY_FIELDS = [
    "index",
    "uuid",
    "utilization.gpu",
    "memory.total",
    "memory.used",
    "memory.free",
    "driver_version",
    "name",
    "gpu_serial",
    "display_active",
    "display_mode",
    "temperature.gpu",
]


class GPU:
    def __init__(
        self,
        id,
        uuid,
        load,
        memory_total,
        memory_used,
        memory_free,
        driver,
        name,
        serial,
        display_mode,
        display_active,
        temperature,
    ):
        self.id = id
        self.uuid = uuid
        self.load = load
        self.memory_util = float(memory_used) / float(memory_total) if memory_total else float("nan")
        self.memory_total = memory_total
        self.memory_used = memory_used
        self.memory_free = memory_free
        self.driver = driver
        self.name = name
        self.serial = serial
        self.display_mode = display_mode
        self.display_active = display_active
        self.temperature = temperature


def safe_float(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return float("nan")


def get_nvidia_smi_path() -> str | None:
    path = shutil.which("nvidia-smi")
    if path:
        return path

    if platform.system() == "Windows":
        return os.path.join(
            os.environ.get("systemdrive", "C:"),  # noqa: SIM112
            "Program Files",
            "NVIDIA Corporation",
            "NVSMI",
            "nvidia-smi.exe",
        )

    return None


def get_gpus() -> list[GPU]:
    nvidia_smi = get_nvidia_smi_path()
    if not nvidia_smi or not os.path.exists(nvidia_smi):
        return []

    try:
        stdout = check_output(
            [
                nvidia_smi,
                f"--query-gpu={','.join(NVIDIA_SMI_QUERY_FIELDS)}",
                "--format=csv,noheader,nounits",
            ],
            creationflags=CREATE_NO_WINDOW if platform.system() == "Windows" else 0,
            stderr=DEVNULL,
        )
    except:
        return []

    lines = stdout.decode("utf-8").strip().splitlines()
    gpus = []

    for line in lines:
        fields = line.split(", ")
        if len(fields) != len(NVIDIA_SMI_QUERY_FIELDS):
            continue  # skip malformed line

        gpus.append(
            GPU(
                id=int(fields[0]),
                uuid=fields[1],
                load=safe_float(fields[2]) / 100,
                memory_total=safe_float(fields[3]),
                memory_used=safe_float(fields[4]),
                memory_free=safe_float(fields[5]),
                driver=fields[6],
                name=fields[7],
                serial=fields[8],
                display_active=fields[9],
                display_mode=fields[10],
                temperature=safe_float(fields[11]),
            )
        )

    return gpus
