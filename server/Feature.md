# Backend API
Core logic provider for Specer, handling document storage, LLM orchestration, and now dynamic blueprints.

## Drive
Maintain state and process heavy operations (like vector-based Diff/Merge using Generative AI) separated from the UI client.

## Planned usage
* **Target Audience**: The Specer Frontend App
* **User Stories**:
    * Receive protocol chunk inputs and classify against LLM.
    * Perform structural diffing and merging of markdown chunks.
    * Maintain historical snapshots of the specification document.
    * Dynamically provide structural blueprints to direct UI and document behavior.

## Business Logic
* **Document Manager**: Handles saving/loading markdown, version history tracking, and snapshotting.
* **LLM Clients**: Connects to `google-genai` (Gemini) or `ollama` for unstructured text synthesis and merging.
* **Blueprints Manager**: (NEW) Scans `blueprints/` directory, extracts YAML frontmatter, and drives dynamic mapping of section types preventing hardcoded hierarchy.

## Expectation & Achievement
* [x] Basic Document Storage and Versioning
* [x] Synchronous and Async LLM Merge calls
* [x] Basic Structure Extraction (Header based)
* [ ] Dynamic Blueprint parsing and retrieval
* [ ] Integrate Blueprints into initialization and `/process`
