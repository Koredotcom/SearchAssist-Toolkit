from pymongo import MongoClient
import numpy as np
from config.configManager import ConfigManager
from datetime import datetime

config_manager = ConfigManager()
config = config_manager.get_config()



def dbService(df, result, timestamp):
    # MongoDB connection setup
    client = MongoClient(config["MongoDB"]["url"])
    db = client[config["MongoDB"]["dbName"]]
    collection = db[config["MongoDB"]["collectionName"]]
    
    result["_id"] = collection.count_documents({})
    dt = datetime.strptime(timestamp, "%Y%m%d-%H%M%S")
    formatted_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
    result['timestamp'] = formatted_timestamp
    df = df.applymap(lambda x: x.tolist() if isinstance(x, np.ndarray) else x)
    data_dict = df.to_dict(orient='records')
    result['full_results'] = data_dict
    collection.insert_one(result)
    print("Data inserted successfully")
    