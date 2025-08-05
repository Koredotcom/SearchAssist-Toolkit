import os

def ensure_logs_directory():
    """Ensure that the logs directory exists."""
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir) 