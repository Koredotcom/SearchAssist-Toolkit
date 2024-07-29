# RAG Evaluator

## Overview

This repo is designed to evaluate queries and ground truths using the Ragas and Crag evaluators. The evaluation can be performed using data from an Excel file and optionally fetching responses via the SearchAI API. The script supports both Ragas and Crag evaluations, and the results are saved to an output Excel file.

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

Sure, here is a revised version of the specific block you provided:

### Running Your First Experiment

### Example 1: Using Both Ragas and Crag Evaluators with SearchAssist API

To run an evaluation on a specific sheet using both Ragas and Crag evaluators and the SearchAssist API, follow these steps:

1. Prepare your Excel file with the following columns:
    - `query`: The query string.
    - `ground_truth`: The expected ground truth for the query.

2. Execute the script with the following command:

```sh
python main.py --input_file path/to/your/excel_file.xlsx --sheet_name "Sheet1" --use_search_api
```
### Example 2: Using only Ragas Evaluator and without Search AI API

To run an evaluation using the Ragas evaluator, follow these steps:

1. Prepare your Excel file with the following columns:
    - `query`: The query string.
    - `ground_truth`: The expected ground truth for the query.
    - `contexts`: A list of contexts (optional).
    - `answer`: The answer string (optional).

2. Execute the script with the following command:

```sh
python main.py --input_file path/to/your/excel_file.xlsx --evaluate_ragas
```
## Additional Details

### Output

The results are saved in the `./outputs` directory with a timestamped filename. The output file will contain the evaluation results for each sheet processed.

### API Key for OpenAI

Ensure that the `OPENAI_API_KEY` environment variable is set with your OpenAI API key before running the script:

```sh
export OPENAI_API_KEY="your_openai_api_key"
```

###Configuration
Ensure the configuration file `config.json` is correctly set up and accessible.

####Setting Up config.json
Create a config.json file in the config directory with the necessary configuration settings. Below is an example of how your config.json file might look:

```json5
{
    "auth_token":"<SA API token>",
    "app_id":"<SA stream ID>",
    "EVALUATION_MODEL_NAME": "<Model to evaluate>"
}
```
Replace `EVALUATION_MODEL_NAME` with the actual name of your model, and replace `app_id` and `auth_token` with the `streamId` and `JWT auth token` of your Search AI application.

## Future Improvements

- Add support for additional evaluators.
- Generate User friendly reports.
- Support for synthetic test data set generator.
- Support for custom LLMs(Azure, Claude etc).
- More to come....!

## Contributing

We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Make your changes and commit them with clear and descriptive messages.
4. Push your changes to your fork.
5. Open a pull request with a detailed description of your changes.

For major changes, please open an issue first to discuss what you would like to change. This helps ensure that your contribution is aligned with the project's goals and avoids duplication of effort.
