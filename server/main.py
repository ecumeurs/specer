import re
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from server.document_manager import manager

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("specer")

app = FastAPI()

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
    manager.save_document(req.name, req.content)
    logger.info(f"COMMIT Success: Document '{req.name}' saved.")
    return {"message": "Document saved successfully."}

# Stub Endpoints for Phase 1

from server.vector_store import store
from server.ollama_client import ollama

# ... (Imports)

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
async def get_diff(req: DiffRequest):
    logger.info("DIFF Request: Generating merge proposal via LLM...")
    # Call Llama 3.2 to merge
    merged_text = await ollama.generate_merge(req.original, req.new, "Merge update into section")
    logger.info(f"DIFF Success: Generated {len(merged_text)} chars.")
    
    return {
        "merged": merged_text
    }

# Mount static files (Frontend)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
