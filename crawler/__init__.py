import logging
import sys


def initialize_logger(name: str, log_level: int = logging.INFO):
    """
    Initialize a logger with the specified name and log level.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level)

    # Create formatter and add it to the handler
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)

    # Add the handler to the logger
    if not logger.handlers:
        logger.addHandler(ch)

    return logger


log = initialize_logger(__name__, logging.DEBUG)

if __name__ == "__main__":
    log.info("hello")
    log.debug("test")
    log.error("error")
