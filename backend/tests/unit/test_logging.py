import logging
import sys

from app.observability.logging import configure_logging


def test_configure_logging_uses_stderr():
    logger = logging.getLogger("enterprise_support_ai")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    configured = configure_logging()

    assert len(configured.handlers) >= 1
    assert configured.handlers[0].stream is sys.stderr
