import logging

from logging.config import dictConfig


def init_config(log_file, level = logging.INFO):

    # Init
    log_config = {
        "version":    1,
        "root":       {
            "handlers": ["file"],
            "level":    "DEBUG"
        },
        "handlers":   {
            "file":    {
                "formatter": "std_out",
                "class":     "logging.FileHandler",
                "level":     level,
                "filename":  log_file
            }
        },
        "formatters": {
            "std_out": {
                "format": '%(asctime)s - %(name)-30s.%(funcName)-20s:%(lineno)-5d - %(levelname)-8s : %(message)s'
            }
        },
    }

    dictConfig(log_config)
