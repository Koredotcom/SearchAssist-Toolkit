from fastapi import APIRouter, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
import time
import logging
from app.services.file_processing import save_and_process_file, process_existing_file
from datetime import datetime
from typing import Optional
import os

router = APIRouter()

logger = logging.getLogger(__name__)

@router.get("/health-check")
async def health_check():
    """Simple health check endpoint to verify the service is running."""
    return JSONResponse(
        content={
            "status": "success",
            "message": "Service is healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "pdf-processing-service"
        },
        status_code=200
    )

@router.post("/process-pdf-markdown/")
async def process_pdf_markdown(
    file: Optional[UploadFile] = None, 
    file_path: Optional[str] = Form(None)
) -> JSONResponse:
    # Check if at least one input method is provided
    if not file and not file_path:
        raise HTTPException(
            status_code=400, 
            detail={
                "status": "error",
                "message": "Either file upload or file path must be provided",
                "timestamp": datetime.now().isoformat()
            }
        )

    start_time = time.time()
    
    try:
        # Process based on the input method
        if file:
            # Existing file upload flow
            if not file.filename.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "status": "error",
                        "message": "File must be a PDF",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
            filename = file.filename
            logger.info(f"[MARKDOWN] Starting processing for uploaded file: {filename}")
            logger.info(f"[MARKDOWN] Start time: {datetime.fromtimestamp(start_time).isoformat()}")
            chunks = await save_and_process_file(file)
        else:
            # New file path flow
            if not file_path.lower().endswith('.pdf'):
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "status": "error",
                        "message": "File must be a PDF",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
            filename = os.path.basename(file_path)
            logger.info(f"[MARKDOWN] Starting processing for file path: {filename}")
            logger.info(f"[MARKDOWN] Start time: {datetime.fromtimestamp(start_time).isoformat()}")
            chunks = await process_existing_file(file_path)
        
        processing_time = time.time() - start_time
        logger.info(f"[MARKDOWN] Completed processing for file: {filename}")
        logger.info(f"[MARKDOWN] Processing time: {processing_time:.2f} seconds")
        logger.info(f"[MARKDOWN] End time: {datetime.now().isoformat()}")

        return JSONResponse(
            content={
                "status": "success",
                "message": f"Successfully processed file: {filename}",
                "processing_time_seconds": round(processing_time, 2),
                "timestamp": datetime.now().isoformat(),
                "chunks": chunks,
                "metadata": {
                    "filename": filename,
                    "file_type": "pdf"
                }
            }, 
            status_code=200
        )

    except Exception as e:
        filename = file.filename if file else os.path.basename(file_path)
        logger.error(f"[MARKDOWN] Error processing {filename}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "status": "error",
                "message": f"Error processing file: {str(e)}",
                "timestamp": datetime.now().isoformat(),
                "filename": filename
            }
        ) 