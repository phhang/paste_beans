# Paste Beans - Screenshot to Beancount Converter

A web application that converts bank statement screenshots to Beancount entries using Azure OpenAI and RAG (Retrieval-Augmented Generation) for consistency with your historical transactions.

## Features

- **Paste screenshots directly** - No file uploads needed, just paste from clipboard
- **AI-powered extraction** - Uses Azure OpenAI Vision to extract date, merchant, and amount
- **RAG consistency** - Maintains consistent merchant names and categories using ChromaDB vector database
- **Historical learning** - Learns from your existing .bean files to match your accounting style
- **Clean interface** - Simple, focused UI for quick entry generation

## Architecture

```
Frontend (HTML/CSS/JS)
    ↓
FastAPI Backend
    ↓
┌─────────────┬──────────────┬────────────────┐
│  Azure      │  ChromaDB    │  RAG Service   │
│  OpenAI     │  Vector DB   │                │
│  (Vision)   │  (.bean)     │  (Consistency) │
└─────────────┴──────────────┴────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.8 or higher
- Azure OpenAI account with a GPT-4 Vision deployment
- Your Azure OpenAI API key and endpoint

### Installation

1. **Clone or download this repository**

2. **Run the start script:**

```bash
./start.sh
```

On first run, this will:
- Create a `.env` file from the template
- Prompt you to add your Azure OpenAI credentials
- Create a virtual environment
- Install all dependencies

3. **Configure Azure OpenAI:**

Edit the `.env` file with your credentials:

```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

4. **Add your existing Beancount files:**

Copy your `.bean` files to `data/bean_files/` directory:

```bash
cp ~/accounting/*.bean data/bean_files/
```

The server will automatically ingest these files on startup for RAG context.

5. **Start the server again:**

```bash
./start.sh
```

6. **Open the frontend:**

Open `frontend/index.html` in your web browser or serve it:

```bash
# Option 1: Open directly
open frontend/index.html

# Option 2: Use Python's HTTP server
cd frontend
python3 -m http.server 8080
# Then visit http://localhost:8080
```

## Usage

1. **Enter your account name** (e.g., `Assets:Bank:Checking`)

2. **Click the paste area and press Ctrl+V (or Cmd+V)** to paste a screenshot of your bank transaction

3. **Click "Generate Beancount Entry"**

4. The app will:
   - Extract transaction details using AI vision
   - Search your historical entries for similar merchants
   - Generate a Beancount entry with consistent naming
   - Display the formatted entry

5. **Copy to clipboard** and paste into your Beancount file

## Example

If you paste a screenshot showing:
```
Date: 2024-01-15
Merchant: AMZN Marketplace
Amount: $45.99
```

And you have previous entries like:
```beancount
2024-01-10 * "Amazon" "Office supplies"
  Expenses:Shopping:Office   32.50 USD
  Assets:Bank:Checking      -32.50 USD
```

The app will generate:
```beancount
2024-01-15 * "Amazon" "Marketplace purchase"
  Expenses:Shopping:Office   45.99 USD
  Assets:Bank:Checking      -45.99 USD
```

Notice it standardized "AMZN Marketplace" to "Amazon" and used the same category as your historical entries.

## API Endpoints

The backend provides several useful endpoints:

- `POST /api/generate-beancount` - Generate entry from screenshot
- `POST /api/ingest-bean-file` - Upload a .bean file to ingest
- `POST /api/ingest-directory` - Re-ingest all files in data/bean_files/
- `GET /api/merchant-context/{name}` - Get historical context for a merchant
- `GET /api/stats` - Get vector database statistics
- `GET /api/health` - Health check

Access API docs at: `http://localhost:8000/docs`

## Project Structure

```
paste_beans/
├── backend/
│   ├── main.py                  # FastAPI server
│   ├── config.py                # Configuration management
│   ├── vector_db.py             # ChromaDB operations
│   ├── rag_service.py           # RAG logic
│   ├── azure_openai_service.py  # Azure OpenAI integration
│   └── requirements.txt         # Python dependencies
├── frontend/
│   ├── index.html              # Main UI
│   ├── style.css               # Styles
│   └── script.js               # Frontend logic
├── data/
│   ├── bean_files/             # Your .bean files (for RAG)
│   └── chroma_db/              # ChromaDB storage (auto-generated)
├── .env.example                # Environment template
├── .gitignore
├── start.sh                    # Startup script
└── README.md
```

## Configuration

All configuration is done via the `.env` file:

```env
# Required: Azure OpenAI
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Optional: Database
CHROMA_PERSIST_DIRECTORY=./data/chroma_db

# Optional: Server
HOST=0.0.0.0
PORT=8000
```

## How RAG Works

1. **Ingestion**: Your .bean files are parsed and stored in ChromaDB with embeddings
2. **Retrieval**: When a new transaction is processed, the merchant name is used to search for similar historical entries
3. **Generation**: The LLM receives context from your historical entries and generates a new entry matching your patterns

This ensures:
- Consistent merchant naming (e.g., always "Amazon" not "AMZN", "Amazon.com", etc.)
- Consistent expense categories
- Consistent formatting and style

## Troubleshooting

### "Azure OpenAI service not configured"

Make sure you've set all required environment variables in `.env`:
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_DEPLOYMENT_NAME

### No historical context being used

1. Check that .bean files are in `data/bean_files/`
2. Restart the server to re-ingest files
3. Check server logs to see ingestion results
4. Visit `http://localhost:8000/api/stats` to see entry count

### CORS errors in browser

Make sure the backend server is running at `http://localhost:8000`. If you need to change the port, update both:
- `PORT` in `.env`
- `API_BASE_URL` in `frontend/script.js`

## Development

### Adding dependencies:

```bash
cd backend
pip install package_name
pip freeze > requirements.txt
```

### Running in development mode:

The server automatically reloads on code changes when started with `start.sh` or `python main.py`.

## License

MIT License - feel free to use and modify for your needs.

## Credits

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Backend framework
- [ChromaDB](https://www.trychroma.com/) - Vector database
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service) - Vision and LLM
- [Beancount](https://beancount.github.io/) - Double-entry accounting
