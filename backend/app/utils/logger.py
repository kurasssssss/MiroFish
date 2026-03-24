import os
import logging
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\x1b[36m',
        'INFO': '\x1b[32m',
        'WARNING': '\x1b[33m',
        'ERROR': '\x1b[31m',
        'CRITICAL': '\x1b[35m'
    }
    RESET = '\x1b[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.msg = f'{log_color}{record.msg}{self.RESET}'
        return super().format(record)

def setup_logger(name):
    log_directory = 'logs'
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # TimedRotatingFileHandler for daily log rotation
    daily_log_handler = TimedRotatingFileHandler(os.path.join(log_directory, '{name}.log'), when='midnight', interval=1, backupCount=7)  
    daily_log_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    # RotatingFileHandler for size-based rotation
    size_log_handler = RotatingFileHandler(os.path.join(log_directory, '{name}_size.log'), maxBytes=10*1024*1024, backupCount=5)
    size_log_handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(daily_log_handler)
    logger.addHandler(size_log_handler)

    return logger

# Convenience functions for direct logging
logger_instance = None

def get_logger(name):
    global logger_instance
    if logger_instance is None:
        logger_instance = setup_logger(name)
    return logger_instance

# Convenience functions for direct logging

def debug(msg):
    get_logger('default').debug(msg)

def info(msg):
    get_logger('default').info(msg)

 def warning(msg):
    get_logger('default').warning(msg)

 def error(msg):
    get_logger('default').error(msg)

 def critical(msg):
    get_logger('default').critical(msg)

"""
Logging System Architecture:

1. Loggers: The main component that the application uses to log messages. Each component can have its own logger.

2. Handlers: Handlers send the log messages to their final destination, which could be a file or the console. We use TimedRotatingFileHandler and RotatingFileHandler.

3. Formatters: They define the layout of log messages. We have implemented a ColoredFormatter for colored output in the console.

Usage Examples:

- To log messages:
    debug('This is a debug message')
    info('This is an info message')
    warning('This is a warning message')
    error('This is an error message')
    critical('This is a critical message')

- To use a custom logger:
    logger = setup_logger('my_logger')
    logger.info('This is an info message from my_logger')

"""
