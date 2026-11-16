import logging
from logging.handlers import RotatingFileHandler
from src.settings import BACKEND


def configure_logging():
    directory = BACKEND / 'logs'
    directory.mkdir(exist_ok=True)
    logger = logging.getLogger('krishi')
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        for handler in (logging.StreamHandler(), RotatingFileHandler(
                directory / 'application.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
