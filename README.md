# Specer: Semantic Spec Merger

A "Semantic Git" for AI-assisted documentation. Merges updates from LLM chats into a master specification document using intelligent merging.

> **Note**: The project currently requires a `.env` file at the root with a `GEMINI_API_KEY` defined. We prioritize replacing this with Google OAuth integrated at a later date to remove this requirement.

## Quick Start

1. **Prerequisites**: Ensure you have Docker and Docker Compose installed, and have created your `.env` file.
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
- **Dynamic Blueprints**: Define custom document hierarchies and templates using Markdown and YAML frontmatter (`blueprints/` directory).
- **Document Management**: Create and Reset named documents seeded from blueprint templates.
- **Semantic Merging**: Uses AI to find the right place for your updates, constrained by blueprint layout rules.
- **Version Control**: Track document history with rollback capability.
  - Version increments on merge completion or manual edits
  - Download clean or annotated (with version history) documents
  - Rollback to any previous version
- **AI Chat Integration**: Interact with Gemini directly to refine specifications.
- **Section Summarization**: Generate semantic summaries for document sections using Ollama.
- **Background Support**: Background processing for long-running semantic merges.
- **Markdown Rendering**: Render documents, sections, or live previews into HTML.

## API Endpoints

### Core Document & Merging
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/init` | POST | Initialize or reset a document |
| `/api/blueprints` | GET | List loaded structural blueprint definitions |
| `/api/spec/{name}` | GET | Get the full document content |
| `/api/structure/{name}` | GET | Get the document structure (sections) |
| `/api/process` | POST | Parse protocol blocks from LLM input |
| `/api/diff` | POST | Start background merge task |
| `/api/commit` | POST | Save document (intermediate) |
| `/api/validate-merge` | POST | Complete merge and bump version |
| `/api/summary` | POST | Generate a summary for a section using Ollama |

### Version Control
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/versions/{name}` | GET | Get version history |
| `/api/download/{name}` | GET | Download document (?annotated=true for version info) |
| `/api/rollback` | POST | Rollback to previous version |

### Gemini Chat API
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/gemini/models` | GET | List available Gemini models |
| `/api/gemini/session` | POST | Create a new Gemini chat session |
| `/api/gemini/session/{id}` | GET | Get session info |
| `/api/gemini/session/{id}` | DELETE | End session |
| `/api/gemini/chat/{id}` | POST | Send a message to Gemini |

### Background Tasks & Rendering
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/task/{id}` | GET | Get status of a background task |
| `/api/task/{id}/cancel`| POST | Cancel a background task |
| `/api/render/document/{name}` | GET | Render full document to HTML |
| `/api/render/section/{name}/{title}` | GET | Render specific section to HTML |
| `/api/render/preview` | POST | Render markdown preview |

## Roadmap / Future Plans

- **Authentication**: We plan to allow OAuth with Google to remove the API key requirement at a later date.
- **UI Rework**: We plan to do a comprehensive UI rework at some point.
- **LLM Multiplexer**: Maybe integration of LLM multiplexer like mammouth to support more models seamlessly.

## Development

The backend code is mounted as a volume, so changes in `./server` will auto-reload.

### Running Tests

```bash
# Unit tests (no server needed)
uv run pytest tests/test_version_control.py -v
uv run pytest tests/test_blueprints.py -v

# E2E tests (requires running server)
docker compose up -d
uv run pytest tests/test_merge_e2e.py -v
uv run pytest tests/test_dynamic_blueprints_e2e.py -v
```
