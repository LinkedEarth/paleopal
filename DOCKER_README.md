# PaleoPal Docker Setup

This guide explains how to run the PaleoPal system using Docker with data persistence.

## Prerequisites

- Docker Desktop or Docker Engine (20.10+)
- Docker Compose (2.0+)
- At least 4GB of available RAM
- At least 10GB of available disk space

## Quick Start

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd paleopal
   ```

2. **Create environment file**:
   ```bash
   cp backend/env.example backend/.env
   ```

3. **Edit the environment file** with your API keys:
   ```bash
   nano backend/.env
   # or
   vim backend/.env
   ```

   Add your LLM API keys:
   ```env
   OPENAI_API_KEY=your_openai_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   GOOGLE_API_KEY=your_google_key_here
   XAI_API_KEY=your_xai_key_here
   ```

4. **Start the system**:
   ```bash
   docker-compose up -d
   ```

5. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Qdrant Dashboard: http://localhost:6333/dashboard

## Architecture

The Docker setup includes:

- **Frontend** (port 3000): React application served by Nginx
- **Backend** (port 8000): FastAPI application with Python
- **Qdrant** (port 6333): Vector database for embeddings
- **Persistent Volumes**: For data storage

## Data Persistence

The system uses Docker volumes for persistent storage:

- `qdrant-data`: Vector database storage
- `backend-data`: SQLite conversations database and uploads
- `backend-libraries`: Document libraries and extracted methods

Your data will persist across container restarts and rebuilds.

## Management Commands

### Start the system
```bash
docker-compose up -d
```

### Stop the system
```bash
docker-compose down
```

### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f qdrant
```

### Check service status
```bash
docker-compose ps
```

### Rebuild and restart
```bash
# Rebuild everything
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Rebuild specific service
docker-compose build backend
docker-compose up -d backend
```

### Access service shells
```bash
# Backend container
docker-compose exec backend bash

# Frontend container
docker-compose exec frontend sh
```

## Development Mode

For development with hot-reloading:

1. **Backend development**:
   ```bash
   # Stop the containerized backend
   docker-compose stop backend
   
   # Run backend locally
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend development**:
   ```bash
   # Stop the containerized frontend
   docker-compose stop frontend
   
   # Run frontend locally
   cd frontend
   npm install
   npm start
   ```

3. **Keep Qdrant running**:
   ```bash
   docker-compose up -d qdrant
   ```

## Configuration

### Environment Variables

Key environment variables in `backend/.env`:

```env
# LLM API Keys
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
GOOGLE_API_KEY=your_key
XAI_API_KEY=your_key

# Default LLM Provider
DEFAULT_LLM_PROVIDER=openai

# Qdrant (handled by Docker)
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# Ollama (if running locally)
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### Port Configuration

Default ports (can be changed in `docker-compose.yml`):
- Frontend: 3000
- Backend: 8000
- Qdrant HTTP: 6333
- Qdrant gRPC: 6334

## Troubleshooting

### Services not starting
```bash
# Check service status
docker-compose ps

# Check logs for errors
docker-compose logs

# Restart specific service
docker-compose restart backend
```

### Port conflicts
If ports are already in use, edit `docker-compose.yml`:
```yaml
services:
  frontend:
    ports:
      - "3001:80"  # Change from 3000 to 3001
```

### Volume permission issues
```bash
# Reset volumes (WARNING: This deletes all data)
docker-compose down -v
docker volume prune
docker-compose up -d
```

### Memory issues
Increase Docker Desktop memory allocation:
- Docker Desktop → Settings → Resources → Memory → 6GB+

### API connection issues
1. Verify environment file exists: `backend/.env`
2. Check API keys are valid
3. Ensure Qdrant is healthy: `curl http://localhost:6333/health`

## Production Deployment

For production deployment:

1. **Use production environment file**:
   ```bash
   cp backend/.env backend/.env.prod
   # Edit .env.prod with production values
   ```

2. **Update docker-compose for production**:
   ```yaml
   # Add to docker-compose.yml
   environment:
     - ENV=production
   ```

3. **Use reverse proxy** (Nginx/Traefik) for HTTPS
4. **Set up monitoring** (logs, health checks)
5. **Configure backups** for persistent volumes

## Backup and Restore

### Backup data
```bash
# Create backup directory
mkdir backups

# Backup volumes
docker run --rm -v paleopal_qdrant-data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/qdrant-backup.tar.gz -C /data .
docker run --rm -v paleopal_backend-data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/backend-data-backup.tar.gz -C /data .
docker run --rm -v paleopal_backend-libraries:/data -v $(pwd)/backups:/backup alpine tar czf /backup/libraries-backup.tar.gz -C /data .
```

### Restore data
```bash
# Stop services
docker-compose down

# Restore volumes
docker run --rm -v paleopal_qdrant-data:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/qdrant-backup.tar.gz -C /data
docker run --rm -v paleopal_backend-data:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/backend-data-backup.tar.gz -C /data
docker run --rm -v paleopal_backend-libraries:/data -v $(pwd)/backups:/backup alpine tar xzf /backup/libraries-backup.tar.gz -C /data

# Start services
docker-compose up -d
```

## Support

For issues with the Docker setup:
1. Check this README for common solutions
2. Review Docker and docker-compose logs
3. Ensure system requirements are met
4. Check for port conflicts and resource availability 