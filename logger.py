import logging
import os
import traceback
import json
from logging.handlers import RotatingFileHandler

try:
    import requests
except Exception:
    requests = None

_LOGGER_CONFIGURED = False


def configure_logging():
    """Configure root logger once based on environment variables."""
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")

    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handlers.append(fh)

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

    _LOGGER_CONFIGURED = True


def get_logger(name=None):
    configure_logging()
    return logging.getLogger(name)


def report_error(exc: Exception, context: dict = None):
    """Send an error report to remote endpoint if configured, otherwise log the details.

    Environment variables:
    - ERROR_REPORT_URL: if set, the module will POST JSON to this URL with keys: error, traceback, context
    """
    logger = get_logger("error_reporter")
    try:
        payload = {
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "context": context or {},
        }
        url = os.getenv("ERROR_REPORT_URL")
        if url and requests is not None:
            try:
                requests.post(url, json=payload, timeout=5)
            except Exception as e:
                logger.error("Failed to send error report to %s: %s", url, e)
        else:
            # no remote endpoint configured or requests not installed; log the payload
            logger.error(
                "Error reported: %s\n%s\nContext: %s",
                payload["error"],
                payload["traceback"],
                json.dumps(payload["context"], ensure_ascii=False),
            )
    except Exception:
        logger.exception("Failed inside report_error")
