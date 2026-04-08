"""FastAPI backend server for Paste Beans application (simplified, no vector DB)."""

import os
import traceback
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn

from config import settings
from azure_openai_service import AzureOpenAIService
from logger import setup_logging, log_exception

# Create logger
logger = setup_logging(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Paste Beans API",
    description="Convert bank statement screenshots to Beancount entries",
    version="2.0.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Custom exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that shows stack traces in debug mode."""
    logger.error(f"Unhandled exception on {request.url.path}: {str(exc)}")

    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc().split('\n')
            }
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP exception handler with debug details."""
    logger.warning(f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}")

    response_content = {
        "error": exc.detail,
        "status_code": exc.status_code
    }

    if settings.debug:
        response_content["path"] = str(request.url)
        response_content["method"] = request.method

    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )


# Initialize services
azure_openai_service: Optional[AzureOpenAIService] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global azure_openai_service

    logger.info("=" * 60)
    logger.info("Starting Paste Beans server (no-vector-db mode)")
    logger.info("=" * 60)

    if settings.debug:
        logger.debug("Debug mode enabled - verbose logging active")
        logger.debug("Configuration:")
        logger.debug(f"  Host: {settings.host}")
        logger.debug(f"  Port: {settings.port}")
        logger.debug(f"  Azure OpenAI Endpoint: {settings.azure_openai_endpoint}")

    logger.info("Initializing services...")

    # Validate Azure OpenAI configuration
    if not settings.validate_azure_config():
        logger.warning("Azure OpenAI configuration is incomplete!")
        logger.warning("Please set the following environment variables in .env:")
        logger.warning("  - AZURE_OPENAI_API_KEY")
        logger.warning("  - AZURE_OPENAI_ENDPOINT")
        logger.warning("  - AZURE_OPENAI_DEPLOYMENT_NAME")
        logger.warning("The server will start but API calls will fail.")
        logger.warning("Copy .env.example to .env and fill in your credentials.")

    # Initialize Azure OpenAI service
    try:
        azure_openai_service = AzureOpenAIService(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment_name=settings.azure_openai_deployment_name,
            api_version=settings.azure_openai_api_version
        )
        logger.info("Azure OpenAI service initialized")

        if settings.debug:
            logger.debug(f"  Deployment: {settings.azure_openai_deployment_name}")
            logger.debug(f"  API Version: {settings.azure_openai_api_version}")

    except Exception as e:
        log_exception(logger, e, "Could not initialize Azure OpenAI service")
        azure_openai_service = None

    logger.info("=" * 60)
    logger.info("Server ready!")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Paste Beans API",
        "version": "2.0.0",
        "mode": "no-vector-db",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "mode": "no-vector-db",
        "azure_openai_configured": settings.validate_azure_config()
    }


@app.post("/api/generate-beancount")
async def generate_beancount(
    image: UploadFile = File(...),
    account_name: str = Form(...)
):
    """Generate Beancount entry from screenshot.

    Args:
        image: Screenshot image file
        account_name: Account name to use in the entry (e.g., "Assets:Bank:Checking")

    Returns:
        JSON with generated Beancount entry
    """
    if azure_openai_service is None:
        raise HTTPException(
            status_code=503,
            detail="Azure OpenAI service not configured. Please check your .env file."
        )

    try:
        # Read image bytes
        image_bytes = await image.read()

        logger.info(f"Processing screenshot for account: {account_name}")
        if settings.debug:
            logger.debug(f"Image size: {len(image_bytes)} bytes")

        # Extract transaction data from screenshot
        logger.info("Extracting transaction data from screenshot...")
        transactions_list = azure_openai_service.extract_transaction_from_screenshot(
            image_bytes
        )

        logger.info(f"Extracted {len(transactions_list)} transaction(s)")
        if settings.debug:
            logger.debug(f"Transactions: {transactions_list}")

        # Generate all Beancount entries in a single API call
        logger.info("Generating Beancount entries...")
        beancount_entries = azure_openai_service.generate_beancount_entries(
            transactions_list,
            account_name
        )

        logger.info(f"Generated {len(beancount_entries)} entries")

        # Pair extracted data with generated entries
        results = []
        for idx, transaction_data in enumerate(transactions_list):
            entry = beancount_entries[idx] if idx < len(beancount_entries) else "Error: No entry generated"
            if settings.debug:
                logger.debug(f"Entry {idx + 1}:\n{entry}")
            results.append({
                "extracted_data": transaction_data,
                "beancount_entry": entry
            })

        logger.info(f"Successfully processed {len(results)} transaction(s)")

        return {
            "success": True,
            "transactions_count": len(results),
            "results": results
        }

    except Exception as e:
        log_exception(logger, e, "Error generating beancount entry")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Starting Paste Beans server...")
    logger.info(f"Access the application at: http://{settings.host}:{settings.port}")
    logger.info(f"API docs at: http://{settings.host}:{settings.port}/docs")

    if settings.debug:
        logger.info("Debug mode: ENABLED")
        logger.debug("Uvicorn will run with reload=True")

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )
