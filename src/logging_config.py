"""
Logging configuration using structlog.
"""

import sys
import structlog
from structlog.stdlib import LoggerFactory


def configure_logging(debug: bool = False):
    """
    Configure structured logging.
    
    Args:
        debug: Enable debug logging
    """
    log_level = "DEBUG" if debug else "INFO"
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None):
    """Get a configured logger."""
    return structlog.get_logger(name)
