#!/bin/bash
set -e

echo "Starting Ollama server on port 7860..."
ollama serve &

# Wait for server to be ready
echo "Waiting for Ollama to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:7860/api/tags > /dev/null 2>&1; then
        echo "Ollama is ready!"
        break
    fi
    sleep 2
done

# Pull the vision model (will use cache if already pulled during build)
echo "Pulling llama3.2-vision model..."
ollama pull llama3.2-vision

echo "Model ready. Ollama is serving on port 7860."

# Keep the container running
wait
