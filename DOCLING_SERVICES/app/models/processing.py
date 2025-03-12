from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import ImageRefMode
from pathlib import Path
import time
import logging
from typing import List, Dict
import app.config as config
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(config.MARKDOWN_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def ensure_logs_directory():
    """Ensure that the logs directory exists."""
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

def process_uploaded_file_sync(file_path: str) -> List[Dict]:
    """Synchronous version of process_uploaded_file"""
    # Set up pipeline options
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.table_structure_options.do_cell_matching = True
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False

    # Create converter instance
    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    chunks = []
    input_doc_path = Path(file_path)
    
    try:
        start_time = time.time()
        # Convert document
        logger.info(f"Started processing Document {file_path}")
        conv_result = doc_converter.convert(input_doc_path)
        end_time = time.time() - start_time
        logger.info(f"Document {file_path} converted in {end_time:.2f} seconds.")
        
        # Process each page
        for page_no, page in conv_result.document.pages.items():
            page_content = conv_result.document.export_to_markdown(
                image_mode=ImageRefMode.REFERENCED,
                page_no=page_no
            )
            chunk_obj = {
                'chunkText': page_content,
                'filename': str(input_doc_path.name),
                'page_number': page_no
            }
            chunks.append(chunk_obj)
            
        return chunks
    except Exception as e:
        logger.error(f"Error processing document {file_path}: {str(e)}")
        raise Exception(f"Error processing document: {str(e)}") 