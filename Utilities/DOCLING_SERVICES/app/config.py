import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Get the base directory of the service
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / 'config' / '.env'
load_dotenv(ENV_FILE)

# Try to load configuration from JSON file if it exists
config_data = {}
config_file_path = BASE_DIR / 'config.json'
if config_file_path.exists():
    with open(config_file_path, 'r') as config_file:
        config_data = json.load(config_file)

# Configuration values with environment variable fallbacks
HOST = os.getenv('HOST', config_data.get('HOST', '0.0.0.0'))
MARKDOWN_SERVICE_PORT = int(os.getenv('MARKDOWN_SERVICE_PORT', config_data.get('MARKDOWN_SERVICE_PORT', 8000)))
PDF_THREAD_POOL_SIZE = int(os.getenv('PDF_THREAD_POOL_SIZE', config_data.get('PDF_THREAD_POOL_SIZE', 3)))

# Logging configuration
LOGS_DIR = os.path.join(BASE_DIR, 'logs')  # Relative to service directory
MARKDOWN_LOG_FILE = os.path.join(LOGS_DIR, 'markdown_service.log')

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# Processing configuration
MAX_RETRIES = int(os.getenv('MAX_RETRIES', config_data.get('MAX_RETRIES', 3)))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', config_data.get('RETRY_DELAY', 5000)))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', config_data.get('REQUEST_TIMEOUT', 300000))) 