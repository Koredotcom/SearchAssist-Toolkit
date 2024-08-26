# Intelligent PDF Chunking with Claude and GPT

## Project Description

This project provides a method to chunk PDFs based on their meaning using AI models Claude and GPT. The process involves extracting the PDF content, processing it with the selected AI model (Claude or GPT), generating rough chunks, and then post-processing these rough chunks into final meaningful chunks.

## Features

- **PDF Extraction**: Extracts content from PDF files.
- **AI Processing**: Uses Claude or GPT based on user preference to generate rough chunks of the PDF content.
- **Post-Processing**: Refines rough chunks into final, meaningful chunks.

## Architecture Diagram

![My Image](Arch-Diagram.jpg)

## Installation

To get started, clone the repository and install the necessary dependencies.

```bash
git clone https://github.com/rahul-kore/chunking-llm.git
cd chunking-llm
pip install -r requirements.txt
```

## Usage

1. **Extract PDF**: Extract content from the PDF file.
2. **AI Model Selection**: Choose between Claude or GPT for processing.
3. **Chunk Generation**: Generate rough chunks using the selected AI model.
4. **Post-Processing**: Refine rough chunks into final chunks.

you can use either 

```bash
resources.chunking_by_GPT.app.chunk_single_pdf

def chunk_single_pdf(timer: bool, pdf_path: str, display_flag=False, save_flag=True)
```

or 

```bash
resources.chunking_by_GPT.app.chunk_multiple_pdf

def chunk_multiple_pdf(timer: bool, folder_path: str, display_flag=False, save_flag=True)
```


## Google Colab Notebook

The Colab notebook demonstrates the steps to chunk PDFs intelligently:

1. **Upload PDF**: Upload the PDF file you want to chunk.
2. **Extract Content**: Use the provided code to extract the content.
3. **Select AI Model**: Choose either Claude or GPT for chunking.
4. **Generate Rough Chunks**: Run the code to generate rough chunks.
5. **Post-Process Chunks**: Refine the rough chunks into final meaningful chunks.