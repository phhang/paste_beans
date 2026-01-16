# Quick Start Guide

## 1. Configure Environment

```bash
# Copy the environment template
cp .env.example .env

# Edit .env and add your Azure OpenAI credentials
nano .env  # or use your preferred editor
```

Required settings:
- `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` - Your endpoint (e.g., https://your-resource.openai.azure.com/)
- `AZURE_OPENAI_DEPLOYMENT_NAME` - Your deployment name (e.g., gpt-4-vision)

## 2. Add Your Beancount Files (Optional but Recommended)

```bash
# Copy your existing .bean files for RAG context
cp ~/path/to/your/*.bean data/bean_files/
```

This allows the AI to learn your merchant naming patterns and expense categories.

## 3. Start the Server

```bash
./start.sh
```

This will:
- Create a Python virtual environment
- Install dependencies
- Ingest your .bean files
- Start the FastAPI server at http://localhost:8000

## 4. Open the Frontend

Open `frontend/index.html` in your web browser:

```bash
# macOS
open frontend/index.html

# Linux
xdg-open frontend/index.html

# Or serve with Python
cd frontend && python3 -m http.server 8080
```

## 5. Use the App

1. **Enter account name**: e.g., `Assets:Bank:Checking`
2. **Click paste area** and press `Ctrl+V` (or `Cmd+V`) to paste your screenshot
3. **Click "Generate Beancount Entry"**
4. **Copy the result** to your Beancount file

## What Screenshots to Use

The app works best with screenshots that clearly show:
- **Date** (e.g., "2024-01-15" or "Jan 15, 2024")
- **Merchant name** (e.g., "Amazon", "Starbucks")
- **Amount** (e.g., "$45.99", "32.50 USD")

Examples:
- Bank transaction list screenshots
- Credit card statement screenshots
- Mobile banking app screenshots
- Receipt photos (if they show date/merchant/amount clearly)

## API Endpoints

If you want to integrate programmatically:

```bash
# Generate entry
curl -X POST http://localhost:8000/api/generate-beancount \
  -F "image=@screenshot.png" \
  -F "account_name=Assets:Bank:Checking"

# Check stats
curl http://localhost:8000/api/stats

# Get merchant context
curl http://localhost:8000/api/merchant-context/Amazon
```

Full API docs: http://localhost:8000/docs

## Troubleshooting

### Server won't start
- Check that Python 3.8+ is installed: `python3 --version`
- Check that .env has valid Azure OpenAI credentials
- Check the server logs for specific errors

### No RAG context being used
- Ensure .bean files are in `data/bean_files/`
- Restart the server to re-ingest files
- Check ingestion logs during startup

### CORS errors
- Make sure backend is running at http://localhost:8000
- Check that the frontend's API_BASE_URL matches the backend port

## Tips

1. **Start with good data**: The more quality .bean files you add, the better the RAG context
2. **Consistent naming**: Once you establish a pattern (e.g., "Amazon" vs "AMZN"), the AI will maintain it
3. **Review entries**: Always review AI-generated entries before adding them to your ledger
4. **Batch processing**: Take multiple screenshots and process them one by one
5. **Update context**: Periodically re-ingest your .bean files as your ledger grows

## Next Steps

- Add more .bean files to `data/bean_files/` to improve RAG accuracy
- Customize expense categories in your existing files
- Explore the API at http://localhost:8000/docs
- Integrate with your accounting workflow
