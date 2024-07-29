# src/utils/fileHandling.py

import json
import os
from datetime import datetime

current_dir = os.getcwd()


def load_json_file(file_path):

    # Construct the full file path
    file_path = os.path.join(current_dir, file_path)

    # Read and parse the JSON file
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)

        # Now you can work with the data
        print(data)
        return data
    except FileNotFoundError:
        print(f"The file {file_path} was not found in {os.path.join(current_dir, relative_path)}")
    except json.JSONDecodeError:
        print(f"The file {file_path} does not contain valid JSON")


def log_response(messages, response, output_directory="api_responses"):
    os.makedirs(output_directory, exist_ok=True)
    file_name = datetime.now().strftime("%d-%m-%Y-%H-%M-%S.json")
    file_path = os.path.join(output_directory, file_name)
    with open(file_path, "w") as f:
        json.dump({"messages": messages, "response": response}, f)

