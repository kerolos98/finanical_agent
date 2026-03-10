ollama serve &
OLLAMA_PID=$!

# Wait for API
echo "Waiting for Ollama API..."
until curl -s localhost:11434/api/tags > /dev/null; do
  sleep 2
done

# Pull and prewarm model
echo "Pulling qwen3:1.7b..."
ollama pull qwen3:1.7b

echo "Pre-warming model..."
curl -X POST http://localhost:11434/api/generate -H "Content-Type: application/json" \
-d '{"model": "qwen3:1.7b", "prompt": "", "keep_alive": -1}'

# Launch Streamlit
echo "Launching Finance Fox..."
streamlit run app/app_ui.py --server.port 8501 --server.address 0.0.0.0

# Keep Ollama running if Streamlit stops
wait $OLLAMA_PID