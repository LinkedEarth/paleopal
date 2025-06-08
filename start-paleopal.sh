#!/bin/bash

# PaleoPal Docker Startup Script
echo "🦴 Starting PaleoPal System..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker compose is available
if ! docker compose version > /dev/null 2>&1; then
    echo "❌ Docker Compose is not available. Please install Docker Compose V2."
    exit 1
fi

# Check if .env file exists
if [ ! -f "backend/.env" ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp backend/env.example backend/.env
    echo "📝 Please edit backend/.env with your API keys:"
    echo "   nano backend/.env"
    echo ""
    echo "Required API keys:"
    echo "   - OPENAI_API_KEY"
    echo "   - ANTHROPIC_API_KEY (optional)"
    echo "   - GOOGLE_API_KEY (optional)"
    echo "   - XAI_API_KEY (optional)"
    echo ""
    read -p "Press Enter after editing the .env file to continue..."
fi

# Start the system
echo "🚀 Starting PaleoPal services..."
docker compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "📊 Service Status:"
docker compose ps

echo ""
echo "✅ PaleoPal is starting up!"
echo ""
echo "🌐 Access points:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   Qdrant Dashboard: http://localhost:6333/dashboard"
echo ""
echo "📋 Useful commands:"
echo "   View logs: docker compose logs -f"
echo "   Stop system: docker compose down"
echo "   Restart: docker compose restart"
echo ""
echo "For full documentation, see DOCKER_README.md" 