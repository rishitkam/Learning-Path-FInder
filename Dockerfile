# Multi-stage build: keeps the final image small
FROM python:3.12-slim AS base

WORKDIR /app

# Hugging Face Spaces requires running as a non-root user (UID 1000)
# We set this up so the app has permission to write to data/learners.db locally
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Install dependencies first (separate layer for caching)
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the files the engine needs at runtime
COPY --chown=user:user api.py db.py embed.py explain.py graph.py path.py profile.py state.py ./
COPY --chown=user:user data/ ./data/

# Hugging Face Spaces expects the app to run on port 7860
ENV PORT=7860
EXPOSE 7860

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port 7860"]
