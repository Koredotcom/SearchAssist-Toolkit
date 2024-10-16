from pymongo import MongoClient
import numpy as np
from config.configManager import ConfigManager

config_manager = ConfigManager()
config = config_manager.get_config()

# MongoDB connection setup
client = MongoClient(config["MongoDB"]["url"])
db = client[config["MongoDB"]["dbName"]]


def dbService(df, name, result):
    results = db[name]
    
    #instert result in results collection with _id as 0
    result['_id'] = 0
    results.insert_one(result)   
    df = df.applymap(lambda x: x.tolist() if isinstance(x, np.ndarray) else x)
    data_dict = df.to_dict(orient='records')
    for i in range(1, len(data_dict)+1):
        data_dict[i-1]['_id'] = i
    results.insert_many(data_dict)
    print("Data inserted successfully")
    