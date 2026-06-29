import logging
from logging import StreamHandler, FileHandler
import datetime
import os
from colorama import Fore, Style, init

init(autoreset=True)  # Initialize colorama

class SingletonMeta(type):
    """
    A Singleton metaclass implementation.
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Fore.BLUE,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record):
        log_color = self.LEVEL_COLORS.get(record.levelno, Fore.WHITE)
        record.msg = log_color + record.msg + Style.RESET_ALL

        # Ensure username is 15 characters wide, padded with spaces
        username = record.username if record.username else 'Unknown'
        record.username = f"{username:<15}"
        
        return super().format(record)

class CustomLogger(metaclass=SingletonMeta):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Create console handler with a higher log level
        ch = StreamHandler()
        ch.setLevel(logging.DEBUG)

        # Create formatter and add it to the handlers
        formatter = ColoredFormatter('[%(username)s - %(asctime)s] %(message)s')
        ch.setFormatter(formatter)

        # Create Logs folder if it does not exist
        if not os.path.exists('Logs'):
            os.makedirs('Logs')

        # Create file handler with the current date and time as filename
        current_time = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        fh = FileHandler(f'Logs/{current_time}.txt')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('[%(username)s - %(asctime)s] %(message)s'))

        # Add the handlers to the logger
        if not self.logger.handlers:
            self.logger.addHandler(ch)
            self.logger.addHandler(fh)
        
        self.username = None
        self.logger = logging.LoggerAdapter(self.logger, {'username': self.username})
    
    def set_username(self, username):
        self.username = username
        self.logger = logging.LoggerAdapter(self.logger.logger, {'username': self.username})

    def log(self, message, level=logging.INFO):
        message = str(message)
        extra = {'username': self.username or 'Unknown'}
        if level == logging.DEBUG:
            self.logger.debug(message, extra=extra)
        elif level == logging.INFO:
            self.logger.info(message, extra=extra)
        elif level == logging.WARNING:
            self.logger.warning(message, extra=extra)
        elif level == logging.ERROR:
            self.logger.error(message, extra=extra)
        elif level == logging.CRITICAL:
            self.logger.critical(message, extra=extra)
        else:
            self.logger.info(message, extra=extra)
    
    def debug(self, message):
        self.log(message, level=logging.DEBUG)
    
    def info(self, message):
        self.log(message, level=logging.INFO)
    
    def warning(self, message):
        self.log(message, level=logging.WARNING)
    
    def error(self, message):
        self.log(message, level=logging.ERROR)
    
    def critical(self, message):
        self.log(message, level=logging.CRITICAL)

if __name__ == "__main__":
    # Example usage
    logger = CustomLogger()
    logger.log('This is an info message.')
    logger.set_username('User123')
    logger.log('This is an info message.')
    logger.log('This is a debug message.', level=logging.DEBUG)
    logger.log('This is a warning message.', level=logging.WARNING)
    logger.log('This is an error message.', level=logging.ERROR)
    logger.log('This is a critical message.', level=logging.CRITICAL)
    logger.log({1:2})
