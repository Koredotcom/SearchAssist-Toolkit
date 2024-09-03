# Intelligent PDF Chunking with Claude and GPT

## Project Description

This project provides a method to chunk PDFs based on their meaning using AI models Claude and GPT. The process involves extracting the PDF content, processing it with the selected AI model (Claude or GPT), generating rough chunks, and then post-processing these rough chunks into final meaningful chunks.

## Features

- **PDF Extraction**: Extracts content from PDF files.
- **AI Processing**: Uses Claude or GPT based on user preference to generate rough chunks of the PDF content.
- **Post-Processing**: Refines rough chunks into final, meaningful chunks.

Refer .idea\intelligent.md for more info!!

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
from resources.ChunkingByGPT.app import CHunkingByGPT

chunker = CHunkingByGPT('Your Key Here','Your Model name here')

'''exapmle to chunk single PDF''' 
chunker.chunk_single_pdf(timer=True,pdf_path=r'Sample File path',display_flag=False,save_flag=True)
```

or 

```bash
from resources.ChunkingByGPT.app import CHunkingByGPT

chunker = CHunkingByGPT('Your Key Here','Your Model name here')

'''exapmle to chunk Multiple PDF''' 
chunker.chunk_multiple_pdf(timer=True,folder_path=r'Sample Folder Path',display_flag=False,save_flag=True)
```