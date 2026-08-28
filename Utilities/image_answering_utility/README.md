PDF Processor
==============

Overview:
---------
PDF Processor is a service for processing PDF files. It supports both individual PDF processing and batch processing of directories containing multiple PDFs. The service can also extract PDFs from archives (e.g., ZIP files) and integrates with MongoDB and AWS services.

Features:
---------
- Process single PDF files or entire directories.
- Automatically extract PDFs from ZIP or other archive formats (.tar, .gz, .tgz).
- Asynchronous processing with a configurable maximum number of concurrent tasks (set via the MAX_CONCURRENT_PROCESSING environment variable).
- MongoDB integration for tracking processing status.
- Logging for monitoring and error handling.
- Convert PDF pages into markdown representations and corresponding image snapshots.
- Upload processed results and generated images to AWS S3 for URL generation.

Tech Stack:
-----------
- Node.js, Express
- MongoDB & Mongoose
- AWS SDK (S3, etc.)
- Various utilities: axios, bull, pdf2pic, extract-zip, and more

Setup:
------
1. Clone the repository.
2. (Optional) Initialize or install MongoDB using:
   - `npm run init-mongodb`
   - `npm run install-mongodb`
3. Make the setup scripts executable: run `chmod +x setup/*.sh`
4. Start the API service by running `./setup/start_api_service.sh`

Example cURL Commands:
------------------------
To test the API endpoint for processing a PDF from a URL without base64 encoding, run:

curl -X POST http://localhost:3000/process-directory-from-url \
  -H "Content-Type: application/json" \
  -d '{"downloadUrl": "https://censusindia.gov.in/nada/index.php/catalog/28594/download/31776/50187_1961_DEM.pdf", "include_base64": false}'

Directory Structure:
--------------------
- src/
  - api/            : API layer (server.js, etc.)
  - services/       : PDF processing and image service implementations
  - scripts/        : Utility and setup scripts
  - config/         : Configuration files (including environment variables)
- utils/             : Helper utilities
- storage/           : Temporary directories and file storage


