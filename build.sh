#!/usr/bin/env bash
# =============================================================================
# Render Build Script for CLI Agent AI
# Builds React frontend and installs Python backend dependencies in one step.
# =============================================================================

# Exit immediately if any command returns a non-zero exit code
set -o errexit

echo "=========================================================="
echo "       BUILDING CLI AGENT AI FULL-STACK PLATFORM          "
echo "=========================================================="

# 1. Build Frontend Production Bundle
echo ""
echo "[1/2] Installing frontend dependencies & building React SPA..."
cd frontend
npm install
npm run build
cd ..

# 2. Install Backend Python Dependencies
echo ""
echo "[2/2] Installing Python dependencies from backend/requirements.txt..."
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

echo ""
echo "=========================================================="
echo " [SUCCESS] Build complete! Single-site deployment ready.  "
echo "=========================================================="
