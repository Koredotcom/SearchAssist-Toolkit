from fastapi import APIRouter, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import time
import logging
from app.services.file_processing import save_and_process_file
from datetime import datetime

router = APIRouter()

logger = logging.getLogger(__name__)

@router.post("/process-pdf-markdown/")
async def process_pdf_markdown(file: UploadFile) -> JSONResponse:
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    start_time = time.time()
    filename = file.filename
    logger.info(f"[MARKDOWN] Starting processing for file: {filename}")
    logger.info(f"[MARKDOWN] Start time: {datetime.fromtimestamp(start_time).isoformat()}")

    try:
        chunks = await save_and_process_file(file)
        processing_time = time.time() - start_time
        logger.info(f"[MARKDOWN] Completed processing for file: {filename}")
        logger.info(f"[MARKDOWN] Processing time: {processing_time:.2f} seconds")
        logger.info(f"[MARKDOWN] End time: {datetime.now().isoformat()}")

        return JSONResponse(content={"status": "success", "chunks": chunks}, status_code=200)

    except Exception as e:
        logger.error(f"[MARKDOWN] Error processing {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}") 