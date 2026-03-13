#!/bin/bash

# Start the Ollama server in the background
ollama serve &
OLLAMA_PID=$!

# Wait for API to be responsive
echo "Waiting for Ollama API..."
until curl -s localhost:11434/api/tags > /dev/null; do
  sleep 2
done

# Pull the model
echo "Pulling llama3.2:1b..."
ollama pull llama3.2:1b

# Pre-warm the model (Loads it into RAM immediately)
echo "Pre-warming model..."
curl -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" \
-d '{"model": "qwen2.5:1.5b", "prompt": "hi", "keep_alive": -1}'

# Launch Streamlit on the standard HF port
echo "Launching Finance Fox..."
streamlit run app_ui.py --server.port 8501 --server.address 0.0.0.0

# Keep the script alive as long as Ollama is running
wait $OLLAMA_PID
