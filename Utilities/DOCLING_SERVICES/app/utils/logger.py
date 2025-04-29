import logging
import os
from app.config import LOGS_DIR, MARKDOWN_LOG_FILE

def setup_logger(name):
    """Set up logger with file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Create formatters and handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # File handler
    file_handler = logging.FileHandler(MARKDOWN_LOG_FILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger 