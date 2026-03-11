FROM ollama/ollama:latest

# 1. Install Python and essentials
USER root
RUN apt-get update && apt-get install -y \
    python3 python3-pip curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Set up the Hugging Face User (Required)
RUN useradd -m -u 1000 user
WORKDIR /home/user/app

# 3. Install Python requirements
COPY --chown=user requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# 4. Copy code and set permissions
COPY --chown=user . .
RUN chmod +x start.sh

# 5. THE CRITICAL FIX: Reset the entrypoint
# This prevents 'ollama' from being prefixed to your CMD
ENTRYPOINT []

# 6. Switch to non-root user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# 7. Hugging Face standard port
EXPOSE 8501

# 8. Start the app
CMD ["/bin/bash", "./start.sh"]