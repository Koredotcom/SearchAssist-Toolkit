import pandas as pd
from pymongo import MongoClient
from config.configManager import ConfigManager
import os
import numpy as np

config_manager = ConfigManager()
config = config_manager.get_config()


def fetch_last_5_testsets():
    try:
        # MongoDB connection setup
        client = MongoClient(config["MongoDB"]["url"])
        db = client[config["MongoDB"]["dbName"]]
        collection = db[config["MongoDB"]["collectionName"]]
    except Exception as e:
        print(f"An error occurred: {e}")
        raise Exception(f"Error in connecting to MongoDB. {e}") 
       
    try:
        # fetch the last 5 documents in the collection
        records = []
        length = collection.count_documents({})
        for i in range(length-5, length):
            record = collection.find_one({"_id": i})
            if record:
                records.append(record)
        for record in records:
            df = pd.DataFrame(record['full_results'])
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            relative_output_dir = os.path.join(current_file_dir,"..", "outputs", "attachments")
            
            # Create the directory if it doesn't exist
            os.makedirs(relative_output_dir, exist_ok=True)
            time = record['timestamp'].replace(" ", "_").replace(":", "-")
            # Save the DataFrame to an Excel file in the specified directory
            df.to_excel(os.path.join(relative_output_dir, f"{time}.xlsx"), index=False)
        return list(records)
    except Exception as e:
        print(f"An error occurred: {e}")
        raise Exception(f"Error in fetching records from MongoDB. {e}")

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
    change_details = ""
    if changes != {}:
        change_details = f"""
        <p>Change details:</p>
        <ul>
            {"".join([f"<li>{metric}: {info['latest_value']} (z-score: {info['z_score']:.2f}, mean: {info['mean']:.2f}, std: {info['std_dev']:.2f})</li>" for metric, info in changes.items()])}
        </ul>
        """

    content = f"""
    <html>
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
        {change_details}
    </body>
    </html>"""

    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "..", "outputs", "attachments")
    with open(os.path.join(relative_output_dir, "mail_body.html"), "w") as file:
        file.write(content)

def mail_subject(sig_change):
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    relative_output_dir = os.path.join(current_file_dir, "..", "outputs", "attachments")
    with open(os.path.join(relative_output_dir, "mail_subject.txt"), "w") as file:
        if(sig_change):
            file.write("Alert: Significant change in System Evaluation Notification")
        else:
            file.write("System Evaluation Notification")

def send_mail():
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from email.utils import formataddr
    
    recipient = "recipient@example.com"
    sender_email = "your_email@example.com"
    sender_name = "Your Name"
    smtp_server = "smtp.example.com"
    smtp_port = 587
    smtp_user = "your_smtp_username"
    smtp_password = "your_smtp_password"
    
    try:
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        relative_output_dir = os.path.join(current_file_dir, "..", "outputs", "attachments")
        
        with open(os.path.join(relative_output_dir, "mail_body.html"), "r") as file:
            content = file.read()
            
        with open(os.path.join(relative_output_dir, "mail_subject.txt"), "r") as file:
            subject = file.read()  
    except Exception as e:
        print(f"Failed to read mail content: {e}")
        return
    
    try:
        msg = MIMEMultipart()
        msg['From'] = formataddr((sender_name, sender_email))
        msg['To'] = recipient
        msg['Subject'] = subject

        # Attach the email body
        msg.attach(MIMEText(content, 'html'))

        # Attach the latest 5 Excel files from the attachments directory
        excel_files = [f for f in os.listdir(relative_output_dir) if f.endswith(".xlsx")]

        for file_name in excel_files:
            file_path = os.path.join(relative_output_dir, file_name)
            with open(file_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {file_name}",
                )
                msg.attach(part)
    except Exception as e:
        print(f"Failed to create email: {e}")
        return

    # Send the email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(sender_email, recipient, msg.as_string())
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")  


# Main logic
def mailService(sendMail):
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

    # For sending mail
    if sendMail:
        print("Sending mail...")
        send_mail()

if __name__ == "__main__":
    mailService()
