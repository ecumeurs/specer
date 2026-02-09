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
- **Semantic Merging**: Uses AI to find the right place for your updates.
- **Version Control**: Track document history with rollback capability.
  - Version increments on merge completion or manual edits
  - Download clean or annotated (with version history) documents
  - Rollback to any previous version

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/init` | POST | Initialize or reset a document |
| `/api/process` | POST | Parse protocol blocks from LLM input |
| `/api/diff` | POST | Start background merge task |
| `/api/commit` | POST | Save document (intermediate) |
| `/api/validate-merge` | POST | Complete merge and bump version |
| `/api/versions/{name}` | GET | Get version history |
| `/api/download/{name}` | GET | Download document (?annotated=true for version info) |
| `/api/rollback` | POST | Rollback to previous version |

## Development

The backend code is mounted as a volume, so changes in `./server` will auto-reload.

### Running Tests

```bash
# Unit tests (no server needed)
uv run pytest tests/test_version_control.py -v

# E2E tests (requires running server)
docker compose up -d
uv run pytest tests/test_merge_e2e.py -v
```
