import logging

logger = logging.getLogger("llama-cpp-python")


def set_verbose(verbose: bool):
    logger.setLevel(logging.DEBUG if verbose else logging.ERROR)
