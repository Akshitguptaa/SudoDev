import logging
import sys
from termcolor import colored

def setup_logger(name="SudoDev"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def log_step(step_name, message):
    """Helper for colorful step logging"""
    print(colored(f"\n[STEP: {step_name}]", "cyan", attrs=["bold"]))
    print(f"{message}")

def log_success(message):
    print(colored(f"✔ {message}", "green"))

def log_error(message):
    print(colored(f"✖ {message}", "red"))