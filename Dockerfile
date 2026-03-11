FROM ollama/ollama:latest

USER root

RUN apt-get update \
    && apt-get install -y python3 python3-pip curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --break-system-packages -r requirements.txt

ADD app /app

RUN chmod +x /app/start.sh

ENTRYPOINT []

EXPOSE 8501

CMD ["/bin/bash", "/app/start.sh"]