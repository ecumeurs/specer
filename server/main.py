import re
import logging
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Literal
from dotenv import load_dotenv
from server.document_manager import manager
from server.markdown_renderer import render_markdown

# Load environment variables from .env file (GEMINI_API_KEY etc.)
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("specer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup."""
    asyncio.create_task(_idle_cleanup_loop())
    yield


app = FastAPI(lifespan=lifespan)

class InitRequest(BaseModel):
    name: str
    reset: bool = False

class ProcessRequest(BaseModel):
    name: str
    text: str

class DiffRequest(BaseModel):
    original: str
    new: str

class CommitRequest(BaseModel):
    name: str
    content: str

class RenderResponse(BaseModel):
    """Response model for render endpoints."""
    content: str
    format: str

# API Endpoints

@app.post("/api/init")
async def init_doc(req: InitRequest):
    logger.info(f"INIT Request: name='{req.name}', reset={req.reset}")
    msg = manager.init_document(req.name, req.reset)
    return {"message": msg, "content": manager.get_document(req.name)}

@app.get("/api/spec/{name}")
async def get_spec(name: str):
    logger.info(f"FETCH Request: name='{name}'")
    content = manager.get_document(name)
    if not content:
        logger.warning(f"Document '{name}' not found.")
        raise HTTPException(status_code=404, detail="Document not found")
    return {"content": content}

@app.get("/api/structure/{name}")
async def get_structure(name: str):
    logger.info(f"STRUCTURE Request: name='{name}'")
    return {"structure": manager.get_structure(name)}

@app.post("/api/commit")
async def commit_doc(req: CommitRequest):
    logger.info(f"COMMIT Request: name='{req.name}', size={len(req.content)} chars")
    # Use simple save (no version bump) for intermediate merge commits
    manager.save_document_simple(req.name, req.content)
    logger.info(f"COMMIT Success: Document '{req.name}' saved.")
    return {"message": "Document saved successfully."}

# -------------------------------------------------------------------------
# Version Control Endpoints
# -------------------------------------------------------------------------

class ValidateMergeRequest(BaseModel):
    """Request to validate all merges are complete and bump version."""
    name: str
    comment: Optional[str] = None

class RollbackRequest(BaseModel):
    """Request to rollback to a specific version."""
    name: str
    version: int

@app.get("/api/versions/{name}")
async def get_versions(name: str):
    """
    Get version history for a document.
    
    Returns list of all versions with metadata.
    """
    logger.info(f"VERSIONS Request: name='{name}'")
    versions = manager.list_versions(name)
    vc_data = manager.get_vc_data(name)
    return {
        "current_version": vc_data.get("current_version", 0),
        "versions": versions
    }

@app.get("/api/download/{name}")
async def download_document(name: str, annotated: bool = False):
    """
    Download document content.
    
    Args:
        name: Document name
        annotated: If True, include version annotations in output
        
    Returns:
        Document content (plain or annotated)
    """
    logger.info(f"DOWNLOAD Request: name='{name}', annotated={annotated}")
    
    if annotated:
        content = manager.get_document_annotated(name)
    else:
        content = manager.get_document(name)
    
    if not content:
        logger.warning(f"Document '{name}' not found.")
        raise HTTPException(status_code=404, detail="Document not found")
    
    vc_data = manager.get_vc_data(name)
    return {
        "content": content,
        "version": vc_data.get("current_version", 1),
        "annotated": annotated
    }

@app.post("/api/validate-merge")
async def validate_merge_complete(req: ValidateMergeRequest):
    """
    Validate that all merges are complete and increment version.
    
    Call this when user confirms all pending merges have been processed.
    This triggers a version bump with 'merge_complete' trigger.
    """
    logger.info(f"VALIDATE-MERGE Request: name='{req.name}'")
    
    content = manager.get_document(req.name)
    if not content:
        raise HTTPException(status_code=404, detail="Document not found")
    
    manager.complete_merge_validation(req.name, req.comment)
    vc_data = manager.get_vc_data(req.name)
    
    logger.info(f"VALIDATE-MERGE Success: '{req.name}' now at version {vc_data['current_version']}")
    return {
        "message": "Merge validated and version incremented.",
        "version": vc_data["current_version"]
    }

@app.post("/api/rollback")
async def rollback_document(req: RollbackRequest):
    """
    Rollback document to a previous version.
    
    Creates a new version entry with 'rollback' trigger.
    """
    logger.info(f"ROLLBACK Request: name='{req.name}', target_version={req.version}")
    
    success = manager.rollback_to_version(req.name, req.version)
    
    if not success:
        logger.warning(f"ROLLBACK Failed: Version {req.version} not found for '{req.name}'")
        raise HTTPException(status_code=404, detail=f"Version {req.version} not found")
    
    vc_data = manager.get_vc_data(req.name)
    logger.info(f"ROLLBACK Success: '{req.name}' rolled back to v{req.version}, now at v{vc_data['current_version']}")
    
    return {
        "message": f"Document rolled back to version {req.version}.",
        "new_version": vc_data["current_version"],
        "content": manager.get_document(req.name)
    }

# -------------------------------------------------------------------------
# Render Endpoints
# -------------------------------------------------------------------------

@app.get("/api/render/section/{name}/{section_title}")
async def render_section(
    name: str,
    section_title: str,
    format: Literal["markdown", "html"] = Query(default="markdown")
) -> RenderResponse:
    """
    Render a specific section in the requested format.
    
    Args:
        name: Document name
        section_title: Title of the section to render
        format: Output format (markdown or html)
        
    Returns:
        RenderResponse with content and format
    """
    logger.info(f"RENDER SECTION Request: name='{name}', section='{section_title}', format='{format}'")
    
    # Get document structure
    structure = manager.get_structure(name)
    
    # Find the section
    section = None
    for item in structure:
        if item["title"].lower() == section_title.lower():
            section = item
            break
    
    if not section:
        raise HTTPException(status_code=404, detail=f"Section '{section_title}' not found")
    
    content = section["content"]
    
    # Render to HTML if requested
    if format == "html":
        content = render_markdown(content)
    
    return RenderResponse(content=content, format=format)

@app.get("/api/render/document/{name}")
async def render_document(
    name: str,
    format: Literal["markdown", "html"] = Query(default="markdown")
) -> RenderResponse:
    """
    Render the full document in the requested format.
    
    Args:
        name: Document name
        format: Output format (markdown or html)
        
    Returns:
        RenderResponse with content and format
    """
    logger.info(f"RENDER DOCUMENT Request: name='{name}', format='{format}'")
    
    content = manager.get_document(name)
    
    if not content:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Render to HTML if requested
    if format == "html":
        content = render_markdown(content)
    
    return RenderResponse(content=content, format=format)

@app.post("/api/render/preview")
async def render_preview(req: ProcessRequest) -> RenderResponse:
    """
    Render arbitrary markdown content as HTML without saving.
    
    Useful for previewing merge results or other temporary content.
    
    Args:
        req: ProcessRequest with markdown text to render
        
    Returns:
        RenderResponse with HTML content
    """
    logger.info(f"RENDER PREVIEW Request: {len(req.text)} chars")
    
    html = render_markdown(req.text)
    
    return RenderResponse(content=html, format="html")


# Stub Endpoints for Phase 1

from server.vector_store import store
from server.ollama_client import ollama
import uuid
import asyncio

# Task Manager State
# Map task_id -> {"status": "pending"|"completed"|"failed"|"cancelled", "result": ..., "task_obj": asyncio.Task}
tasks = {}

async def run_merge_task(task_id: str, req: DiffRequest):
    try:
        logger.info(f"Task {task_id}: Starting merge...")
        # We can implement explicit cancellation check if we want, but task.cancel() handles the await
        merged_text = await ollama.generate_merge(req.original, req.new, "Merge update into section")
        
        # Log result details
        if merged_text is None:
             logger.error(f"Task {task_id}: merged_text is None!")
        else:
             logger.info(f"Task {task_id}: Generated {len(merged_text)} chars. Content Preview: {merged_text[:50]}...")

        tasks[task_id]["result"] = merged_text
        tasks[task_id]["status"] = "completed"
        logger.info(f"Task {task_id}: Completed.")
    except asyncio.CancelledError:
        logger.info(f"Task {task_id}: Cancelled.")
        tasks[task_id]["status"] = "cancelled"
    except Exception as e:
        logger.error(f"Task {task_id}: Failed with {e}")
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["error"] = str(e)

@app.post("/api/process")
async def process_text(req: ProcessRequest):
    logger.info(f"PROCESS Request: Analyzing input ({len(req.text)} chars)")
    
    # Regex to parse the protocol
    # Updated to support optional bullet points (* ) and flexible whitespace
    pattern = r"<<<SPEC_START>>>\s+(?:[*]\s*)?Target-Section:\s*(.*?)\n\s*(?:[*]\s*)?Change-Summary:\s*(.*?)\n\s*(.*?)<<<SPEC_END>>>"
    matches = list(re.finditer(pattern, req.text, re.DOTALL))
    
    if not matches:
        logger.warning("PROCESS Failed: No protocol matches found.")
        return {"status": "error", "message": "Protocol not found or invalid format."}
    
    logger.info(f"PROCESS: Found {len(matches)} protocol blocks.")
    results = []
    
    # Get current structure for exact/fuzzy matching
    current_structure = manager.get_structure(req.name)
    existing_titles = {item['title']: item['content'] for item in current_structure}

    for i, match in enumerate(matches):
        target_section_intent = match.group(1).strip()
        change_summary = match.group(2).strip()
        raw_content = match.group(3).strip()
        
        # Splitting logic: Split by headers but respect hierarchy
        # We only split if the new header level is <= current chunk's header level
        # e.g. ### Header (3) -> #### Subheader (4) : Keep together
        # e.g. ### Header (3) -> ### Header (3) : Split
        # e.g. ### Header (3) -> ## Header (2) : Split
        
        chunks = []
        lines = raw_content.split('\n')
        current_chunk = []
        current_header_level = None # None means introductory text (level 0 essentially, but headers always split it)
        
        for line in lines:
            header_match = re.match(r'^(#+)\s', line)
            if header_match:
                level = len(header_match.group(1))
                
                # Decide whether to split
                should_split = False
                if current_chunk:
                    if current_header_level is None:
                        # Previous was intro text, header always splits it
                        should_split = True
                    elif level <= current_header_level:
                        # Same or higher level header (e.g. H3 <= H3, H2 <= H3) -> Split
                        should_split = True
                    # else: H4 > H3 -> Don't split, append as child
                
                if should_split:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = [line]
                    current_header_level = level
                else:
                    # Append (either start of first chunk, or child header)
                    current_chunk.append(line)
                    # If this was the first header of the block/chunk, set level
                    if current_header_level is None:
                         current_header_level = level
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        if not chunks and raw_content:
            chunks = [raw_content]
            
        logger.info(f"  Block {i+1}: Intent='{target_section_intent}', Split into {len(chunks)} chunks")

        for chunk in chunks:
            # 1. Inspect Chunk for Header override
            # If the chunk defines its own header (e.g. ### Milestone 1), and that header is NEW,
            # we should treat it as a new section regardless of what the Target-Section intent says (which might be the parent).
            
            chunk_header_title = None
            first_line = chunk.split('\n')[0].strip()
            if first_line.startswith('#'):
                 chunk_header_title = first_line.lstrip('#').strip()
            
            force_new_section_title = None
            if chunk_header_title:
                # Check if this specific header exists
                is_existing_header = False
                for t in existing_titles.keys():
                    if t.lower() == chunk_header_title.lower():
                        is_existing_header = True
                        break
                
                # If not existing, and looks like a Feature/Milestone, force NEW.
                lower_header = chunk_header_title.lower()
                if not is_existing_header and (
                    lower_header.startswith("milestone") or 
                    lower_header.startswith("feature")
                ):
                    force_new_section_title = chunk_header_title
            
            if force_new_section_title:
                 section_title = force_new_section_title
                 original_text = "(New Section)"
                 logger.info(f"    -> Chunk defines new header '{section_title}'. Forcing New Section.")
            else:
                # 2. Try Structure Match (Exact or Suffix) for Intent
                matched_title = None
                matched_content = None

                # Clean intent (remove "Feature: " prefix if present to match headers?)
                # Actually, let's try to match the intent against the titles.
                # Intent: "Context, Aim & Integration: Integration"
                # Config Title: "Integration" (nested under Context...)
                
                # Simple heuristic: Does any existing title end with the intent? 
                # OR Does the intent end with any existing title?
                
                # Case A: Intent is full path "A: B". Title is "B".
                # Check if title is a suffix of intent? NO, intent might be "Update Integration".
                
                # Let's iterate over existing titles and check for matches
                best_structure_match = None
                
                # Normalize intent
                norm_intent = target_section_intent.lower()

                for title, content in existing_titles.items():
                    norm_title = title.lower()
                    
                    # Exact match
                    if norm_intent == norm_title:
                        best_structure_match = title
                        break
                    
                    # Suffix match: Intent "Context: Integration" matches Title "Integration"
                    if norm_intent.endswith(": " + norm_title) or norm_intent.endswith("-> " + norm_title):
                         best_structure_match = title # We keep looking for exact match, but keep this as candidate
                    
                if best_structure_match:
                     matched_title = best_structure_match
                     matched_content = existing_titles[matched_title]
                     logger.info(f"    -> Structure Match: Intent='{target_section_intent}' matched Section='{matched_title}'")

                if matched_title:
                    original_text = matched_content
                    section_title = matched_title
                else:
                    # 3. Check for Explicit "New" Intents (Feature/Milestone) in the INTENT string
                    # If the intent explicitly names a Feature or Milestone that didn't match existing structure,
                    # we force it as a NEW section to avoid Semantic Search mistakenly matching sub-headers (like "Context").
                    is_explicit_new = False
                    lower_intent = target_section_intent.lower()
                    if lower_intent.startswith("feature:") or lower_intent.startswith("milestone:") or \
                       lower_intent.startswith("feature ") or lower_intent.startswith("milestone "):
                        is_explicit_new = True
                    
                    if is_explicit_new:
                         section_title = target_section_intent
                         original_text = "(New Section)"
                         logger.info(f"    -> Explicit New Section intent: '{target_section_intent}'. Skipping semantic search.")
                    else:
                        # 4. Semantic Search (Fallback)
                        # We try to find the best match for this specific chunk
                        best_match = await store.find_best_match(req.name, target_section_intent + "\n" + chunk)
                        
                        if not best_match:
                            original_text = "(No matching section found. Will be added as new.)"
                            # If the chunk starts with a header, use that as the section title
                            first_line = chunk.split('\n')[0]
                            if first_line.startswith('#'):
                                 section_title = first_line.lstrip('#').strip()
                            else:
                                 section_title = f"{target_section_intent}" 
                            
                            logger.info(f"    -> No semantic match for chunk using '{target_section_intent}'. Added as new.")
                        else:
                            original_text = best_match["text"]
                            section_title = best_match["header"]
                            logger.info(f"    -> Semantic Match: '{section_title}' (Score: {best_match.get('score', 'N/A')})")
                
            results.append({
                "section": section_title,
                "original_text": original_text,
                "new_text": chunk,
                "summary": change_summary
            })
    
    return {
        "status": "success",
        "matches": results
    }

@app.post("/api/diff")
async def start_diff_task(req: DiffRequest):
    logger.info("DIFF Request: Starting background merge task...")
    task_id = str(uuid.uuid4())
    
    # Create asyncio task
    task = asyncio.create_task(run_merge_task(task_id, req))
    
    tasks[task_id] = {
        "status": "pending",
        "result": None,
        "task_obj": task
    }
    
    return {"task_id": task_id}

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    t = tasks[task_id]
    return {
        "task_id": task_id,
        "status": t["status"],
        "result": t.get("result"),
        "error": t.get("error")
    }

@app.post("/api/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    if task_id not in tasks:
         raise HTTPException(status_code=404, detail="Task not found")
         
    t = tasks[task_id]
    if t["status"] in ["pending", "running"]: # Treating pending as running for simplicity
        t["task_obj"].cancel()
        t["status"] = "cancelled"
        logger.info(f"Cancellation requested for Task {task_id}")
        return {"message": "Cancellation requested"}
    
    return {"message": "Task already completed or cancelled"}


# -------------------------------------------------------------------------
# Summary Generation Endpoint
# -------------------------------------------------------------------------

class SummaryRequest(BaseModel):
    """Request to generate an AI summary for a feature section.

    Attributes:
        name:    Document name (used to look up the section content).
        section: Exact title of the feature section to summarise
                 (e.g. ``"Feature: User Authentication"``).
    """
    name: str
    section: str


@app.post("/api/summary")
async def generate_summary(req: SummaryRequest):
    """Generate a 100–200 word Ollama summary for a feature section.

    Steps:
        1. Look up the section in the document structure (404 if missing).
        2. Gather full content including child sub-sections.
        3. Call ``ollama.generate_summary(content)``.
        4. Return ``{"summary": "<text>"}`` or raise 500 on Ollama error.
    """
    logger.info(f"SUMMARY Request: doc='{req.name}', section='{req.section}'")

    structure = manager.get_structure(req.name)
    if not structure:
        raise HTTPException(status_code=404, detail=f"Document '{req.name}' not found.")

    # Locate the requested section (case-insensitive)
    idx = next(
        (i for i, s in enumerate(structure) if s["title"].lower() == req.section.lower()),
        None
    )
    if idx is None:
        raise HTTPException(status_code=404, detail=f"Section '{req.section}' not found.")

    # Gather section + all children
    base_level = structure[idx]["level"]
    parts = [structure[idx]["content"]]
    for s in structure[idx + 1:]:
        if s["level"] <= base_level:
            break
        parts.append(s["content"])
    full_content = "\n".join(parts)

    summary_text = await ollama.generate_summary(full_content)

    if summary_text.startswith("Error:"):
        logger.error(f"SUMMARY Failed for '{req.section}': {summary_text}")
        raise HTTPException(status_code=500, detail=summary_text)

    logger.info(f"SUMMARY Success: '{req.section}' → {len(summary_text)} chars")
    return {"summary": summary_text}


# -------------------------------------------------------------------------
# Gemini Chat Endpoints
# -------------------------------------------------------------------------

from server.gemini_client import gemini_client, session_repo, DEFAULT_MODEL
import uuid as _uuid


class GeminiSessionRequest(BaseModel):
    """
    Request to open a new Gemini chat session.

    Attributes:
        doc_name:               Document to work on (used to fetch structure/content).
        scope:                  "document" for a global discussion, or an exact section
                                title (e.g. "Feature: Auth") for a focused conversation.
        model:                  Gemini model ID. Defaults to gemini-3-flash-preview.
        include_global_context: If True and a top-level "Context, Aim & Integration"
                                section exists, its content is appended to the system prompt.
    """
    doc_name: str = "default"
    scope: str = "document"
    model: str = DEFAULT_MODEL
    include_global_context: bool = True


class GeminiChatRequest(BaseModel):
    """
    Request to send one user turn within an existing chat session.

    Attributes:
        message:         The user's message text.
        linked_sections: Section titles whose content should be prepended to this
                         message (sent once; the UI clears chips after send).
    """
    message: str
    linked_sections: list[str] = []


# Background task: evict idle sessions every 60 s
async def _idle_cleanup_loop():
    while True:
        await asyncio.sleep(60)
        removed = await session_repo.cleanup_idle()
        if removed:
            logger.info(f"[Cleanup] Evicted {removed} idle Gemini session(s)")



@app.get("/api/gemini/models")
async def list_gemini_models():
    """
    Return the list of Gemini models available for structured-output chat.

    The list is ordered: preferred / newer models appear first.
    Falls back to a hard-coded default list if the API key is not set.
    """
    models = await gemini_client.list_models()
    return {"models": models, "default": DEFAULT_MODEL}


@app.post("/api/gemini/session", status_code=201)
async def create_gemini_session(req: GeminiSessionRequest):
    """
    Create a new Gemini chat session.

    - Fetches the document structure and section content from DocumentManager.
    - Builds the system prompt (doc tree + scope content + optional global context).
    - Creates a google-genai Chat object stored server-side.

    Returns:
        session_id (str): UUID to use in subsequent /api/gemini/chat and DELETE calls.
    """
    structure = manager.get_structure(req.doc_name)
    if not structure and req.scope != "document":
        raise HTTPException(status_code=404, detail=f"Document '{req.doc_name}' not found.")

    # Build flat tree list for system prompt
    doc_tree = [{"title": s["title"], "level": s["level"]} for s in structure]

    # --- Resolve scope content ---
    if req.scope == "document":
        scope_label = "Document level"
        scope_content = manager.get_document(req.doc_name)
    else:
        # Find matching section + all its children
        idx = next(
            (i for i, s in enumerate(structure) if s["title"].lower() == req.scope.lower()),
            None
        )
        if idx is None:
            raise HTTPException(status_code=404, detail=f"Section '{req.scope}' not found.")

        scope_label = req.scope
        base_level = structure[idx]["level"]
        # Gather section + children
        parts = [structure[idx]["content"]]
        for s in structure[idx + 1:]:
            if s["level"] <= base_level:
                break
            parts.append(s["content"])
        scope_content = "\n".join(parts)

    # --- Optional global context (top-level "Context, Aim & Integration") ---
    global_context: Optional[str] = None
    if req.include_global_context:
        ctx_section = next(
            (s for s in structure
             if "context" in s["title"].lower() and "aim" in s["title"].lower()
             and s["level"] == 2),
            None
        )
        if ctx_section:
            # Include the section and its children
            ctx_idx = structure.index(ctx_section)
            ctx_parts = [ctx_section["content"]]
            for s in structure[ctx_idx + 1:]:
                if s["level"] <= ctx_section["level"]:
                    break
                ctx_parts.append(s["content"])
            global_context = "\n".join(ctx_parts)

    system_prompt = gemini_client.build_system_prompt(
        doc_tree=doc_tree,
        scope_label=scope_label,
        scope_content=scope_content,
        global_context=global_context,
    )

    session_id = str(_uuid.uuid4())

    try:
        await session_repo.create(
            session_id=session_id,
            model=req.model,
            system_prompt=system_prompt,
            doc_name=req.doc_name,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    logger.info(f"[Gemini] Session created: {session_id} scope='{scope_label}' model='{req.model}'")
    return {"session_id": session_id, "model": req.model, "scope": scope_label}


@app.get("/api/gemini/session/{session_id}")
async def get_gemini_session(session_id: str):
    """
    Return metadata for an active Gemini chat session.

    Returns exchange_count, model, timestamps, and a `warn` flag
    that turns True when exchange_count reaches 15.
    """
    info = await session_repo.info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    return info


@app.delete("/api/gemini/session/{session_id}", status_code=204)
async def destroy_gemini_session(session_id: str):
    """
    Destroy a Gemini chat session and release its memory.

    Idempotent: returns 204 even if the session has already expired.
    """
    await session_repo.destroy(session_id)
    logger.info(f"[Gemini] Session destroyed: {session_id}")
    return JSONResponse(status_code=204, content=None)


@app.post("/api/gemini/chat/{session_id}")
async def gemini_chat(session_id: str, req: GeminiChatRequest):
    """
    Send one user turn to an active Gemini chat session.

    If `linked_sections` is non-empty, each section's content is fetched from
    the document (identified by the session's stored doc_name) and prepended
    to the message before sending to the SDK. The UI clears chips after each
    send — linked sections are strictly one-shot per message.

    Returns:
        GeminiSpecResponse fields (discussion, commit_summary, updates)
        plus exchange_count and warn flag.
    """
    # Verify session exists before doing any work
    info = await session_repo.info(session_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    # Build the final message, prepending any linked-section content
    message_parts = []
    if req.linked_sections:
        doc_name = info["doc_name"]
        structure = manager.get_structure(doc_name)
        title_to_content = {s["title"]: s["content"] for s in structure}

        for section_title in req.linked_sections:
            # Case-insensitive lookup
            content = next(
                (v for k, v in title_to_content.items()
                 if k.lower() == section_title.lower()),
                None
            )
            if content:
                message_parts.append(
                    f"[LINKED SECTION: {section_title}]\n{content}\n---"
                )
            else:
                logger.warning(f"[Gemini] Linked section not found: '{section_title}'")

    message_parts.append(req.message)
    message = "\n\n".join(message_parts)

    try:
        parsed = await session_repo.send(session_id, message)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(f"[Gemini] Unexpected error in session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {exc}")

    # Re-fetch info for updated exchange_count
    info = await session_repo.info(session_id)
    return {
        **parsed.model_dump(),
        "exchange_count": info["exchange_count"] if info else 0,
        "warn": info["warn"] if info else False,
    }



# Mount static files (Frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
