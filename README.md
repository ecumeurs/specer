# Specer: Semantic Spec Merger

A "Semantic Git" for AI-assisted documentation. Merges updates from LLM chats into a master specification document using intelligent merging.

## Quick Start

1. **Prerequisites**: Ensure you have Docker and Docker Compose installed.
2. **Start Services**:
    ```bash
    docker compose up -d
    ```
    This begins both the Backend (FastAPI) and Ollama.

3. **Install Models** (First Run Only):
    Since the Ollama volume is persistent, you only need to do this once.
    ```bash
    docker exec -it ollama ollama pull llama3.2
    docker exec -it ollama ollama pull nomic-embed-text
    ```

4. **Access UI**:
    Open [http://localhost:8001](http://localhost:8001) in your browser.

## Features

- **Protocol Parsing**: Automatically extracts "Spec Updates" from chat logs.
- **Document Management**: Create and Reset named documents.
- **Semantic Merging** (Coming Soon): Uses AI to find the right place for your updates.

## Development

The backend code is mounted as a volume, so changes in `./server` will auto-reload.
