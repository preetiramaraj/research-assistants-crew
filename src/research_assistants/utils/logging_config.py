"""
Shared logging configuration for the research assistants project.
Provides reusable file logging setup.
"""

import logging
from pathlib import Path


def setup_file_logger(
    name: str,
    log_file_path: str,
    level: int = logging.INFO
) -> logging.Logger:
    """
    Create a logger that writes to a file.
    
    Args:
        name: Logger name (typically __name__)
        log_file_path: Path to the log file
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    log_file = Path(log_file_path)
    
    handler = logging.FileHandler(log_file)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    logger.setLevel(level)
    
    return logger
