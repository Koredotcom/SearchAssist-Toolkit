# RAG Evaluator

## Overview

This repo is designed to evaluate queries and ground truths using the Ragas and Crag evaluators. The evaluation can be performed using data from an Excel file and optionally fetching responses via the SearchAI API. The script supports both Ragas and Crag evaluations, and the results are saved to an output Excel file or can be stored in mongoDB.

## Installation

### Prerequisites

- Install new virtual environment(Recommended)
- Python 3.9.x
- Pip package manager

### Installing Packages

1. Ensure you have Python and pip installed. You can check this by running:
 ```sh
 python --version
 pip --version
 ```

2. Install the necessary packages by running:
 ```sh
 pip install -r requirements.txt
 ```

## Usage

### Command-Line Arguments

- `--input_file`: Path to the input Excel file (required).
- `--sheet_name`: Specific sheet name to evaluate (optional, defaults to all sheets).
- `--evaluate_ragas`: Run only Ragas evaluation (optional).
- `--evaluate_crag`: Run only Crag evaluation (optional).
- `--use_search_api`: Use SearchAssist API to fetch responses (optional).
- `--save_db`: Save the evaluation results to MongoDB (optional).
- `--llm_model`: Specify the LLM model to use for evaluation (optional) (To use azure openai model, set it to "azure").

### Running Your First Experiment

#### 🚀 NEW: High-Performance Batch Processing

The system now supports **asynchronous batch processing** for significantly improved performance when processing large datasets.

### Example 1: High-Performance Batch Processing (NEW)

Process large datasets efficiently with configurable batch processing:

1. **Basic batch processing** (recommended for most users):
```sh
python main.py --input_file your_file.xlsx --use_search_api --batch_size 10 --max_concurrent 5
```

2. **High-performance processing** (for powerful systems and APIs that allow higher concurrency):
```sh
python main.py --input_file your_file.xlsx --use_search_api --batch_size 20 --max_concurrent 10
```

3. **Conservative processing** (for rate-limited APIs):
```sh
python main.py --input_file your_file.xlsx --use_search_api --batch_size 5 --max_concurrent 2
```

**Performance Impact**: For 100 queries, batch processing reduces time from ~5-8 minutes to ~1-2 minutes! 🚀

### Example 2: Traditional Evaluation Methods

#### Using Both Ragas and Crag Evaluators with SearchAssist API

1. Prepare your Excel file with the following columns:
    - `query`: The query string.
    - `ground_truth`: The expected ground truth for the query.

2. Execute the script:
```sh
python main.py --input_file path/to/your/excel_file.xlsx --sheet_name "Sheet1" --use_search_api
```

#### Using only Ragas Evaluator without Search API

1. Prepare your Excel file with the following columns:
    - `query`: The query string.
    - `ground_truth`: The expected ground truth for the query.
    - `contexts`: A list of contexts (optional).
    - `answer`: The answer string (optional).

2. Execute the script:
```sh
python main.py --input_file path/to/your/excel_file.xlsx --evaluate_ragas
```

#### Advanced Usage with Azure OpenAI and Database Storage

```sh
python main.py --input_file path/to/your/excel_file.xlsx --evaluate_ragas --use_search_api --save_db --llm_model azure --batch_size 15 --max_concurrent 8
```

## 🔧 New Batch Processing Configuration

### Command-Line Arguments (NEW)

- `--batch_size`: Number of queries to process in each batch (default: 10)
- `--max_concurrent`: Maximum concurrent requests per batch (default: 5)

### Recommended Settings by Dataset Size

| Dataset Size | Batch Size | Max Concurrent | Expected Time (100 queries) |
|-------------|------------|----------------|----------------------------|
| Small (≤20) | 5 | 2 | ~30-60 seconds |
| Medium (21-100) | 10 | 5 | ~1-2 minutes |
| Large (100-500) | 15 | 8 | ~2-5 minutes |
| Very Large (500+) | 20 | 10 | ~5-15 minutes |

### 📊 Enhanced File Output Features (NEW)

The system now provides **robust file writing** with comprehensive error handling:

#### Multi-Sheet Output Structure
- **Main Results**: Each input sheet becomes an output sheet
- **Processing_Summary**: Detailed processing statistics
- **Processing_Metadata**: Configuration and timing information
- **Error Sheets**: Detailed error information for failed processes

#### File Integrity Features
- ✅ **Automatic backup creation** for existing files
- ✅ **Data validation** before writing
- ✅ **CSV fallback** if Excel writing fails
- ✅ **File integrity verification** after writing
- ✅ **Detailed progress tracking** and logging

#### Example Output Structure
```
your_file_evaluation_output_20240315-143022.xlsx
├── Sheet1 (Main results)
├── Sheet2 (Additional sheet results) 
├── Processing_Summary (Success/failure summary)
├── Processing_Metadata (Configuration details)
└── ERROR_Sheet3 (Error details if any sheet failed)
```
## Additional Details

### Output

The results are saved in the `./outputs` directory with a timestamped filename. The output file will contain the evaluation results for each sheet processed.

### API Key for OpenAI

Ensure that the `OPENAI_API_KEY` environment variable is set with your OpenAI API key before running the script:

Linux
```sh
export OPENAI_API_KEY="your_openai_api_key"
```
```sh
export AZURE_OPENAI_API_KEY="your_openai_api_key"
```
Windows
```sh
$env:OPENAI_API_KEY="your_openai_api_key"
```
```sh
$env:AZURE_OPENAI_API_KEY="your_openai_api_key"
```

###Configuration
Ensure the configuration file `config.json` is correctly set up and accessible.

####Setting Up config.json
Create a config.json file in the config directory with the necessary configuration settings. Below is an example of how your config.json file might look:

```json5
{
    "<UXO or SA>": {
        "app_id": "<UXO or SA stream ID>",
        "client_id": "<UXO or SA client ID>",
        "client_secret": "<UXO or SA client secret>",
        "domain": "<SA or UXO domain url>"
    },
    "openai": {
        "model_name": "<EVALUATION_MODEL_NAME>",
        "embedding_name": "<EVALUATION_EMBEDDING_NAME>"
    },
    // use this if you are using azure openai model
    "azure": {
        {
            "openai_api_version": "<your_openai_api_version>",
            "base_url": "<your_base_url>",
            "model_deployment": "<your_model_deployment>",
            "model_name": "<your_model_name>",
            "embedding_deployment": "<your_embedding_deployment>",
            "embedding_name": "<your_embedding_name>"
        }
    },
    "MongoDB": {
        "url": "<MONGO URL>",
        "dbName": "<DB NAME>",
        "collectionName": "<COLLECTION NAME>"
    }
    
}
```
Replace the placeholders with your actual values. 
- If saving to MongoDB, set `url`, `dbName`, and `collectionName` in the `MongoDB` section of the config.json file.

- for Azure openai model, set `EVALUATION_MODEL_NAME`, `openai_api_version`, `base_url`, `model_deployment`, `model_name`, `embedding_deployment`, `embedding_name`, `model_version` in config.json file.

```json5
{
    "openai_api_version": "v1",
    "base_url": "https://api.openai.com",
    "model_deployment": "azure",
    "model_name": "gpt-3.5-turbo",
    "model_version": "latest"
}
```

---

# API Documentation

## Overview

This FastAPI application provides two main endpoints: `/runeval` and `/mailService`. These endpoints allow users to run evaluations and send emails with the results, respectively.

## Endpoints

### 1. `/runeval`

#### Method: POST

**Summary**: Run Eval

**Description**: This endpoint allows users to run an evaluation based on the provided Excel file, config file, and parameters.

**Request Body**:
- **Content Type**: `application/json`
- **Schema**: `Body`
  - **Properties**:
    - `excel_file` (string): The path to the Excel file.
    - `config_file` (string): The path to the config file.
    - `params` (object): Evaluation parameters.
      - **Schema**: `Params`
        - **Properties**:
          - `sheet_name` (string): The name of the sheet in the Excel file.
          - `evaluate_ragas` (boolean): Whether to evaluate ragas. Default is `false`.
          - `evaluate_crag` (boolean): Whether to evaluate crag. Default is `false`.
          - `use_search_api` (boolean): Whether to use the search API. Default is `false`.
          - `llm_model` (string): The LLM model to use.
          - `save_db` (boolean): Whether to save the results to the database. Default is `false`.

**Responses**:
- **200**: Successful Response
  - **Content Type**: `application/json`
  - **Schema**: Empty object
- **422**: Validation Error
  - **Content Type**: `application/json`
  - **Schema**: `HTTPValidationError`
    - **Properties**:
      - `detail` (array): List of validation errors.
        - **Items**: `ValidationError`
          - **Properties**:
            - `loc` (array): Location of the error.
              - **Items**: `string` or `integer`
            - `msg` (string): Error message.
            - `type` (string): Error type.

### 2. `/mailService`

#### Method: POST

**Summary**: Mail Service

**Description**: This endpoint allows users to send an email with the evaluation results.

**Query Parameters**:
- `send_mail` (boolean): Whether to send the email. Default is `false`.

**Responses**:
- **200**: Successful Response
  - **Content Type**: `application/json`
  - **Schema**: Empty object
- **422**: Validation Error
  - **Content Type**: `application/json`
  - **Schema**: `HTTPValidationError`
    - **Properties**:
      - `detail` (array): List of validation errors.
        - **Items**: `ValidationError`
          - **Properties**:
            - `loc` (array): Location of the error.
              - **Items**: `string` or `integer`
            - `msg` (string): Error message.
            - `type` (string): Error type.

## Components

### Schemas

#### `Body`
- **Properties**:
  - `excel_file` (string): The path to the Excel file.
  - `config_file` (string): The path to the config file.
  - `params` (object): Evaluation parameters.
    - **Schema**: `Params`
      - **Properties**:
        - `sheet_name` (string): The name of the sheet in the Excel file.
        - `evaluate_ragas` (boolean): Whether to evaluate ragas. Default is `false`.
        - `evaluate_crag` (boolean): Whether to evaluate crag. Default is `false`.
        - `use_search_api` (boolean): Whether to use the search API. Default is `false`.
        - `llm_model` (string): The LLM model to use.
        - `save_db` (boolean): Whether to save the results to the database. Default is `false`.

#### `HTTPValidationError`
- **Properties**:
  - `detail` (array): List of validation errors.
    - **Items**: `ValidationError`
      - **Properties**:
        - `loc` (array): Location of the error.
          - **Items**: `string` or `integer`
        - `msg` (string): Error message.
        - `type` (string): Error type.

#### `Params`
- **Properties**:
  - `sheet_name` (string): The name of the sheet in the Excel file.
  - `evaluate_ragas` (boolean): Whether to evaluate ragas. Default is `false`.
  - `evaluate_crag` (boolean): Whether to evaluate crag. Default is `false`.
  - `use_search_api` (boolean): Whether to use the search API. Default is `false`.
  - `llm_model` (string): The LLM model to use.
  - `save_db` (boolean): Whether to save the results to the database. Default is `false`.

#### `ValidationError`
- **Properties**:
  - `loc` (array): Location of the error.
    - **Items**: `string` or `integer`
  - `msg` (string): Error message.
  - `type` (string): Error type.

---


## Future Improvements

- Add support for additional evaluators.
- Generate User friendly reports.
- Support for synthetic test data set generator.
- Support for custom LLMs(Claude etc).
- More to come....!

## Contributing

We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with clear and descriptive messages.
4. Push your changes to your fork.
5. Open a pull request with a detailed description of your changes.

For major changes, please open an issue first to discuss what you would like to change. This helps ensure that your contribution is aligned with the project's goals and avoids duplication of effort.