# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Paste Beans is a web application that converts bank statement screenshots to Beancount accounting entries using Azure OpenAI Vision and RAG (Retrieval-Augmented Generation) for maintaining consistency with historical transactions.

**Tech Stack:**
- **Backend**: FastAPI (Python) with uvicorn
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **AI**: Azure OpenAI (GPT-4 Vision for OCR, chat completions for generation)
- **Vector DB**: ChromaDB for RAG context
- **Accounting**: Beancount format

## Development Commands

### Starting the Server

```bash
# Start server (handles venv creation, dependencies, and startup)
./start.sh

# Start manually (from backend directory)
cd backend
python main.py

# With debug mode (verbose logging, stack traces)
cd backend
python main.py --debug
```

### Running Tests

There are currently no automated tests in this project.

### Managing Dependencies

```bash
cd backend
pip install package_name
pip freeze > requirements.txt
```

## Architecture

### Request Flow

```
1. User pastes screenshot in frontend
2. Frontend sends image + account name to FastAPI
3. Backend:
   a. Azure OpenAI Vision extracts transaction data (date, merchant, amount)
   b. RAGService queries ChromaDB for similar historical entries
   c. Azure OpenAI generates Beancount entry with RAG context
4. Frontend displays formatted entry for user to copy
```

### Core Components

**Backend Services** (in `backend/`):

- **main.py**: FastAPI application with endpoints. Orchestrates the entire flow from image upload to Beancount generation.

- **azure_openai_service.py**: Handles all Azure OpenAI API calls:
  - `extract_transaction_from_screenshot()`: Vision API to extract transaction fields from images
  - `generate_beancount_with_context()`: Chat completion API to generate Beancount entries using RAG prompts

- **vector_db.py**: ChromaDB wrapper for storing/retrieving Beancount entries:
  - `parse_beancount_entry()`: Parses Beancount text to extract payee, category, accounts
  - `add_entry()`: Adds parsed entry to vector database
  - `search_similar()`: Semantic search for similar transactions
  - `ingest_bean_file()` / `ingest_directory()`: Batch import of .bean files

- **rag_service.py**: RAG logic for maintaining consistency:
  - `get_merchant_context()`: Finds historical entries for a merchant
  - `build_rag_prompt()`: Constructs prompt with historical examples
  - Determines most common payee name and expense category from history

- **config.py**: Environment variable management using python-dotenv
  - Validates Azure OpenAI configuration
  - Supports CLI arguments (`--debug`, `--verbose`)

- **logger.py**: Centralized logging with debug mode support

**Frontend** (in `frontend/`):

- **index.html**: Main UI with paste area for screenshots
- **script.js**: Handles image paste, API calls, result display
- **style.css**: Styling

**Data Storage**:

- `data/bean_files/`: Directory where user places existing .bean files for ingestion
- `data/chroma_db/`: ChromaDB persistent storage (auto-generated)

## Key Concepts

### RAG (Retrieval-Augmented Generation)

The application uses RAG to maintain consistency across Beancount entries:

1. **Ingestion**: On startup, all `.bean` files in `data/bean_files/` are parsed and stored in ChromaDB with embeddings
2. **Retrieval**: When processing a new transaction, the merchant name is used to search for similar historical entries (semantic search)
3. **Augmentation**: Historical examples are added to the prompt sent to Azure OpenAI
4. **Generation**: LLM generates entry matching the user's historical patterns

**Benefits:**
- Standardizes merchant names (e.g., "AMZN Marketplace" → "Amazon")
- Maintains consistent expense categories
- Follows user's formatting conventions

### Beancount Entry Format

Standard Beancount transaction format parsed by the system:

```
YYYY-MM-DD * "Payee" "Narration"
  Expenses:Category:Subcategory    XX.XX USD
  Assets:Bank:Checking            -XX.XX USD
```

The parser (`vector_db.py:parse_beancount_entry()`) uses regex to extract:
- Date (YYYY-MM-DD)
- Payee (first quoted string)
- Narration (second quoted string, optional)
- Accounts (lines starting with Expenses:, Assets:, Liabilities:, Income:, Equity:)
- Expense category (first Expenses: account found)

## API Endpoints

**Primary Endpoints:**

- `POST /api/generate-beancount` - Main endpoint: upload screenshot + account name, get Beancount entry
  - Form data: `image` (file), `account_name` (string)
  - Returns: extracted transaction data + generated Beancount entry + RAG context flag

**Management Endpoints:**

- `POST /api/ingest-bean-file` - Upload single .bean file to add to vector DB
- `POST /api/ingest-directory` - Re-ingest all files from `data/bean_files/`
- `GET /api/merchant-context/{name}` - Get historical context for a merchant
- `GET /api/stats` - Vector database statistics (entry count)
- `GET /api/health` - Health check (includes Azure OpenAI config status)

**Documentation:**

- `GET /docs` - Swagger/OpenAPI documentation (auto-generated by FastAPI)

## Configuration

All configuration via `.env` file (copy from `.env.example`):

**Required:**
```env
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision
```

**Optional:**
```env
AZURE_OPENAI_API_VERSION=2024-02-15-preview
CHROMA_PERSIST_DIRECTORY=./data/chroma_db
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

**Validation:**

On startup, `config.py:validate_azure_config()` checks for required fields. Server will start but API calls will fail if Azure OpenAI is not configured.

## Common Patterns

### Adding a New API Endpoint

1. Add endpoint function in `main.py` with `@app.get()` or `@app.post()` decorator
2. Use dependency injection for services (global `vector_db`, `rag_service`, `azure_openai_service`)
3. Wrap in try/except with `HTTPException` for errors
4. Use `logger.info()` for important steps, `logger.debug()` for details
5. Return JSON response (FastAPI auto-serializes)

### Modifying RAG Behavior

Key function: `rag_service.py:build_rag_prompt()`

This function constructs the prompt sent to Azure OpenAI. Modifications here affect:
- How historical context is presented
- What instructions are given to the LLM
- Consistency requirements

### Changing Transaction Extraction

Key function: `azure_openai_service.py:extract_transaction_from_screenshot()`

The `extraction_prompt` variable defines what the Vision API should extract. Current fields:
- date (YYYY-MM-DD format)
- merchant (payee name)
- amount (with currency)
- description (optional notes)

LLM returns JSON array (supports multiple transactions per screenshot).

### Updating Beancount Parser

Key function: `vector_db.py:parse_beancount_entry()`

Uses regex to parse Beancount format. If modifying:
- Update `pattern` for transaction header
- Update `account_pattern` for posting lines
- Test with various Beancount entry formats

## Debug Mode

Enable with `--debug` flag or `DEBUG=true` in `.env`:

```bash
cd backend
python main.py --debug
```

**Effects:**
- Verbose logging (all debug statements)
- Full stack traces in API responses
- Request/response details logged
- Uvicorn reload mode enabled

## Troubleshooting

### "Azure OpenAI service not configured"
- Check `.env` has all required Azure OpenAI variables
- Run `GET /api/health` to verify configuration status

### No RAG context being used
- Ensure `.bean` files exist in `data/bean_files/`
- Restart server to re-ingest files
- Check startup logs for ingestion results
- Verify with `GET /api/stats` endpoint

### CORS errors in frontend
- Backend must run on port matching `API_BASE_URL` in `frontend/script.js` (default: 8000)
- CORS is currently set to allow all origins (`allow_origins=["*"]`)

### ChromaDB errors
- Delete `data/chroma_db/` directory and restart to reset vector database
- Re-ingest .bean files after reset

## Project Conventions

- **Logging**: Use the logger from `logger.py`, not print statements
- **Error handling**: Raise `HTTPException` in endpoints, log with `log_exception(logger, e, context)`
- **Configuration**: All settings via environment variables, no hardcoded values
- **API responses**: Always return JSON with `success` field and meaningful error messages
- **Code organization**: Keep service classes focused on single responsibility
