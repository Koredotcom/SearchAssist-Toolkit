from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    """Simple health check endpoint to verify the service is running."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)