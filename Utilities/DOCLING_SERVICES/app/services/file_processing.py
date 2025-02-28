import os
import tempfile
import asyncio
from fastapi import UploadFile
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict
from app.models.processing import process_uploaded_file_sync
import app.config as config
import shutil

# Create a process pool for concurrent CPU-bound processing
process_pool = ProcessPoolExecutor(max_workers=config.PDF_THREAD_POOL_SIZE)

async def save_and_process_file(file: UploadFile) -> List[Dict]:
    """Save the uploaded file and process it."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, file.filename)
        save_uploaded_file(file, temp_file_path)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(process_pool, process_uploaded_file_sync, temp_file_path)

def save_uploaded_file(file: UploadFile, destination: str) -> None:
    """Save the uploaded file to the specified destination."""
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer) 