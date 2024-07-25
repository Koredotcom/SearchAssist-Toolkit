# src/config/configManager.py

import json
from pathlib import Path

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config = cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        config_path = Path(__file__).parent / 'config.json'
        with open(config_path, 'r') as f:
            return json.load(f)

    def get_config(self):
        return self.config