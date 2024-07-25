import json

# Function to read the configuration file
def read_config(file_path):
    with open(file_path, 'r') as file:
        config = json.load(file)
    return config