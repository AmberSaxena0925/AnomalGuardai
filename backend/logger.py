"""
logger.py — Logging Configuration for AnomalyGuard
"""

import logging
import logging.handlers
import os
from config import config


def setup_logging():
    """Configure logging for the application."""
    logger = logging.getLogger("anomalyguard")
    logger.setLevel(getattr(logging, config.logging.LOG_LEVEL))
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(config.logging.LOG_FILE), exist_ok=True)
    
    formatter = logging.Formatter(config.logging.LOG_FORMAT)
    
    # Console handler
    if config.logging.ENABLE_CONSOLE_LOGGING:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, config.logging.LOG_LEVEL))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # File handler with rotation
    if config.logging.ENABLE_FILE_LOGGING:
        file_handler = logging.handlers.RotatingFileHandler(
            config.logging.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, config.logging.LOG_LEVEL))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create global logger instance
logger = setup_logging()


def get_logger(name: str = "anomalyguard") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
