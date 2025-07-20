#!/bin/bash

# SoundCloud Downloader Setup Script

echo "🎵 Setting up SoundCloud Downloader..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Create downloads directory
echo "📁 Creating downloads directory..."
mkdir -p downloads

echo "✅ Setup complete!"
echo ""
echo "🚀 To start the server:"
echo "   1. Activate virtual environment: source venv/bin/activate"
echo "   2. Run the server: python app.py"
echo "   3. Open your browser to: http://localhost:5000"
echo ""
echo "📝 Note: Make sure you have FFmpeg installed for audio conversion"
echo "   - On Ubuntu/Debian: sudo apt install ffmpeg"
echo "   - On macOS: brew install ffmpeg"
echo "   - On Windows: Download from https://ffmpeg.org/download.html"