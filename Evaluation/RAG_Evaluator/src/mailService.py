import pandas as pd
from pymongo import MongoClient
from config.configManager import ConfigManager
import os
import numpy as np

config_manager = ConfigManager()
config = config_manager.get_config()

# MongoDB connection setup
client = MongoClient(config["MongoDB"]["url"])
db = client[config["MongoDB"]["dbName"]]

# fetch the last 5 testsets from a collection (where _id = 0)
def fetch_last_5_testsets():
    collections = db.list_collection_names()
    records = []
    
    collections = sorted(collections)[::-1][:5]
    
    for collection_name in collections:
        collection = db[collection_name]
        record = collection.find_one({"_id": 0})
        if record:
            records.append(record)

        df = pd.DataFrame(list(collection.find()))
        # Determine the directory relative to the location of the current file
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        relative_output_dir = os.path.join(current_file_dir, "outputs", "attachments")
        
        # Create the directory if it doesn't exist
        os.makedirs(relative_output_dir, exist_ok=True)
        
        # Save the DataFrame to an Excel file in the specified directory
        df.to_excel(os.path.join(relative_output_dir, f"{collection_name}.xlsx"), index=False)
    
    return records

# calculate the z-score for a given metric
def calculate_z_score(value, mean, std_dev):
    if std_dev == 0:
        return 0
    return (value - mean) / std_dev

# Function to check for significant change using z-scores
def detect_significant_change(latest_record, records, threshold=2):
    significant = False
    metrics = [
        # "answer_relevancy",
        # "faithfulness",
        "context_recall",
        "context_precision",
        # "answer_correctness",
        # "answer_similarity",
    ]
    changes = {}

    for metric in metrics:
        values = [record[metric] for record in records]
        mean_value = np.mean(values)
        std_dev = np.std(values)
        latest_value = latest_record[metric]
        z_score = calculate_z_score(latest_value, mean_value, std_dev)

        # If the z-score exceeds the threshold, mark the change as significant
        if abs(z_score) > threshold:
            significant = True
            changes[metric] = {
                'latest_value': latest_value,
                'mean': mean_value,
                'std_dev': std_dev,
                'z_score': z_score
            }
            print("Significant change detected!")
            print(f"{metric}: {z_score}")

    return significant, changes


def mail_body_html(latest_record, changes):
    content = f"""<html>
    <body>
        <p>System Evaluation Metrics:</p>
        <ul>
            <li>Answer Relevancy: {latest_record['answer_relevancy']}</li>
            <li>Faithfulness: {latest_record['faithfulness']}</li>
            <li>Context Recall: {latest_record['context_recall']}</li>
            <li>Context Precision: {latest_record['context_precision']}</li>
            <li>Answer Correctness: {latest_record['answer_correctness']}</li>
            <li>Answer Similarity: {latest_record['answer_similarity']}</li>
        </ul>
        <p>Change details:</p>
        <ul>
            {"".join([f"<li>{metric}: {info['latest_value']} (z-score: {info['z_score']:.2f}, mean: {info['mean']:.2f}, std: {info['std_dev']:.2f})</li>" for metric, info in changes.items()])}
        </ul>
    </body>
    </html>"""

    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "outputs", "attachments")
    with open(os.path.join(relative_output_dir, "mail_body.html"), "w") as file:
        file.write(content)

def mail_subject(sig_change):
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "outputs", "attachments")
    with open(os.path.join(relative_output_dir, "mail_subject.txt"), "w") as file:
        if(sig_change):
            file.write("Alert: Significant change in System Evaluation Notification")
        else:
            file.write("System Evaluation Notification")


# Main logic
def mailService():
    # Fetch the last 5 test set records (_id = 0 from each collection)
    records = fetch_last_5_testsets()

    # Check the latest record (last in the fetched list)
    latest_record = records[-1]
    
    
    significant, changes = detect_significant_change(latest_record, records)
    
    # Create mail body html file
    mail_body_html(latest_record, changes)

    # Check if there is a significant change and update the subject
    if significant:
        mail_subject(True)        
    else:
        mail_subject(False)

if __name__ == "__main__":
    mailService()
