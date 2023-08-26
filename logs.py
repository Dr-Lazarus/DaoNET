import logging
from pythonjsonlogger import jsonlogger

formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(message)s')
# formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

def setup_logger(name, log_file, level=logging.INFO):
    """To setup as many loggers as you want"""
    """
    Here, handler is the file it will be written to, and logger is the logger 
    object that we can call for logging. 
    """    
    handler = logging.FileHandler(log_file)# Will write messages to a file named log_file      
    handler.setFormatter(formatter)

    logger = logging.getLogger(name) # Creates a logger with the name 'name'
    logger.setLevel(level) # Overwrites the default log level
    logger.addHandler(handler) # Adds the handler to the logger

    return logger