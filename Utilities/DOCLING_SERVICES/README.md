# DOCLING_SERVICES

## Overview

DOCLING_SERVICES is a FastAPI-based application designed to process PDF files and convert them into Markdown format. It leverages the Docling library for efficient document conversion and provides a simple API for seamless integration.

## Features

- **PDF to Markdown Conversion:** Easily convert PDF documents to Markdown.
- **Concurrent Processing:** Handles multiple PDF processing tasks concurrently.
- **Configurable Settings:** Customize host, port, and other parameters via `config.json` or environment variables.
- **Logging:** Comprehensive logging for monitoring and debugging.

## Setup

### Prerequisites

- Python 3.8 or higher
- Git

**Configure Environment (Optional)**
   
   Customize settings by editing `config.json` or setting environment variables. Default configurations are provided in `config.json`.

## Running the Service

### Using the Setup Script

Execute the setup and run the service:

1. **Clone the Repository**
    ```bash
    git clone <repository-url>
    cd DOCLING_SERVICES
    ```

2. **Install Dependencies**
    ```bash
    ./setup.sh
    ```

### Manually Starting the Service

Ensure the virtual environment is activated, then run:
```bash
python -m app.main
```

The service will start on the host and port specified in `config.json` (default is `0.0.0.0:8000`).

## Usage

### API Endpoint

- **POST** `/process-pdf-markdown/`

    Upload a PDF file to convert it into Markdown format.

### Example `curl` Command

```bash
1. Using File Path (Already on Server)
curl -X POST "http://localhost:8000/process-pdf-markdown/" \
  -H "Content-Type: multipart/form-data" \
  -F "file_path=/tmp/already_uploaded/document.pdf"

2. Using Form Data (File Upload)
curl -X POST "http://localhost:8000/process-pdf-markdown/" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/your/document.pdf"
```

### Response Format

Upon successful processing, the API returns a JSON response:

```json
{
  "status": "success",
  "chunks": [
    {
      "chunkText": "Markdown content of page 1",
      "filename": "document.pdf",
      "page_number": 1
    },
    {
      "chunkText": "Markdown content of page 2",
      "filename": "document.pdf",
      "page_number": 2
    }
    // ... more pages
  ]
}
```

### Error Handling

If an error occurs during processing, the API responds with an appropriate HTTP status code and error message.

    

## Logging

Logs are stored in the `logs/` directory by default. You can monitor the `markdown_service.log` file for detailed insights into the application's operations.

## Configuration

Settings can be adjusted in the `config.json` file or via environment variables. Key configurations include:

- `HOST`: Server host (default: `0.0.0.0`)
- `MARKDOWN_SERVICE_PORT`: Server port (default: `8000`)
- `PDF_THREAD_POOL_SIZE`: Number of worker threads for PDF processing (default: `3`)
- `LOGS_DIR`: Directory for log files (default: `logs`)
- `MARKDOWN_LOG_FILE`: Log file name (default: `markdown_service.log`)

## License
Kore.ai
