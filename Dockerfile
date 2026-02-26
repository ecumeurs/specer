FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml .
RUN pip install fastapi uvicorn httpx numpy markdown pygments python-dotenv google-genai

COPY . .

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
