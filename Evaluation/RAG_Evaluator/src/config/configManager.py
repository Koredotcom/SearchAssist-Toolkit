# src/config/configManager.py
# 
# ARCHITECTURAL NOTE: 
# This system no longer requires a static config.json file!
# All configurations are now dynamically created per-session in routes/app.py
# This ConfigManager provides fallback defaults when no session config exists.

import json
import os
from pathlib import Path

class ConfigManager:
    _instance = None

    def __new__(cls, config_path=None):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config = cls._instance._load_config(config_path)
        return cls._instance

    def _load_config(self, config_path=None):
        """
        Load configuration from specified path or create minimal default.
        Supports session-specific configs for multi-user isolation.
        """
        if config_path and os.path.exists(config_path):
            # Use session-specific config if provided
            print(f"🔧 Loading session-specific config from: {config_path}")
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Create minimal default config (no static file needed!)
            print(f"🔧 Creating minimal default config (no static config.json required)")
            return {
                "cost_of_model": {
                    "input": 0.00000015,
                    "output": 0.0000006
                },
                "MongoDB": {
                    "url": os.getenv("MONGO_URL", "<MONGO_URL>"),
                    "dbName": os.getenv("DB_NAME", "<DB_NAME>"),
                    "collectionName": os.getenv("COLLECTION_NAME", "<COLLECTION_NAME>")
                },
                "openai": {
                    "model_name": "gpt-4o",
                    "embedding_name": "text-embedding-ada-002"
                },
                "azure": {
                    "openai_api_version": "2024-02-15-preview",
                    "base_url": "<AZURE_BASE_URL>",
                    "model_name": "gpt-4o",
                    "model_deployment": "<MODEL_DEPLOYMENT>",
                    "embedding_deployment": "<EMBEDDING_DEPLOYMENT>",
                    "embedding_name": "text-embedding-ada-002"
                }
            }

    def get_config(self):
        return self.config
    
    @classmethod
    def create_session_config_manager(cls, session_config_path):
        """
        Create a new ConfigManager instance for session-specific config.
        This bypasses the singleton pattern for session isolation.
        """
        instance = object.__new__(cls)
        instance.config = instance._load_config(session_config_path)
        return instance