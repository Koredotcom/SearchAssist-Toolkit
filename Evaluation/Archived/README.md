# SearchAssist Evaluation Utility

This utility provides a detailed result about SearchAssist accuracy by generating a CSV file with all necessary debugging details. The utility performs a comparison between the expected answer and the retrieved answer in four stages:

1. Exact string match.
2. Substring match.
3. Fuzzy string match.
4. Semantic match by embeddings (Note: This stage requires running a separate Python service).

If you want to disable the semantic match, set the flag `semantic_flag = 0` in the `src.js` code. If you want to enable it, set the flag as `semantic_flag = 1`.

## Table of Contents

- Requirements
- Configuration
- Installation and Usage

## Requirements

To use this utility, the following dependencies are required:

- Python 3.8.10 (Follow the installation steps from [here](https://linuxize.com/post/how-to-install-python-3-8-on-ubuntu-18-04/) for Ubuntu) [Only needed if semantic similiarity has to be performed]
- Flask
- numpy
- nltk
- sentence-transformers
- node.js
- express
- body-parser
- fs
- fast-csv
- axios
- path
- fuzzball
- compute-cosine-similarity
- csv-writer


## Configuration

Before running the utility, make sure to properly set up the CSV files:

- Format of `user_query.csv` file present under `data` directory:
  - Include columns for ID, User_Query, expected_url, expected_ans, and expected_title (User_Query and Expected_Ans are mandatory).
  
- Format of `output.csv` file present under `output` directory:
  - The file should have the following headers:
    1. ID
    2. User_Query
    3. Expected_Ans
    4. Expected_URL
    5. Expected_Title
    6. Answer_Snippet (Retrieved_Ans)
    7. Actual_Title
    8. Actual_URLs
    9. Answer_Status
    10. URL_Status
    11. Title_Status
    12. Chunk_Text
    13. Chunk_Position
    14. Model_Used
- Obtain Unique IDs (host, stream_id, search_index_id, index_pipeline_id, query_pipeline_id, user_id, auth_token) and Auth token for your SA app by opening up SA-builder app from the network tab from the debug console (ctrl+shift+i)

## Installation and Usage

1. Start the embeddings server (if you want to use semantic match):
   - Go to the `embeddings_server` directory.
   - Install Python 3.8.10.
   - Download the ML model for semantic similarity:
      - git lfs install
      - git clone https://huggingface.co/sentence-transformers/multi-qa-mpnet-base-cos-v1
      - Keep the downloaded folder at root directory of the repo.
   - Run `python3 embeddings_server.py`.

2. Run the server for app and input CSV details:
   - Go to the `src` directory [cd src]
   - Install the required modules with `npm install` [ only if node_modules are not already present].
   - Update the credentials in `creds.json` file with the respective information from the SearchAssist application (e.g., host, stream_id, search_index_id, index_pipeline_id, query_pipeline_id, user_id, auth_token).
   - Keep embedings_model as false to avoid semantic similarity while testing the results.
   - In case of a fresh run, keep start_index = 0 and clear the output.csv file.
   - Run `node server_creds.js`.

3. Run the script to make SearchAssist calls and generate the result sheet:
   - In a new terminal go to the `src` directory .
   - Run `node src.js`.
