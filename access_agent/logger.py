import logging
from enum import StrEnum

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

SILENT = logging.CRITICAL + 1
TOOL_CALL_LOGGER = "access_agent.agent_service"


class Verbosity(StrEnum):
    CLEAN = "clean"
    MINI = "mini"
    VERBOSE = "verbose"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(verbosity: Verbosity) -> None:
    """clean: no logs. mini: only agent tool-call logs. verbose: everything, including HTTP requests."""
    logging.getLogger().setLevel(logging.INFO if verbosity == Verbosity.VERBOSE else SILENT)
    logging.getLogger(TOOL_CALL_LOGGER).setLevel(logging.INFO if verbosity != Verbosity.CLEAN else SILENT)
