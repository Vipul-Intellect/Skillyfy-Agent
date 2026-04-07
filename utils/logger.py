import logging
import sys

def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        # Use stderr so MCP JSON-RPC on stdout stays clean
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def get_logger(name):
    return setup_logger(name)
