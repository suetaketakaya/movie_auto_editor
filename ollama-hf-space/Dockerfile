FROM ollama/ollama:latest

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces requires port 7860
ENV OLLAMA_HOST=0.0.0.0:7860
EXPOSE 7860

# Pre-pull model at build time (cached in image)
# Using smaller vision model for HF free tier (CPU)
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
