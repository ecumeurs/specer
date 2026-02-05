Here is the comprehensive summary and blueprint for your **"Semantic Spec Merger"** application.

### 1. Project Overview

**The Goal:** Build a "Semantic Git" for AI-assisted documentation. It allows you to iteratively refine a specification document by feeding it chat logs (prompt replies), automatically finding where that new information belongs, and merging it intelligently.

**The Logic:**

1. **Destructure:** Strip headers/footers and isolate the core update from the LLM reply using a standardized "Spec Protocol."
2. **Match:** Use vector embeddings to find *where* in the Master Document this new paragraph belongs (Semantic Search).
3. **Merge:** Use a local SLM (Small Language Model) to blend the new content with the old, resolving conflicts while keeping the tone consistent.

---

### 2. The Engine: Ollama on Docker

You are using **Ollama** as a self-hosted API to handle all AI tasks (Merging & Matching) without leaving your local network.

**The Setup:**
Run the container (exposing port 11434):

```bash
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

```

**The Models (Run once inside the container):**

1. **The Brain (Merger):** `llama3.2` (Lightweight, fast, smart enough for rewriting text).
2. **The Eyes (Matcher):** `nomic-embed-text` (Optimized for turning text into math vectors).

```bash
docker exec -it ollama ollama pull llama3.2
docker exec -it ollama ollama pull nomic-embed-text

```

**Usage:** Your web app will send HTTP POST requests to `http://localhost:11434/api/embeddings` (to find matches) and `http://localhost:11434/api/generate` (to merge text).

---

### 3. The Web App Specification (MVP)

This will be a lightweight single-page application (SPA) backed by a simple Python server (FastAPI).

#### **A. User Interface (The Dashboard)**

1. **"The Protocol" Box:** A read-only text area containing your **Standardized System Prompt** (with `<<<SPEC_START>>>` rules) so you can quickly copy it into Gemini/ChatGPT before starting a session. See `spec_protocol.md` for details.
2. **"Input" Zone:** A text box to paste the raw "Discussion Minutes" (the LLM's reply).
3. **"Structure" View:** A sidebar showing the current headers of the Master Document (e.g., `1. Auth`, `2. Database`).
4. **"The Arbiter" (Review Zone):** The core interactive area.
* *Left Col:* Original Paragraph (found via matching); New paragraph (from the LLM).
* *Right Col:* Proposed Merged Paragraph. (editable)
* *Action:* Buttons for "Accept Merge", "Insert as New", or "Discard".


5. **"Download" Button:** Get the current `.md` file.

#### **B. Storage Strategy (The File System)**

You will persist the state using two simple files in a `./data` folder on the server:

1. **`master_spec.md` (The Truth):**
* The human-readable Markdown file. This is what you download at the end of the day.
* *Updated:* Every time you click "Accept" in the UI.


2. **`vector_store.json` (The Cache):**
* **Purpose:** Speed. We don't want to re-calculate vectors for the whole document every time you paste a reply.
* **Content:** A JSON list mapping Paragraph IDs to their Vector Embeddings.
* *Format:* `[{ "id": "p_1", "text": "...", "vector": [0.12, -0.4, ...] }, ...]`
* *Logic:* When `master_spec.md` is updated, we only re-calculate embeddings for the *changed* paragraphs and update this JSON file.



#### **C. Workflow Logic**

1. **User** pastes text -> **Server** runs Regex Destructurer.
2. **Server** sends new text to Ollama (`nomic-embed-text`) -> Gets Vector A.
3. **Server** loads `vector_store.json` -> Calculates Cosine Similarity -> Finds Paragraph B (Best Match).
4. **Server** sends (A + B) to Ollama (`llama3.2`) -> Asks for a Merge -> Gets Result C.
5. **UI** shows "A vs C".
6. **User** accepts -> **Server** overwrites A with C in `master_spec.md` AND updates `vector_store.json`.

### 4. Notes

We use uv to manage our Python environment.

