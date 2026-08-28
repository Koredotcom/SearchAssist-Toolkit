import os
import tempfile
import asyncio
from fastapi import UploadFile
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict
from app.models.processing import process_uploaded_file_sync, ensure_logs_directory
import app.config as config
import shutil
import uuid
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Create a process pool for concurrent CPU-bound processing
process_pool = ProcessPoolExecutor(max_workers=config.PDF_THREAD_POOL_SIZE)

# Create a single temporary directory for all file processing
TEMP_DIR = tempfile.mkdtemp(prefix="pdf_processing_")

# Ensure the temporary directory exists
def ensure_temp_directory():
    """Ensure that the temporary directory exists."""
    try:
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
            logger.info(f"Created temporary directory: {TEMP_DIR}")
        return True
    except Exception as e:
        logger.error(f"Failed to create temporary directory: {str(e)}")
        return False

# Call this at startup
ensure_temp_directory()

async def save_and_process_file(file: UploadFile) -> List[Dict]:
    """Save the uploaded file and process it."""
    # Generate a unique filename to avoid collisions
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    temp_file_path = os.path.join(TEMP_DIR, unique_filename)
    
    logger.info(f"Processing uploaded file: {file.filename}")
    logger.info(f"Temporary file path: {temp_file_path}")
    
    try:
        # Save the file
        try:
            save_uploaded_file(file, temp_file_path)
            logger.info(f"File saved successfully to {temp_file_path}")
        except Exception as e:
            logger.error(f"Failed to save file {file.filename}: {str(e)}")
            raise Exception(f"Failed to save file: {str(e)}")
        
        # Process the file
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(process_pool, process_uploaded_file_sync, temp_file_path)
            logger.info(f"Successfully processed file: {file.filename}")
            return result
        except Exception as e:
            logger.error(f"Error during file processing for {file.filename}: {str(e)}")
            raise Exception(f"Error during file processing: {str(e)}")
    finally:
        # Clean up the file after processing
        try:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {temp_file_path}: {str(e)}")

async def process_existing_file(file_path: str) -> List[Dict]:
    """Process an existing file at the given path."""
    logger.info(f"Processing existing file at path: {file_path}")
    
    # Verify file exists
    if not os.path.exists(file_path):
        error_msg = f"File not found at path: {file_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(process_pool, process_uploaded_file_sync, file_path)
        logger.info(f"Successfully processed existing file: {file_path}")
        return result
    except Exception as e:
        logger.error(f"Error processing existing file {file_path}: {str(e)}")
        raise Exception(f"Error processing existing file: {str(e)}")

def save_uploaded_file(file: UploadFile, destination: str) -> None:
    """Save the uploaded file to the specified destination."""
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving file to {destination}: {str(e)}")
        raise Exception(f"Error saving file: {str(e)}") 