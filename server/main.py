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
    
    for i, match in enumerate(matches):
        target_section_intent = match.group(1).strip()
        change_summary = match.group(2).strip()
        raw_content = match.group(3).strip()
        
        # Splitting logic: Split by headers
        chunks = []
        lines = raw_content.split('\n')
        current_chunk = []
        
        for line in lines:
            if re.match(r'^#+\s', line):
                if current_chunk:
                    chunks.append("\n".join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        if not chunks and raw_content:
            chunks = [raw_content]
            
        logger.info(f"  Block {i+1}: Intent='{target_section_intent}', Split into {len(chunks)} chunks")

        for chunk in chunks:
            # Semantic Search for each chunk
            # We try to find the best match for this specific chunk
            # If the chunk has a header, we might assume it is a section title.
            
            best_match = await store.find_best_match(req.name, target_section_intent + "\n" + chunk)
            
            if not best_match:
                original_text = "(No matching section found. Will be added as new.)"
                # If the chunk starts with a header, use that as the section title
                first_line = chunk.split('\n')[0]
                if first_line.startswith('#'):
                     section_title = first_line.lstrip('#').strip()
                else:
                     section_title = f"{target_section_intent} (New)"
                
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
