#!/bin/bash
# Setup Script für Ollama Models
# Lädt die wichtigsten Models für Lead-Scraping

set -e

echo "🚀 KR-Lead-Scraper - Ollama Setup"
echo "=================================="
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "❌ Ollama ist nicht erreichbar auf localhost:11434"
    echo "   Starte Docker Container: docker-compose up -d ollama"
    exit 1
fi

echo "✅ Ollama ist erreichbar"
echo ""

# Function to pull model
pull_model() {
    local model=$1
    local description=$2

    echo "📥 Lade Model: $model"
    echo "   $description"

    if ollama pull "$model"; then
        echo "✅ $model erfolgreich geladen"
    else
        echo "⚠️  Fehler beim Laden von $model"
    fi
    echo ""
}

# Pull Models
echo "Lade empfohlene Models..."
echo ""

# Fast & Efficient (Default)
pull_model "llama3.2" "Schnell, gut für Extraktion (3B)"

# Better Quality
pull_model "mistral" "Bessere Qualität für komplexe Texte (7B)"

# Specialized for Business Data
pull_model "qwen2.5:7b" "Spezialisiert für Business-Daten (7B)"

echo "=================================="
echo "✅ Setup abgeschlossen!"
echo ""
echo "Verfügbare Models:"
ollama list
echo ""
echo "💡 Tipp: Ändere das Model in .env:"
echo "   OLLAMA_MODEL=llama3.2  # oder mistral, qwen2.5"
echo ""
