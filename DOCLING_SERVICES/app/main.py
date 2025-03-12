from fastapi import FastAPI
import uvicorn
from app.routes.pdf_processing import router as pdf_router
from app.routes.health import router as health_router
from app.utils.logger import setup_logger
import app.config as config

# Initialize FastAPI app
app = FastAPI(
    title="PDF Markdown Service",
    description="Service for converting PDF files to markdown format",
    version="1.0.0"
)

# Setup logger
logger = setup_logger('markdown-service')

# Include routes
app.include_router(pdf_router)
app.include_router(health_router)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting PDF Markdown Service on {config.HOST}:{config.MARKDOWN_SERVICE_PORT}")
    logger.info(f"Thread pool size: {config.PDF_THREAD_POOL_SIZE}")

if __name__ == "__main__":
    try:
        uvicorn.run(
            app,
            host=config.HOST,
            port=config.MARKDOWN_SERVICE_PORT,
            log_config=None  # Use our custom logging config
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise 