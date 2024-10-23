#!/bin/bash
set -e  # Exit on error

echo "🚀 Starting development environment setup..."

# Create and activate virtual environment
echo "📦 Setting up Python virtual environment..."
python -m venv .venv
source .venv/bin/activate

# Upgrade pip and install basic tools
echo "🔧 Upgrading pip and installing development tools..."
python -m pip install --upgrade pip
pip install wheel setuptools

# Install project dependencies
if [ -f "requirements.txt" ]; then
    echo "📚 Installing project dependencies..."
    pip install -r requirements.txt
fi

if [ -f "requirements-dev.txt" ]; then
    echo "🔨 Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# Install pre-commit hooks if config exists
if [ -f ".pre-commit-config.yaml" ]; then
    echo "🔍 Setting up pre-commit hooks..."
    pip install pre-commit
    pre-commit install
fi

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p logs
mkdir -p data
mkdir -p tests

# Set up git config if in git repository
if [ -d ".git" ]; then
    echo "🔧 Configuring git..."
    git config --local core.autocrlf input
    git config --local core.eol lf
fi

echo "✨ Setup complete! Happy coding!"