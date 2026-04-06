#!/bin/bash

# ============================================================================
# ALGORITHMIC TRADING PLATFORM - STARTUP SCRIPT
# ============================================================================
# This script builds and starts the entire trading platform with Docker
# Usage: ./scripts/start_platform.sh
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   ALGORITHMIC TRADING PLATFORM - STARTUP              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example...${NC}"
    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    echo -e "${RED}⚠️  IMPORTANT: Edit .env and configure your Zerodha credentials!${NC}"
    echo ""
fi

# Navigate to project root
cd "$PROJECT_ROOT"

# Create logs directory
mkdir -p logs
chmod 755 logs

# Create config directory
mkdir -p config

echo -e "${GREEN}✓ Project structure ready${NC}"
echo ""

# Step 1: Build all services
echo -e "${BLUE}[1/4] Building Docker images...${NC}"
docker-compose build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Build successful${NC}"
else
    echo -e "${RED}✗ Build failed${NC}"
    exit 1
fi

echo ""

# Step 2: Start services
echo -e "${BLUE}[2/4] Starting services...${NC}"
docker-compose up -d

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Services started${NC}"
else
    echo -e "${RED}✗ Failed to start services${NC}"
    exit 1
fi

echo ""

# Step 3: Wait for services to be healthy
echo -e "${BLUE}[3/4] Waiting for services to be healthy...${NC}"
echo "This may take 1-2 minutes..."
sleep 10

# Check PostgreSQL
echo -n "Checking PostgreSQL..."
until docker exec algo_trading_db pg_isready -U postgres > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e "${GREEN} ✓${NC}"

# Check Backend
echo -n "Checking Backend API..."
until curl -s http://localhost:8000/health > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e "${GREEN} ✓${NC}"

# Check Frontend
echo -n "Checking Frontend..."
until curl -s http://localhost:3000 > /dev/null 2>&1; do
    echo -n "."
    sleep 2
done
echo -e "${GREEN} ✓${NC}"

echo ""

# Step 4: Display status
echo -e "${BLUE}[4/4] Platform Status:${NC}"
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          ✓ PLATFORM READY                              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Backend API:${NC}     http://localhost:8000"
echo -e "${BLUE}Frontend UI:${NC}     http://localhost:3000"
echo -e "${BLUE}Database:${NC}        localhost:5432"
echo -e "${BLUE}Redis:${NC}           localhost:6379"
echo ""
echo -e "${BLUE}Health Check:${NC}    http://localhost:8000/health"
echo ""

# Show container status
echo -e "${BLUE}Container Status:${NC}"
docker-compose ps

echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo "  View logs:       docker-compose logs -f backend"
echo "  Stop platform:   docker-compose down"
echo "  Restart:         docker-compose restart"
echo ""
echo -e "${GREEN}✓ Platform startup complete!${NC}"
echo ""
