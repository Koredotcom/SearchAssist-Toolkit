# Salesforce Custom Extraction Utility

This utility allows for custom extraction of data from Salesforce and ingest to search AI.

## Prerequisites

- Python 3.9.7
- Git

## Getting Started

Follow the steps below to set up and run the Salesforce Custom Extraction Utility.

### Steps

1. **Clone the repository**:
    ```bash
    git clone https://github.com/Koredotcom/SearchAssist-Toolkit.git

2. **Checkout to the Salesforce Custom Extraction Utility branch**:
    ```bash
    git checkout master
    ```

3. **Navigate to the Salesforce Custom Extraction Utility directory**:
    ```bash
    cd Extraction/SalesforceCustomExtractionUtility
    ```

4. **Create a `.env` file and configure the following environment variables**:
    ```plaintext
     
    # Specify the language model provider: "openai" or "azure"
    llm_used=""

    # open ai
    open_ai_key=""
    openAI_apibase=""
    openai_model=""


    #Azure open ai
    AZURE_OPENAI_KEY=""
    API_BASE=""
    azure_model=""
    userSubDomain= ""
    deployment=""
    Apiversion=""

    #update testing environment
    # if cloud then test_env="login" for sandbox="test"
    test_env=""

    # Access Token
    hostUrl = "***"
    clientId = "**"
    clientSecret = "***"
    redirectUri = "***"
    accessTokenAuthCode = "***"

    # Each Batch Count
    eachBatchCount = 10

    # SearchAssist credentials
    searchassist_botId = "***"
    searchassist_Auth = "***"
    searchassist_URL = "***"

    # Input and Output Paths
    input_path = ".data/input/"
    output_path = ".data/output/"
    ```

    #Proxy URLs for network access
    proxies= {"http": "PROXY URL","https": "PROXY URL"}

    #Specifies whether data fetching uses URL names or Item IDs
    #inputFormat="urlnames" or inputFormat="itemids"
    inputFormat =""

    #SSL Verification
    #Set to "False" if SSL Verification is not needed, otherwise set to "True"
    ssl=""


5. **Create and activate a virtual environment**:
    ```bash
    cd /data
    /data/Python-3.9.7/bin/python3.9 -m venv py3.9.7
    source /data/py3.9.7/bin/activate
    ```

6. **Install the required packages**:
    ```bash
    pip install -r requirements.txt
    ```

7. **Run the utility**:
    ```bash
    python main.py
    ```

## Configuration Details

- **OPENAI_KEY**: API key for OpenAI services.
- **hostUrl**: URL of the host for the access token.
- **clientId**: Client ID for authentication.
- **clientSecret**: Client secret for authentication.
- **redirectUri**: Redirect URI for authentication.
- **accessTokenAuthCode**: Access token authorization code.
- **eachBatchCount**: Number of records to process in each batch.
- **searchassist_botId**: Bot ID for SearchAssist.
- **searchassist_Auth**: Authentication token for SearchAssist.
- **searchassist_URL**: URL for SearchAssist services.
- **input_path**: Path to the input directory.
- **output_path**: Path to the output directory.

## Notes

- Ensure you have the necessary permissions and credentials to access Salesforce and SearchAssist services.
- The `.env` file should be kept secure and not shared publicly.
