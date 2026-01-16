#!/bin/bash

# Start script for Paste Beans

echo "🫘 Starting Paste Beans..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "Please edit .env and add your Azure OpenAI credentials:"
    echo "  - AZURE_OPENAI_API_KEY"
    echo "  - AZURE_OPENAI_ENDPOINT"
    echo "  - AZURE_OPENAI_DEPLOYMENT_NAME"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
    echo ""
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
cd backend
pip install -q -r requirements.txt
cd ..
echo "✅ Dependencies installed"
echo ""

# Start the server
echo "Starting Paste Beans server..."
echo ""
echo "🌐 Application: http://localhost:8000"
echo "📚 API docs: http://localhost:8000/docs"
echo ""

# Check for debug flag and pass to Python
DEBUG_FLAG=""
if [ "$1" = "--debug" ] || [ "$1" = "-d" ] || [ "$1" = "--verbose" ] || [ "$1" = "-v" ]; then
    DEBUG_FLAG="--debug"
    echo "🐛 Debug mode enabled"
    echo ""
fi

cd backend
python main.py $DEBUG_FLAG
