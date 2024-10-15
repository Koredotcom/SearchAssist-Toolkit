import pandas as pd
from pymongo import MongoClient
from config.configManager import ConfigManager

config_manager = ConfigManager()
config = config_manager.get_config()

# MongoDB connection setup
client = MongoClient(config["MongoDB"]["url"])
db = client[config["MongoDB"]["dbName"]]

# fetch the last 5 testsets from a collection (where _id = 0)
def fetch_last_5_testsets():
    collections = db.list_collection_names()
    records = []
    
    for collection_name in collections:
        collection = db[collection_name]
        record = collection.find_one({"_id": 0})
        if record:
            records.append(record)

        df = pd.DataFrame(list(collection.find()))
        df.to_excel(f"../outputs/attachments/{collection_name}.xlsx", index=False)
    
    # Sort collections by insertion order and get the last 5 records
    records = sorted(records, key=lambda x: x['_id'], reverse=True)[:5]
    return records[::-1]  # Reverse to maintain chronological order

# calculate moving average 
def calculate_moving_average(records, metric):
    values = [record[metric] for record in records]
    return sum(values) / len(values)

# check if there is significant change in the latest record
def has_significant_change(latest_record, moving_averages, threshold=0.01):
    for metric, avg_value in moving_averages.items():
        latest_value = latest_record.get(metric, 0)
        percentage_change = abs((latest_value - avg_value) / avg_value)
        if percentage_change > threshold:
            print(f"{metric}: {percentage_change}")
            print("Significant change detected!")
            return True
    return False

def mail_body_html(latest_record):
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
    </body>
    </html>"""

    with open("../outputs/mail_body.html", "w") as file:
        file.write(content)
        
def mail_subject(sig_change):
    with open("../outputs/mail_subject.txt", "w") as file:
        if(sig_change):
            file.write("Alert: Significant change in System Evaluation Notification")
        else:
            file.write("System Evaluation Notification")


# Main logic
def mailService():
    # Fetch the last 5 test set records (_id = 0 from each collection)
    records = fetch_last_5_testsets()

    # Calculate moving averages for each metric
    moving_averages = {
        'answer_relevancy': calculate_moving_average(records, 'answer_relevancy'),
        'faithfulness': calculate_moving_average(records, 'faithfulness'),
        'context_recall': calculate_moving_average(records, 'context_recall'),
        'context_precision': calculate_moving_average(records, 'context_precision'),
        'answer_correctness': calculate_moving_average(records, 'answer_correctness'),
        'answer_similarity': calculate_moving_average(records, 'answer_similarity'),
    }

    # Check the latest record (last in the fetched list)
    latest_record = records[-1]
    
    # Create mail body html file
    mail_body_html(latest_record)

    # Check if there is a significant change and update the subject
    if has_significant_change(latest_record, moving_averages):
        mail_subject(True)        
    else:
        mail_subject(False)

if __name__ == "__main__":
    mailService()
