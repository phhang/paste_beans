"""FastAPI backend server for Paste Beans application."""

import os
import sys
import logging
import traceback
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import uvicorn

from config import settings
from vector_db import VectorDatabase
from rag_service import RAGService
from azure_openai_service import AzureOpenAIService
from logger import setup_logging, log_exception

# Create logger
logger = setup_logging(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="Paste Beans API",
    description="Convert bank statement screenshots to Beancount entries with RAG",
    version="1.0.0",
    debug=settings.debug  # Enable FastAPI debug mode
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
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
        # Return full stack trace in debug mode
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": traceback.format_exc().split('\n')
            }
        )
    else:
        # Return sanitized error in production
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
vector_db: Optional[VectorDatabase] = None
rag_service: Optional[RAGService] = None
azure_openai_service: Optional[AzureOpenAIService] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global vector_db, rag_service, azure_openai_service

    logger.info("=" * 60)
    logger.info("Starting Paste Beans server")
    logger.info("=" * 60)

    if settings.debug:
        logger.debug("Debug mode enabled - verbose logging active")
        logger.debug("Configuration:")
        logger.debug(f"  Host: {settings.host}")
        logger.debug(f"  Port: {settings.port}")
        logger.debug(f"  Azure OpenAI Endpoint: {settings.azure_openai_endpoint}")
        logger.debug(f"  Chroma DB: {settings.chroma_persist_directory}")

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

    # Initialize vector database
    try:
        vector_db = VectorDatabase(settings.chroma_persist_directory)
        logger.info(f"Vector database initialized at: {settings.chroma_persist_directory}")
    except Exception as e:
        log_exception(logger, e, "Failed to initialize vector database")
        raise

    # Initialize RAG service
    rag_service = RAGService(vector_db)
    logger.info("RAG service initialized")

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

    # Check for existing .bean files and offer to ingest them
    bean_dir = settings.bean_files_directory
    if os.path.exists(bean_dir):
        bean_files = [f for f in os.listdir(bean_dir) if f.endswith('.bean')]
        if bean_files:
            logger.info(f"Found {len(bean_files)} .bean files in {bean_dir}")
            logger.info("Ingesting existing files into vector database...")

            try:
                results = vector_db.ingest_directory(bean_dir)
                total_entries = sum(results.values())
                logger.info(f"Ingested {total_entries} total entries from {len(results)} files")

                if settings.debug:
                    for filename, count in results.items():
                        logger.debug(f"  {filename}: {count} entries")

            except Exception as e:
                log_exception(logger, e, "Error ingesting bean files")

    # Print collection stats
    stats = vector_db.get_collection_stats()
    logger.info("Vector database stats:")
    logger.info(f"  Total entries: {stats['total_entries']}")

    logger.info("=" * 60)
    logger.info("Server ready!")
    logger.info("=" * 60)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Paste Beans API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    if vector_db is None or rag_service is None:
        raise HTTPException(status_code=503, detail="Services not initialized")

    stats = vector_db.get_collection_stats()

    return {
        "status": "healthy",
        "azure_openai_configured": settings.validate_azure_config(),
        "vector_db_entries": stats['total_entries']
    }


@app.post("/api/generate-beancount")
async def generate_beancount(
    image: UploadFile = File(...),
    account_name: str = Form(...)
):
    """Generate Beancount entry from screenshot.

    Args:
        image: Screenshot image file
        account_name: Account name to use in the entry

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

        # Process each transaction and generate Beancount entries
        results = []
        for idx, transaction_data in enumerate(transactions_list, 1):
            # Get merchant name for RAG
            merchant = transaction_data.get('merchant', 'UNKNOWN')

            logger.info(f"Processing transaction {idx}/{len(transactions_list)}: {merchant}")

            # Build RAG prompt with historical context
            logger.debug("Building RAG context...")
            rag_prompt = rag_service.build_rag_prompt(
                merchant_name=merchant,
                date=transaction_data.get('date'),
                amount=transaction_data.get('amount'),
                account_name=account_name
            )

            if settings.debug:
                logger.debug(f"RAG prompt:\n{rag_prompt}")

            # Generate Beancount entry
            logger.info("Generating Beancount entry...")
            beancount_entry = azure_openai_service.generate_beancount_with_context(
                transaction_data,
                rag_prompt
            )

            logger.info(f"Generated entry for {merchant}")
            if settings.debug:
                logger.debug(f"Entry:\n{beancount_entry}")

            results.append({
                "extracted_data": transaction_data,
                "beancount_entry": beancount_entry,
                "rag_context_used": merchant != 'UNKNOWN'
            })

        # Optionally: Add the new entries to vector database for future RAG
        # (commented out by default to avoid polluting the database with unverified entries)
        # for result in results:
        #     vector_db.add_entry(result['beancount_entry'])

        logger.info(f"Successfully processed {len(results)} transaction(s)")

        return {
            "success": True,
            "transactions_count": len(results),
            "results": results
        }

    except Exception as e:
        log_exception(logger, e, "Error generating beancount entry")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-bean-file")
async def ingest_bean_file(file: UploadFile = File(...)):
    """Ingest a .bean file into the vector database.

    Args:
        file: .bean file to ingest

    Returns:
        JSON with ingestion results
    """
    if not file.filename.endswith('.bean'):
        raise HTTPException(
            status_code=400,
            detail="Only .bean files are supported"
        )

    try:
        # Save file temporarily
        temp_path = os.path.join(settings.bean_files_directory, file.filename)
        os.makedirs(settings.bean_files_directory, exist_ok=True)

        content = await file.read()

        with open(temp_path, 'wb') as f:
            f.write(content)

        # Ingest file
        count = vector_db.ingest_bean_file(temp_path)

        # Get updated stats
        stats = vector_db.get_collection_stats()

        return {
            "success": True,
            "filename": file.filename,
            "entries_added": count,
            "total_entries": stats['total_entries']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest-directory")
async def ingest_directory():
    """Ingest all .bean files from the data directory.

    Returns:
        JSON with ingestion results
    """
    try:
        results = vector_db.ingest_directory(settings.bean_files_directory)
        stats = vector_db.get_collection_stats()

        return {
            "success": True,
            "files_processed": results,
            "total_entries": stats['total_entries']
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/merchant-context/{merchant_name}")
async def get_merchant_context(merchant_name: str):
    """Get historical context for a merchant.

    Args:
        merchant_name: Name of the merchant

    Returns:
        JSON with merchant context and suggestions
    """
    try:
        context = rag_service.get_merchant_context(merchant_name)
        return context

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
async def get_stats():
    """Get vector database statistics.

    Returns:
        JSON with database statistics
    """
    try:
        stats = vector_db.get_collection_stats()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files for frontend
# Get the absolute path to the frontend directory
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """Serve frontend files. Catch-all route for SPA."""
        # Skip API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        # Try to serve the requested file
        file_path = os.path.join(frontend_path, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)

        # Default to index.html for SPA routing
        index_path = os.path.join(frontend_path, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)

        raise HTTPException(status_code=404, detail="File not found")


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
        reload=settings.debug,  # Only reload in debug mode
        log_level="debug" if settings.debug else "info"
    )
