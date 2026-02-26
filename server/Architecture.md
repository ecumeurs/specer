# Backend APIs
Centralized server operations and HTTP API.

## Identification
* Feature: Specer Backend
* Scope: API / Server Engine

## Layout
* `main.py`: FastAPI entry point, defining all HTTP endpoints.
* `document_manager.py`: File storage interaction, history, and versioning system.
* `gemini_client.py` & `ollama_client.py`: Wrapper adapters for LLM interactions.
* `markdown_renderer.py`: Utility to turn markdown to HTML for previews.
* `vector_store.py`: Embedded similarity search for doc chunks.
* `blueprints_manager.py`: System for dynamic loading of structural blueprints based on YAML+Markdown templates.
* `blueprint.py`: Data definition for dynamic templates.

## API / Interface
* `POST /api/process`: Takes raw user input and figures out what sections to update.
* `POST /api/diff`: Triggers background async LLM generation of a merged section.
* `GET /api/task/{task_id}`: Polls the background LLM task.
* `GET /api/blueprints`: (Planned) Fetch dynamically parsed blueprints.

## Internal Mechanics
* Endpoints interact with managers directly. For long running tasks, `main.py` stores a task map and returns early, allowing standard HTTP polling.

## Tests
* Core tests found in `tests/test_merge_e2e.py` and unit tests in corresponding `tests/test_*.py` files.

## Related
* `static/`: The frontend client consuming this API.
* `blueprints/`: The configuration files injected into the server at runtime.
