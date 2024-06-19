# HTML to Structured Data Extractor

This Python script is designed to extract structured data from HTML content. It takes an input directory containing JSON files or HTML files, processes the content, and saves the extracted structured data in JSON format to an output directory.

## Prerequisites

- Python 3.9.7
- Required Python packages (listed in the `requirements.txt` file)

## Installation

1. Clone the repository or download the source code.
2. Install the required Python packages by running the following command:
   - pip install -r requirements.txt
3. Obtain an OpenAI API key and set it as an environment variable named `OPENAI_KEY`.

## Usage

The script can be run from the command line with optional arguments to specify the input and output directories. 
If no arguments are provided, the default input directory is `./data/input/`, and the default output directory is `./data/output/`.
 - python main.py [input_directory_path] [output_directory_path]
- `input_directory_path`: The path to the directory containing the input JSON or HTML files.
- `output_directory_path`: The path to the directory where the output JSON files will be saved.

### Input File Format

The script supports two types of input files:

1. **JSON files**: The script expects the JSON files to contain a nested structure with HTML content. It will extract the HTML content from the JSON file and process it. Sample input files are provided in the `data/input/` directory.

2. **HTML files**: If HTML files are present in the input directory at `./data/input/html/`, the script will process them directly.

### Output File Format

The script will generate JSON files containing the extracted structured data. Each output file will have the same name as the corresponding input file, with the extension `_chunks.json`. Sample output files are provided in the `data/output/` directory.

## Code Overview

1. The script imports the required libraries and sets up the OpenAI configuration.
2. It defines helper functions for parsing HTML and JSON files, cleaning JSON data, extracting table of contents, handling OpenAI responses, and fetching the lookup table from the OpenAI response.
3. The `extract_chunks` function is the main function that processes the HTML content, extracts structured data using the OpenAI API, and converts the data to the desired format.
4. The `save_json` function saves the extracted data to a JSON file in the output directory.
5. The `helper` function is the entry point of the script. It handles command-line arguments, processes the input files, and saves the output files.

## Requirements

The required Python packages are listed in the `requirements.txt` file