"""
Global configuration settings
"""
import logging

LOG_LEVEL = logging.WARNING 

log_to_file = False

if log_to_file:
    handler = logging.FileHandler("log.log")
else:
    handler = logging.StreamHandler()

handler.setFormatter(logging.Formatter("%(name)s:%(levelname)s:: %(message)s"))
logger = logging.getLogger("CFGext")
logger.setLevel(LOG_LEVEL)
logger.addHandler(handler)
