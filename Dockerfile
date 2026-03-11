FROM ollama/ollama:latest

# Install Python and essentials
RUN apt-get update && apt-get install -y \
    python3 python3-pip curl && \
    apt-get clean

WORKDIR /app

# Install all Python requirements
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
# Copy code
COPY . .

# HF Spaces default port for web apps
EXPOSE 8501

# Make start.sh executable
RUN chmod +x start.sh

# Start the app
CMD ["./start.sh"]