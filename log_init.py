import logging
import datetime

def initialize_logger(function_name):
    today = datetime.datetime.now()

    # Logger instantiation
    logger = logging.getLogger(function_name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)-20s - %(levelname)-8s - %(message)s')

    # Logger console output configuration
    consoleHandler = logging.StreamHandler()
    consoleHandler.setLevel(logging.DEBUG)
    consoleHandler.setFormatter(formatter)

    # Logger file configuration
    fileHandler = logging.FileHandler(f"logs/{today.strftime('%Y_%m_%d')}.log")
    fileHandler.setLevel(logging.INFO)
    fileHandler.setFormatter(formatter)

    if not len(logger.handlers):
        logger.addHandler(consoleHandler)
        logger.addHandler(fileHandler)

    return logger
