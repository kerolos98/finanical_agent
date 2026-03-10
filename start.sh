#!/bin/bash

# 1. Start Ollama in the background
ollama serve &

# 2. Wait for the Ollama API to wake up
echo "Waiting for Ollama API..."
while ! curl -s localhost:11434/api/tags > /dev/null; do
  sleep 2
done

# 3. Pull the 1.5B model
echo "Pulling qwen3:1.7b..."
ollama pull qwen3:1.7b

# 4. PRE-WARM: Load the model into RAM immediately
# We send an empty prompt just to trigger the load
echo "Pre-warming model into RAM..."
curl -X POST http://localhost:11434/api/generate -d '{"model": "qwen3:1.7b, "prompt": "", "keep_alive": -1}'

# 5. Launch Streamlit
echo "Launching Finance Fox..."
streamlit run app/app_ui.py --server.port 7860 --server.address 0.0.0.0