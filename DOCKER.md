# Docker Guide for Paste Beans

This guide explains how to run Paste Beans using Docker for easy deployment and reuse.

## Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (included with Docker Desktop)
- `.env` file configured with Azure OpenAI credentials

## Quick Start

### 1. Build and Start the Container

```bash
# Build and start in detached mode
docker-compose up -d

# Or build and start with logs visible
docker-compose up
```

### 2. Access the Application

Open your browser and navigate to:
```
http://localhost:8000
```

The API documentation is available at:
```
http://localhost:8000/docs
```

### 3. Stop the Container

```bash
# Stop the container
docker-compose down

# Stop and remove volumes (clears ChromaDB data)
docker-compose down -v
```

## Docker Commands

### Building

```bash
# Build the image
docker-compose build

# Rebuild without cache
docker-compose build --no-cache
```

### Running

```bash
# Start in background
docker-compose up -d

# Start and view logs
docker-compose up

# View logs of running container
docker-compose logs -f
```

### Managing

```bash
# Stop the container
docker-compose stop

# Start stopped container
docker-compose start

# Restart the container
docker-compose restart

# Remove container (keeps volumes)
docker-compose down

# Remove container and volumes
docker-compose down -v
```

### Debugging

```bash
# Execute commands inside running container
docker-compose exec paste-beans bash

# View real-time logs
docker-compose logs -f paste-beans

# Check container status
docker-compose ps

# Inspect container health
docker inspect paste-beans-app | grep -A 10 Health
```

## Data Persistence

The following directories are mounted as volumes for data persistence:

- `./data/chroma_db` - ChromaDB vector database storage
- `./data/bean_files` - Beancount files for ingestion

**Important:** Data in these directories persists even when the container is stopped or removed (unless you use `docker-compose down -v`).

## Adding Beancount Files

To add existing `.bean` files for RAG context:

1. Place your `.bean` files in `./data/bean_files/`
2. Restart the container to trigger re-ingestion:
   ```bash
   docker-compose restart
   ```

Or trigger manual ingestion via API:
```bash
curl -X POST http://localhost:8000/api/ingest-directory
```

## Environment Configuration

Configuration is loaded from `.env` file. Key variables:

```env
# Required
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-vision

# Optional (defaults shown)
AZURE_OPENAI_API_VERSION=2024-02-15-preview
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

After changing `.env`, restart the container:
```bash
docker-compose restart
```

## Port Configuration

By default, the application runs on port 8000. To use a different port:

1. Edit `docker-compose.yml`:
   ```yaml
   ports:
     - "3000:8000"  # Maps host port 3000 to container port 8000
   ```

2. Restart:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Vector Database Management

The `manage_vectordb.py` script can be run inside the Docker container using `docker-compose exec`.

### Show Database Statistics

```bash
# Basic stats
docker-compose exec paste-beans python manage_vectordb.py --stats

# Detailed stats with sample entries
docker-compose exec paste-beans python manage_vectordb.py --stats --verbose
```

### Load Bean Files

```bash
# Load from default directory (data/bean_files/)
docker-compose exec paste-beans python manage_vectordb.py --load

# Load a specific file
docker-compose exec paste-beans python manage_vectordb.py --load /app/data/bean_files/transactions.bean

# Load from a specific directory
docker-compose exec paste-beans python manage_vectordb.py --load /app/data/bean_files/
```

**Workflow for adding new bean files:**

1. Place `.bean` files in `./data/bean_files/` on your host
2. Load them into the database:
   ```bash
   docker-compose exec paste-beans python manage_vectordb.py --load --stats
   ```

### Cleanup Database

```bash
# Cleanup with confirmation prompt (interactive)
docker-compose exec paste-beans python manage_vectordb.py --cleanup

# Cleanup without confirmation (automated)
docker-compose exec paste-beans python manage_vectordb.py --cleanup --yes
```

### Combined Operations

```bash
# Cleanup, reload, and show stats
docker-compose exec paste-beans python manage_vectordb.py --cleanup --yes --load --stats

# Load and show verbose stats
docker-compose exec paste-beans python manage_vectordb.py --load --stats --verbose
```

### Interactive Shell Access

For more complex operations, open a shell inside the container:

```bash
# Start an interactive bash session
docker-compose exec paste-beans bash

# Once inside, you can run commands directly
cd /app/backend
python manage_vectordb.py --stats
python manage_vectordb.py --load --verbose
exit
```

### Common Management Tasks

**Check how many entries are in the database:**
```bash
docker-compose exec paste-beans python manage_vectordb.py --stats
```

**Reset database and reload fresh data:**
```bash
# Ensure your .bean files are in ./data/bean_files/
docker-compose exec paste-beans python manage_vectordb.py --cleanup --yes --load --stats
```

**Add new transactions without removing existing ones:**
```bash
# Copy new .bean file to data directory
cp ~/accounting/january.bean ./data/bean_files/

# Load the new file
docker-compose exec paste-beans python manage_vectordb.py --load --stats
```

### Troubleshooting Management Commands

**"No .bean files found" error:**
```bash
# Check if files exist in the volume
docker-compose exec paste-beans ls -la /app/data/bean_files/

# If empty, add files on host and they'll be visible in container
cp your_file.bean ./data/bean_files/
```

**Permission errors:**
```bash
# Fix permissions on host
sudo chown -R $USER:$USER ./data/

# Or run command as root in container
docker-compose exec -u root paste-beans python manage_vectordb.py --stats
```

## Troubleshooting

### Container won't start

```bash
# Check logs for errors
docker-compose logs paste-beans

# Verify .env file exists and is valid
cat .env
```

### "Port already in use" error

```bash
# Check what's using port 8000
lsof -i :8000  # On macOS/Linux
netstat -ano | findstr :8000  # On Windows

# Either stop the conflicting service or change the port in docker-compose.yml
```

### ChromaDB errors

```bash
# Reset the vector database
docker-compose down
rm -rf data/chroma_db/*
docker-compose up -d
```

### Can't access from host browser

- Ensure the container is running: `docker-compose ps`
- Check if port is exposed: `docker port paste-beans-app`
- Verify firewall isn't blocking port 8000

## Production Deployment

For production use:

1. **Use specific versions** in `docker-compose.yml`:
   ```yaml
   image: paste-beans:1.0.0
   ```

2. **Don't bind mount .env** - Use Docker secrets or environment variables:
   ```yaml
   environment:
     - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
   ```

3. **Add reverse proxy** (nginx/Traefik) for HTTPS

4. **Set resource limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1.0'
         memory: 1G
   ```

5. **Enable restart policy**: Already set to `unless-stopped`

## Building for Different Architectures

To build for a specific platform (e.g., ARM for Raspberry Pi):

```bash
docker buildx build --platform linux/arm64 -t paste-beans:arm64 .
```

## Exporting/Importing Images

### Export image for reuse elsewhere:

```bash
# Save image to tar file
docker save paste-beans:latest | gzip > paste-beans.tar.gz

# Load on another machine
gunzip -c paste-beans.tar.gz | docker load
```

### Push to Docker registry:

```bash
# Tag image
docker tag paste-beans:latest your-registry.com/paste-beans:latest

# Push
docker push your-registry.com/paste-beans:latest
```

## Health Checks

The container includes a health check that pings `/api/health` every 30 seconds.

Check health status:
```bash
docker inspect paste-beans-app | grep -A 5 Health
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [FastAPI with Docker](https://fastapi.tiangolo.com/deployment/docker/)
