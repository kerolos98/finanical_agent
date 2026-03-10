FROM ollama/ollama:latest

# Install Python and essentials
RUN apt-get update && apt-get install -y \
    python3 python3-pip curl && \
    apt-get clean

WORKDIR /app

# Install all requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy your code
COPY . .
ENV OLLAMA_KEEP_ALIVE=-1
# Give permission to the start script
RUN chmod +x start.sh

# HF Spaces default port
EXPOSE 7860

# Run the orchestration script
CMD ["./start.sh"]